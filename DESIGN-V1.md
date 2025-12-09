Codex Autorunner – Product-Oriented Design (V1 CLI, V2 Web UI)

This document specifies a practical, extensible design for a Codex-based autorunner that can be instantiated in any git repo (or used to bootstrap a new one). It is written to be implementable by another AI or engineer with minimal additional guidance.

It assumes Codex is only accessible via the Codex CLI (codex --yolo exec --sandbox danger-full-access) and that Codex’s sandbox/harness is not available through an SDK. It also incorporates and refines the earlier loop design that runs Codex against three markdown docs and recycles previous run output as context.

1. Goals and Non-goals
1.1 Goals

Run Codex autonomously in a loop within any git repo to execute a prioritized backlog.

Use human-editable markdown docs as the primary control surface:

TODO.md – ordered checklist of tasks.

PROGRESS.md – running log, handoff notes.

OPINIONS.md – design opinions, constraints, policies.

V1: Provide a robust CLI tool that:

Initializes a repo for use with Codex Autorunner.

Runs the autorun loop.

Exposes basic inspection and editing helpers.

V2: Add a local web UI (desktop and mobile friendly) to:

View and edit the three docs ergonomically.

Start/stop the autorunner.

View logs.

Chat with Codex anchored in the repo context.

1.2 Non-goals (for now)

No cloud backend or hosted multi-user service.

No multi-repo or distributed orchestration.

No direct API/SDK integration with Codex harness (CLI only).

No complex plugin framework or tool marketplace.

2. High-level Architecture

Single-process, repo-local tool with three main layers:

Core Engine

Pure logic for:

Reading/writing docs.

Building Codex prompts.

Running the Codex CLI process.

Logging and extracting previous output.

Looping with basic backoff/stop conditions.

No UI assumptions.

CLI Interface (V1)

Thin wrapper over the engine.

Commands: init, run, once, status, log, edit, doctor.

Web Server + Web UI (V2)

codex-autorunner serve starts:

An HTTP API (FastAPI/Flask).

A background runner manager using the same engine as the CLI.

A static web UI (SPA or simple HTML+JS) that talks to the HTTP API.

Everything operates within a single git repo at a time. The “active repo” is the repo root (detected from CWD or an explicit --repo flag).

3. On-disk Layout and State

All persistent state lives inside the repo. Default layout:

<repo-root>/
  TODO.md
  PROGRESS.md
  OPINIONS.md
  .codex-autorunner/
    config.yml
    state.json
    codex-autorunner.log
    lock         # optional lock file
    prompt.txt   # optional custom prompt template

3.1 Markdown Docs

TODO.md

Markdown list with checkbox items:

- [ ] Migrate auth module to new library
- [x] Remove deprecated endpoints


“Outstanding” tasks are lines with - [ ].

Ordering is significant: Codex should work from top to bottom.

PROGRESS.md

Freeform markdown log of what Codex (or humans) did:

Summaries of completed tasks.

Tests executed.

Hand-off notes.

OPINIONS.md

Markdown text capturing:

Architectural preferences.

Policy decisions.

Constraints (e.g., “no new runtime dependencies”, “prefer pure functions,” etc.).

3.2 Config: .codex-autorunner/config.yml

Minimal YAML configuration with versioning:

version: 1

docs:
  todo: "TODO.md"
  progress: "PROGRESS.md"
  opinions: "OPINIONS.md"

codex:
  binary: "codex"
  args: ["--yolo", "exec", "--sandbox", "danger-full-access"]

prompt:
  prev_run_max_chars: 6000
  template: ".codex-autorunner/prompt.txt"  # optional; default built-in

runner:
  sleep_seconds: 5
  stop_after_runs: null     # null => unlimited
  max_wallclock_seconds: null

git:
  auto_commit: false
  commit_message_template: "[codex] run #{run_id}"


Best practices:

Strictly validate config on startup (doctor and run should fail fast).

Preserve unknown fields for forward compatibility.

3.3 State: .codex-autorunner/state.json

