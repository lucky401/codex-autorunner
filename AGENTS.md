# Codex Autorunner – Agent Guide

This repo dogfoods codex-autorunner to build itself. Read this before running the agent loop.

## Layout and key files
- Core package code: `src/codex_autorunner/` (engine, CLI, server/API).
- Runtime/config/state live under `.codex-autorunner/` (not at repo root):
  - Docs the agent reads/updates: `.codex-autorunner/TODO.md`, `.codex-autorunner/PROGRESS.md`, `.codex-autorunner/OPINIONS.md`.
  - Config: `.codex-autorunner/config.yml` (docs paths, codex CLI args, server host/port/auth token).
  - State/log: `.codex-autorunner/state.json`, `.codex-autorunner/codex-autorunner.log`, `.codex-autorunner/lock`.
- Design references: `DESIGN-V1.md` (CLI/engine) and `DESIGN-V2.md` (API/server/UI).

## CLI commands
- `codex-autorunner init` (per repo) seeds `.codex-autorunner/*` docs/state/config.
- `codex-autorunner run` / `once` run the loop; `--repo PATH` targets another repo.
- `codex-autorunner resume` clears stale locks and restarts; `--once` for a single run.
- `codex-autorunner kill` sends SIGTERM to a running loop and marks state error.
- `codex-autorunner log` / `status` / `edit` are self-explanatory.
- `codex-autorunner serve` starts the FastAPI server+API (host/port from config).

## API endpoints (from `serve`)
- Docs: `GET/PUT /api/docs`, `GET /api/state`.
- Runner control: `POST /api/run/start`, `/stop`, `/kill`, `/resume`.
- Logs: `GET /api/logs` (run_id/tail) and `GET /api/logs/stream` (SSE).
- Chat: `POST /api/chat` (ad-hoc Codex prompt with optional docs).
- Responses may require `Authorization: Bearer <token>` if `server.auth_token` set.

## Dogfooding rules
- The agent should edit only the configured docs under `.codex-autorunner/`, not root-level files.
- Leave `.codex-autorunner/lock` and `state.json` alone unless cleaning up stale runs; use `kill`/`resume` commands instead of manual edits when possible.
- Keep TODO/PROGRESS/OPINIONS in sync; top TODO items drive the loop.
- Respect opinions: small, well-tested changes, minimal deps, simple UI bundle served by FastAPI, surface kill/resume controls, show runner pid/status.

## Quick start to run the loop here
1) Ensure deps are installed: `pip install -e .` (already done in this repo).
2) Verify status: `codex-autorunner status` (expect docs under `.codex-autorunner/`).
3) Start: `codex-autorunner run` (or `once`/`resume` if recovering). Use `--force` only if lock/state is stale.
4) View progress/logs: `codex-autorunner log --tail 200` or `--run N`.
5) Serve API/UI backend: `codex-autorunner serve` (defaults: 127.0.0.1:4173).

## Common pitfalls
- Don’t re-seed root-level TODO/PROGRESS/OPINIONS; use the paths in config.
- If status is stuck “running” with no process, use `codex-autorunner kill` then `resume`.
- `.gitignore` already excludes runtime artifacts; keep it that way when moving docs.

Stay aligned with DESIGN-V1/V2 and the existing docs before making changes.
