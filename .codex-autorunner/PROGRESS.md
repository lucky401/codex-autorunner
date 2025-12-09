# Progress

- Initialized codex-autorunner project structure and CLI.
- Added default docs (TODO, PROGRESS, OPINIONS) and config for dogfooding.
- Installed package locally via `pip install -e .` for immediate CLI availability.
- Implemented V2 backend pieces: FastAPI server, RunnerManager threading, chat endpoint, log streaming, and serve command.
- Added server config defaults (host/port/auth token) and updated deps for FastAPI/Uvicorn.
- Pinned Click to <8.2 to keep Typer help output working.
- Prepared backlog for building the V2 web UI and wiring SSE/WebSocket streams.
- Added kill/resume support (CLI + API), runner PID tracking, and status reporting for headless control.
- Relocated TODO/PROGRESS/OPINIONS into .codex-autorunner/ and set config defaults accordingly.