Small JSON file reflecting current/last run:

{
  "last_run_id": 12,
  "status": "idle",     // "idle" | "running" | "error"
  "last_exit_code": 0,
  "last_run_started_at": "2025-01-01T12:34:56Z",
  "last_run_finished_at": "2025-01-01T12:35:30Z"
}


Update atomically after each run.

3.4 Log: .codex-autorunner/codex-autorunner.log

Single append-only log for all runs:

Wrap each run with markers:

=== run 12 start ===
[2025-01-01T12:34:56Z] run=12 Codex CLI started...
[2025-01-01T12:35:01Z] run=12 stdout: ...
...
=== run 12 end (code 0) ===


Use timestamps and run ids on every line.

The engine extracts previous-run output from this log for context.

4. Core Engine Design

The core engine is a library used by both CLI and web server.

4.1 Key Responsibilities

Parse config and state.

Detect whether there are outstanding TODO items.

Build a full Codex prompt using:

Docs (TODO, PROGRESS, OPINIONS).

Optional previous run output.

A stable instructions block.

Run Codex CLI as a subprocess with streaming output.

Append logs with run markers.

Update state.json and optional git commit.

Implement the main autorun loop with backoff and termination rules.

4.2 Locking (Single-instance Safety)

To avoid two autorunners running on the same repo:

Use .codex-autorunner/lock:

On startup, if lock exists:

Read PID.

If process still alive, refuse to start unless a --force flag is used.

If not alive, remove stale lock.

When starting a run loop, write current PID to lock.

On clean exit, remove lock.

This prevents concurrent loops from interfering with each other.

4.3 TODO Parsing

Implement a small parser:

Read configured TODO.md.

For each line, if it matches:

- [ ] <text> → outstanding.

- [x] <text> or - [X] <text> → done.

todos_done() returns True iff there are zero - [ ] items.

4.4 Prompt Construction

The engine constructs a prompt string for Codex. Suggested default structure:

You are Codex, an autonomous coding assistant operating on a git repository.

You are given three documents:
1) TODO: an ordered checklist of tasks.
2) PROGRESS: a running log of what has been done and how it was validated.
3) OPINIONS: design constraints, architectural preferences, and migration policies.

You must:
- Work through TODO items from top to bottom.
- Prefer fixing issues over just documenting them.
- Keep TODO, PROGRESS, and OPINIONS in sync.
- Leave clear handoff notes (tests run, files touched, expected diffs).

<TODO>
... contents of TODO.md ...
</TODO>

<PROGRESS>
... contents of PROGRESS.md ...
</PROGRESS>

<OPINIONS>
... contents of OPINIONS.md ...
</OPINIONS>

[Optional previous run output section]

<PREV_RUN_OUTPUT>
... clipped text of previous run ...
</PREV_RUN_OUTPUT>

Instructions:
1) Select the highest priority unchecked TODO item and try to make concrete progress on it.
2) Make actual edits in the repo as needed.
3) Update TODO/PROGRESS/OPINIONS before finishing.
4) Prefer small, safe, self-contained changes with tests where applicable.
5) When you are done for this run, print a concise summary of what changed and what remains.


If .codex-autorunner/prompt.txt exists, load it as a template and interpolate markers like {{TODO}}, {{PROGRESS}}, {{OPINIONS}}, {{PREV_RUN_OUTPUT}}.

4.5 Previous Run Output Extraction

From codex-autorunner.log:

Find the block for run_id - 1:

Start: === run {id} start ===

End: === run {id} end

Extract text between those markers.

Optionally strip timestamps and metadata, or keep them if useful.

Truncate to last prev_run_max_chars characters from config.

If block not found, omit previous output.

4.6 Codex CLI Execution

The engine runs Codex via subprocess.Popen:

Build command:

cmd = [config.codex.binary] + config.codex.args + [prompt_string]


Example:

codex --yolo exec --sandbox danger-full-access "<prompt>"


Use:

stdout=PIPE, stderr=STDOUT.

