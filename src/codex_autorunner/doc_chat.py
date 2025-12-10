import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Optional, Tuple

from asyncio.subprocess import PIPE, STDOUT

from .engine import Engine, _process_alive, timestamp
from .state import load_state
from .utils import atomic_write

ALLOWED_DOC_KINDS = ("todo", "progress", "opinions", "spec")
DOC_CHAT_TIMEOUT_SECONDS = 180


@dataclass
class DocChatRequest:
    kind: str
    message: str
    stream: bool = False


class DocChatError(Exception):
    """Base error for doc chat failures."""


class DocChatValidationError(DocChatError):
    """Raised when a request payload is invalid."""


class DocChatBusyError(DocChatError):
    """Raised when a doc chat is already running for the target doc."""


def _normalize_kind(kind: str) -> str:
    key = (kind or "").lower()
    if key not in ALLOWED_DOC_KINDS:
        raise DocChatValidationError("invalid doc kind")
    return key


def _normalize_message(message: str) -> str:
    msg = (message or "").strip()
    if not msg:
        raise DocChatValidationError("message is required")
    return msg


def format_sse(event: str, data: object) -> str:
    payload = data if isinstance(data, str) else json.dumps(data)
    lines = payload.splitlines() or [""]
    parts = [f"event: {event}"]
    for line in lines:
        parts.append(f"data: {line}")
    return "\n".join(parts) + "\n\n"


DOC_CHAT_PROMPT_TEMPLATE = """You are Codex, an autonomous coding assistant helping rewrite a single work doc for this repository.

Target doc: {doc_title}
User request: {message}

Instructions:
- Update only the {doc_title} document.
- Preserve Markdown structure and checkbox syntax; do not drop sections.
- Return the fully rewritten {doc_title} content. Optionally begin with one short summary line prefixed with "Agent:" followed by the updated document.
- Do not include diffs or explanations outside of the optional summary line.

<WORK_DOCS>
<TODO>
{todo}
</TODO>

<PROGRESS>
{progress}
</PROGRESS>

<OPINIONS>
{opinions}
</OPINIONS>

<SPEC>
{spec}
</SPEC>
</WORK_DOCS>

{recent_run_block}

<TARGET_DOC>
{target_doc}
</TARGET_DOC>
"""


