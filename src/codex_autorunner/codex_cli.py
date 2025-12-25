import json
import re
import subprocess
from typing import Iterable, Optional, Tuple

from .utils import resolve_executable, subprocess_env

SUBCOMMAND_HINTS = ("exec", "resume")


def extract_flag_value(args: Iterable[str], flag: str) -> Optional[str]:
    if not args:
        return None
    for arg in args:
        if not isinstance(arg, str):
            continue
        if arg.startswith(f"{flag}="):
            return arg.split("=", 1)[1] or None
    args_list = [str(a) for a in args]
    for idx, arg in enumerate(args_list):
        if arg == flag and idx + 1 < len(args_list):
            return args_list[idx + 1]
    return None


def strip_flag(args: Iterable[str], flag: str) -> list[str]:
    cleaned: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        arg_str = str(arg)
        if arg_str == flag:
            skip_next = True
            continue
        if arg_str.startswith(f"{flag}="):
            continue
        cleaned.append(arg_str)
    return cleaned


def inject_flag(
    args: Iterable[str],
    flag: str,
    value: Optional[str],
    *,
    subcommands: Iterable[str] = SUBCOMMAND_HINTS,
) -> list[str]:
    if not value:
        return [str(a) for a in args]
    args_list = [str(a) for a in args]
    if extract_flag_value(args_list, flag):
        return args_list
    insert_at = None
    for cmd in subcommands:
        try:
            insert_at = args_list.index(cmd)
            break
        except ValueError:
            continue
    if insert_at is None:
        return [flag, value] + args_list
    return args_list[:insert_at] + [flag, value] + args_list[insert_at:]


def apply_codex_options(
    args: Iterable[str],
    *,
    model: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> list[str]:
    with_model = inject_flag(args, "--model", model)
    return inject_flag(with_model, "--reasoning", reasoning)


def _run_codex_cli(binary: str, args: list[str]) -> Tuple[Optional[str], Optional[str]]:
    resolved = resolve_executable(binary)
    if not resolved:
        return None, f"Codex binary not found: {binary}"
    try:
        proc = subprocess.run(
            [resolved, *args],
            capture_output=True,
            text=True,
            timeout=3,
            env=subprocess_env(),
        )
    except Exception as exc:
        return None, str(exc)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return None, detail or f"codex exited {proc.returncode}"
    return (proc.stdout or "").strip(), None


def _parse_json_list(payload: str) -> list[str]:
    try:
        data = json.loads(payload)
    except Exception:
        return []
    if isinstance(data, list):
        return [str(item) for item in data if item]
    if isinstance(data, dict):
        for key in ("models", "data", "reasoning", "levels"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                out: list[str] = []
                for item in items:
                    if isinstance(item, dict):
                        val = item.get("id") or item.get("name") or item.get("value")
                        if val:
                            out.append(str(val))
                    elif item:
                        out.append(str(item))
                return out
    return []


def _parse_text_list(payload: str) -> list[str]:
    out: list[str] = []
    for line in payload.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.lower().startswith("available"):
            continue
        if cleaned.startswith("-"):
            cleaned = cleaned[1:].strip()
        match = re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]*", cleaned)
        out.append(match.group(0) if match else cleaned)
    return out


def discover_codex_models(binary: str) -> Tuple[list[str], str, Optional[str]]:
    payload, error = _run_codex_cli(binary, ["models", "--json"])
    if payload:
        parsed = _parse_json_list(payload)
        if parsed:
            return sorted(set(parsed)), "codex-cli", None
    payload, error = _run_codex_cli(binary, ["models"])
    if payload:
        parsed = _parse_text_list(payload)
        if parsed:
            return sorted(set(parsed)), "codex-cli", None
    return [], "none", error


def discover_codex_reasoning(binary: str) -> Tuple[list[str], str, Optional[str]]:
    default_levels = ["low", "medium", "high", "xhigh"]
    return default_levels, "default", None