Line-buffered reading (for line in proc.stdout).

For each output line:

Prefix with timestamp and run_id.

Append to codex-autorunner.log.

Optionally forward to live stream subscribers (web UI).

On process completion:

Capture exit_code = proc.returncode.

Log the end marker with exit code.

Return exit_code.

4.7 Main Loop Algorithm

Pseudo-code for the core loop:

def run_loop(repo_root, config):
    state = load_state()
    run_id = (state.last_run_id or 0) + 1
    start_wallclock = now()

    while True:
        if config.runner.max_wallclock_seconds is not None:
            if (now() - start_wallclock).total_seconds() > config.runner.max_wallclock_seconds:
                update_state(status="idle", last_run_id=run_id - 1)
                break

        if todos_done():
            update_state(status="idle", last_run_id=run_id - 1)
            break

        prev_output = extract_run_output(run_id - 1)
        prompt = build_prompt(prev_output=prev_output, prev_id=run_id - 1)

        update_state(
            status="running",
            last_run_id=run_id,
            last_run_started_at=now(),
        )

        exit_code = run_codex_cli(prompt, run_id)

        update_state(
            status="error" if exit_code != 0 else "idle",
            last_exit_code=exit_code,
            last_run_id=run_id,
            last_run_finished_at=now(),
        )

        if config.git.auto_commit and exit_code == 0:
            maybe_git_commit(run_id)

        if exit_code != 0:
            break

        if config.runner.stop_after_runs is not None:
            if run_id >= config.runner.stop_after_runs:
                break

        run_id += 1
        sleep(config.runner.sleep_seconds)

4.8 Git Integration (Optional)

If enabled:

After a successful run:

git add configured doc files (and optionally Codex-modified files).

git commit -m commit_message_template, with #{run_id} substituted.

This is optional and off by default to avoid surprising changes.

4.9 Error Handling

Fail fast if:

Config is invalid.

Codex binary is missing.

Docs are missing (unless init is running).

Stop loop on any non-zero Codex exit code.

Set status="error" in state and leave a clear entry in the log.

5. CLI Interface (V1)

Use a library like Typer or Click. All commands accept an optional --repo PATH argument; default is current working directory with auto-detection of git root.

5.1 codex-autorunner init [PATH]

Behavior:

Determine repo root:

If PATH is provided, use that; else use CWD.

If no .git exists, optionally git init (with --git-init flag).

Create default docs if missing:

TODO.md with a sample checklist.

PROGRESS.md with an empty or sample header.

OPINIONS.md with some starter guidance.

Create .codex-autorunner/ directory.

Write default config.yml if missing.

Initialize state.json if missing.

Create empty codex-autorunner.log if missing.

Do not overwrite existing files unless --force is provided.

5.2 codex-autorunner run

Behavior:

Acquire lock (fail if another instance is active).

Run the main loop until:

No outstanding TODO items.

Codex exits with non-zero.

stop_after_runs reached.

max_wallclock_seconds reached.

Stream logs to stdout.

On exit, print summary:

Last run id, last exit code, status.

5.3 codex-autorunner once

Same as run but only executes a single Codex run:

stop_after_runs=1 semantics regardless of config.

5.4 codex-autorunner status

Behavior:

Read state.json and print:

Status, last run id, last exit code, last start/finish timestamps.

Optionally show a short message about outstanding TODO count.

5.5 codex-autorunner log [--run N] [--tail N]

Behavior:

If --run is provided:

Extract only that run’s block from the log.

Else:

If --tail is provided, show last N lines.

If not, show last run’s block.

5.6 codex-autorunner edit [todo|progress|opinions]

Behavior:

Resolve file path from config.

Open in $EDITOR (fallback vi).

Useful for quick adjustments without leaving terminal.

5.7 codex-autorunner doctor

Behavior:

Validate:

Repo root and .git.

Existence and readability of docs and config.

Codex binary presence and version (run codex --version).

Config schema correctness.

Print actionable diagnostics; exit non-zero on failure.