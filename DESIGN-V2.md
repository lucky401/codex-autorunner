6. Web Server + Web UI (V2)

V2 adds a serve command that starts a local HTTP server and web UI while reusing the same core engine.

6.1 Process Model

Single process, single repo.

Components:

HTTP server (e.g., FastAPI).

RunnerManager that controls the background loop in a thread.

File-based state as before.

RunnerManager example:

class RunnerManager:
    def __init__(self, repo_root, config):
        self.repo_root = repo_root
        self.config = config
        self.thread = None
        self.stop_flag = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag.set()

    def _run_loop(self):
        run_loop(self.repo_root, self.config, external_stop_flag=self.stop_flag)


Modify run_loop() to periodically check external_stop_flag between runs.

6.2 HTTP API

Assume server binds to http://localhost:4173 by default (configurable).

6.2.1 Docs

GET /api/docs

Response:

{
  "todo": "...",
  "progress": "...",
  "opinions": "..."
}


PUT /api/docs/{kind}

kind ∈ todo, progress, opinions.

Body: { "content": "..." }.

Overwrite file atomically.

Return updated content and maybe last modified timestamp.

6.2.2 Runner Control

GET /api/state

Returns state.json plus derived fields (e.g., outstanding TODO count).

POST /api/run/start

Body: empty or { "once": true }.

Starts RunnerManager:

If once=true, run only one iteration.

Otherwise, run the usual loop.

Returns current state.

POST /api/run/stop

Sets stop_flag in RunnerManager.

Returns updated state after marking a graceful stop.

6.2.3 Logs

GET /api/logs?run_id=&tail=

If run_id provided, return that run’s block.

Else if tail provided, return last tail lines.

Else default to last run’s block.

GET /api/logs/stream

Server-Sent Events (SSE) or WebSocket streaming.

Emits new log lines as they are appended.

6.2.4 Chat with Codex

POST /api/chat

Body:

{
  "message": "How should I structure the migration?",
  "include_todo": true,
  "include_progress": true,
  "include_opinions": true
}


Build a “chat-style” Codex prompt:

Optional inclusion of TODO/PROGRESS/OPINIONS (read-only).

Include user message clearly as <USER_MESSAGE>.

Clarify that Codex should primarily respond with guidance, and only modify files if explicitly requested.

Run a single Codex CLI process (separate from the autorun loop).

Return:

{
  "run_id": 27,
  "response": "..."
}


or stream the response via SSE/WebSocket.

The chat endpoint does not automatically update TODO/PROGRESS/OPINIONS; the user can apply changes manually or via dedicated UI actions.

6.3 Web UI

Implement as a static web application (React, Svelte, or simple HTML+JS). The UI can be served from / by the same HTTP process.

6.3.1 Views

Dashboard

Show:

Current state (idle/running/error).

Last run id, exit code, timestamps.

Number of outstanding TODO items.

Controls:

Start autorunner (continuous or once).

Stop autorunner.

Docs Editor

Three tabs: TODO, PROGRESS, OPINIONS.

Textarea or markdown editor.

Save button calling PUT /api/docs/{kind}.

Checkbox rendering for TODO lines for better readability.

Logs

Tail viewer:

Uses GET /api/logs/stream for live updates when the autorunner is running.

Controls:

Choose a run id.

Tail last N lines.

Chat

Chat panel:

Conversation-like view (messages from user and Codex).

Input box for message.

Checkboxes for including TODO/PROGRESS/OPINIONS.

On submit:

Send to /api/chat.

Display streaming response.

Optional: “Add as TODO” button that:

Converts a chat suggestion into a new - [ ] line in TODO.md via PUT /api/docs/todo.

6.3.2 Mobile Responsiveness

Use a mobile-first layout with:

Top or bottom navigation (Dashboard/Docs/Logs/Chat).

Simple, vertical content stacking.

Avoid heavy frameworks or complex state management to keep bundle small.

6.3.3 Authentication

MVP: local machine usage only, bind to localhost with no auth.

Keep a simple config field for future optional token:

Example:

server:
  auth_token: null


If non-null, require an Authorization header.

7. Extensibility and Best-practice Hooks
7.1 Config Versioning

Store version in config.yml.

On load:

If version mismatched, either:

Apply migration code, or

Fail with a clear error until manual migration.

7.2 Additional Docs

Extend config to allow extra read-only docs in future:

docs:
  todo: "TODO.md"
  progress: "PROGRESS.md"
  opinions: "OPINIONS.md"
  extras:
    - name: "ARCHITECTURE"
      path: "ARCHITECTURE.md"
      include_in_prompt: true


V1 can ignore extras; V2+ can include them in prompts and display them in the UI.

7.3 Prompt Templates

Storing the prompt as a file (prompt.txt) enables per-repo customization without code changes.

Use simple placeholder syntax:

{{TODO}}, {{PROGRESS}}, {{OPINIONS}}, {{PREV_RUN_OUTPUT}}.

If template is missing, fallback to built-in default.

7.4 Metrics Hook (Optional, Not Required)

Add a small internal function:

def report_event(kind: str, payload: dict):
    pass


Initially, implement as a no-op or log to stdout.

Later, users can patch/extend to send metrics to their system of choice.

7.5 Backend Abstraction (Minimal)

Define a very small interface for the Codex backend:

class CodexBackend(Protocol):
    def run(self, prompt: str, run_id: int) -> CodexResult:
        ...


Implement CLIBackend that uses the Codex CLI.

Add MockBackend for tests.

Do not build a full plugin system; keep this simple.

8. Implementation Order

Suggested implementation steps:

Core data structures:

Config model, state model, TODO parser.

File IO helpers:

Atomic reads/writes, log append, run extraction.

Codex backend:

CLIBackend with streaming.

Core engine:

build_prompt, extract_run_output, run_loop.

CLI:

init, run, once, status, log, edit, doctor.

Locking and basic error handling.

Web server:

serve command.

HTTP API endpoints.

RunnerManager.

Web UI:

Dashboard, Docs, Logs, Chat.

This yields a product that is robust, straightforward to reason about, and easy to extend without over-engineering.