class DocChatService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._locks: Dict[str, asyncio.Lock] = {
            key: asyncio.Lock() for key in ALLOWED_DOC_KINDS
        }
        self._recent_summary_cache: Optional[str] = None

    def parse_request(
        self, kind: str, payload: Optional[dict]
    ) -> DocChatRequest:
        if payload is None or not isinstance(payload, dict):
            raise DocChatValidationError("invalid payload")
        key = _normalize_kind(kind)
        message = _normalize_message(str(payload.get("message", "")))
        stream = bool(payload.get("stream", False))
        return DocChatRequest(kind=key, message=message, stream=stream)

    def repo_blocked_reason(self) -> Optional[str]:
        lock_path = self.engine.lock_path
        if lock_path.exists():
            pid_text = lock_path.read_text(encoding="utf-8").strip()
            pid = int(pid_text) if pid_text.isdigit() else None
            if pid and _process_alive(pid):
                return f"Autorunner is running (pid={pid}); try again later."
            return "Autorunner lock present; clear or resume before using doc chat."

        state = load_state(self.engine.state_path)
        if state.status == "running":
            return "Autorunner is currently running; try again later."
        return None

    def doc_busy(self, kind: str) -> bool:
        key = _normalize_kind(kind)
        return self._locks[key].locked()

    @asynccontextmanager
    async def doc_lock(self, kind: str):
        lock = self._locks[_normalize_kind(kind)]
        if lock.locked():
            raise DocChatBusyError(f"Doc chat already running for {kind}")
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def _chat_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def _log(self, chat_id: str, message: str) -> None:
        line = f"[{timestamp()}] doc-chat id={chat_id} {message}\n"
        self.engine.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.engine.log_path.open("a", encoding="utf-8") as f:
            f.write(line)

    def _doc_pointer(self, kind: str) -> str:
        path = self.engine.config.doc_path(kind)
        try:
            return str(path.relative_to(self.engine.repo_root))
        except ValueError:
            return str(path)

    @staticmethod
    def _compact_message(message: str, limit: int = 240) -> str:
        compact = " ".join((message or "").split()).replace('"', "'")
        if len(compact) > limit:
            return compact[: limit - 3] + "..."
        return compact

    def _recent_run_summary(self) -> Optional[str]:
        if self._recent_summary_cache is not None:
            return self._recent_summary_cache
        state = load_state(self.engine.state_path)
        if not state.last_run_id:
            return None
        summary = self.engine.extract_prev_output(state.last_run_id)
        self._recent_summary_cache = summary
        return summary

    def _build_prompt(self, request: DocChatRequest) -> str:
        docs = {key: self.engine.docs.read_doc(key) for key in ALLOWED_DOC_KINDS}
        target_doc = docs.get(request.kind, "")
        recent_block = self._recent_run_summary()
        recent_section = (
            f"<RECENT_RUN>\n{recent_block}\n</RECENT_RUN>"
            if recent_block
            else "<RECENT_RUN>No recent run summary available.</RECENT_RUN>"
        )
        return DOC_CHAT_PROMPT_TEMPLATE.format(
            doc_title=request.kind.upper(),
            message=request.message,
            todo=docs.get("todo", ""),
            progress=docs.get("progress", ""),
            opinions=docs.get("opinions", ""),
            spec=docs.get("spec", ""),
            recent_run_block=recent_section,
            target_doc=target_doc,
        )

    async def _run_codex_cli(self, prompt: str, chat_id: str) -> str:
        cmd = [self.engine.config.codex_binary, *self.engine.config.codex_args, prompt]
        self._log(chat_id, f"cmd={' '.join(cmd[:-1])} prompt_chars={len(prompt)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.engine.repo_root),
                stdout=PIPE,
                stderr=STDOUT,
            )
        except FileNotFoundError:
            raise DocChatError(f"Codex binary not found: {self.engine.config.codex_binary}")

        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=DOC_CHAT_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            self._log(chat_id, "timed out waiting for codex process")
            raise DocChatError("Doc chat agent timed out")

        exit_code = proc.returncode
        output = (stdout.decode("utf-8", errors="ignore") if stdout else "").strip()
        for line in output.splitlines():
            self._log(chat_id, f"stdout: {line}")
        self._log(chat_id, f"exit_code={exit_code}")
        if exit_code != 0:
            raise DocChatError(f"Codex CLI exited with code {exit_code}")
        if not output:
            raise DocChatError("Codex CLI produced no output")
        return output

    def _parse_agent_output(
        self, output: str, kind: str
    ) -> Tuple[str, str]:
        text = (output or "").strip()
        if not text:
            raise DocChatValidationError("Agent returned empty output")
        agent_message = ""
        content = text
        if text.lower().startswith("agent:"):
            lines = text.splitlines()
            agent_message = lines[0][len("agent:") :].strip()
            content = "\n".join(lines[1:]).lstrip()
        if agent_message and not content.strip():
            raise DocChatValidationError("Agent response missing document content")
        if not content.strip():
            raise DocChatValidationError("Agent returned empty document content")
        return agent_message or f"Updated {kind.upper()} via doc chat.", content

    def _validate_doc_content(self, kind: str, content: str) -> str:
        if not isinstance(content, str):
            raise DocChatValidationError("Agent returned non-string content")
        text = content.strip("\n")
        if not text.strip():
            raise DocChatValidationError("Agent returned empty document content")
        lower_text = text.lower()
        if "<work_docs>" in lower_text or "<target_doc>" in lower_text:
            raise DocChatValidationError("Agent output contained prompt markers")
        if kind == "todo":
            checkbox_lines = []
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("- ["):
                    checkbox_lines.append(stripped)
                    if not (
                        stripped.startswith("- [ ]")
                        or stripped.lower().startswith("- [x]")
                    ):
                        raise DocChatValidationError(
                            f"Malformed TODO checkbox line: {stripped}"
                        )
            if not checkbox_lines:
                raise DocChatValidationError("TODO content missing checkbox items")
        return content

    async def execute(self, request: DocChatRequest) -> dict:
        chat_id = self._chat_id()
        started_at = time.time()
        doc_pointer = self._doc_pointer(request.kind)
        message_for_log = self._compact_message(request.message)
        self._log(
            chat_id,
            f"start kind={request.kind} path={doc_pointer} message=\"{message_for_log}\"",
        )
        try:
            prompt = self._build_prompt(request)
            output = await self._run_codex_cli(prompt, chat_id)
            agent_message, content = self._parse_agent_output(output, request.kind)
            content = self._validate_doc_content(request.kind, content)
            atomic_write(self.engine.config.doc_path(request.kind), content)
            self._log(
                chat_id,
                f"wrote {request.kind} to {self.engine.config.doc_path(request.kind)}",
            )
            duration_ms = int((time.time() - started_at) * 1000)
            self._log(
                chat_id,
                "result=success "
                f"kind={request.kind} path={doc_pointer} duration_ms={duration_ms} "
                f"message=\"{message_for_log}\"",
            )
            return {
                "status": "ok",
                "kind": request.kind,
                "content": content,
                "agent_message": agent_message,
            }
        except DocChatError as exc:
            duration_ms = int((time.time() - started_at) * 1000)
            detail = self._compact_message(str(exc))
            self._log(
                chat_id,
                "result=error "
                f"kind={request.kind} path={doc_pointer} duration_ms={duration_ms} "
                f"message=\"{message_for_log}\" detail=\"{detail}\"",
            )
            return {"status": "error", "detail": str(exc)}
        except Exception as exc:  # pragma: no cover - defensive
            duration_ms = int((time.time() - started_at) * 1000)
            detail = self._compact_message(str(exc))
            self._log(
                chat_id,
                "result=error kind={kind} path={path} duration_ms={duration_ms} "
                "message=\"{message}\" detail=\"{detail}\"".format(
                    kind=request.kind,
                    path=doc_pointer,
                    duration_ms=duration_ms,
                    message=message_for_log,
                    detail=detail,
                ),
            )
            return {"status": "error", "detail": "Doc chat failed"}

    async def stream(self, request: DocChatRequest) -> AsyncIterator[str]:
        try:
            async with self.doc_lock(request.kind):
                yield format_sse("status", {"status": "queued"})
                try:
                    result = await self.execute(request)
                except DocChatError as exc:
                    yield format_sse("error", {"detail": str(exc)})
                    return
                if result.get("status") == "ok":
                    yield format_sse("update", result)
                    yield format_sse("done", {"status": "ok"})
                else:
                    detail = result.get("detail") or "Doc chat failed"
                    yield format_sse("error", {"detail": detail})
        except DocChatBusyError as exc:
            yield format_sse("error", {"detail": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            yield format_sse("error", {"detail": str(exc)})
