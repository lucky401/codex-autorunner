from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

from codex_autorunner.core.ticket_manager_cli import MANAGER_REL_PATH


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    tool = repo / MANAGER_REL_PATH
    return subprocess.run(
        [sys.executable, str(tool), *args], cwd=repo, text=True, capture_output=True
    )


def test_tool_seeded_with_repo(repo: Path) -> None:
    tool = repo / MANAGER_REL_PATH
    assert tool.exists()
    assert tool.stat().st_mode & 0o111


def test_list_and_create_and_move(repo: Path) -> None:
    tickets = repo / ".codex-autorunner" / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)

    res = _run(repo, "create", "--title", "First", "--agent", "codex")
    assert res.returncode == 0

    res = _run(repo, "create", "--title", "Second", "--agent", "codex")
    assert res.returncode == 0

    res = _run(repo, "list")
    assert "First" in res.stdout and "Second" in res.stdout

    res = _run(repo, "insert", "--before", "1")
    assert res.returncode == 0

    res = _run(repo, "move", "--start", "2", "--to", "1")
    assert res.returncode == 0

    res = _run(repo, "lint")
    assert res.returncode == 0


def test_create_quotes_special_scalars(repo: Path) -> None:
    tickets = repo / ".codex-autorunner" / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)

    res = _run(repo, "create", "--title", "Fix #123: timing", "--agent", "qa:bot")
    assert res.returncode == 0

    ticket_path = tickets / "TICKET-001.md"
    content = ticket_path.read_text(encoding="utf-8")
    assert "Fix #123: timing" in content

    res = _run(repo, "lint")
    assert res.returncode == 0


def test_insert_requires_anchor(repo: Path) -> None:
    tickets = repo / ".codex-autorunner" / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)
    res = _run(repo, "insert")
    assert res.returncode != 0


def test_insert_with_title_creates_ticket(repo: Path) -> None:
    tickets = repo / ".codex-autorunner" / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)

    _run(repo, "create", "--title", "First", "--agent", "codex")
    _run(repo, "create", "--title", "Second", "--agent", "codex")

    res = _run(repo, "insert", "--before", "1", "--title", "Inserted", "--agent", "bot")
    assert res.returncode == 0
    assert "Inserted gap and created" in res.stdout

    ticket_paths = sorted(
        p.name for p in tickets.iterdir() if p.name.startswith("TICKET-")
    )
    assert ticket_paths == ["TICKET-001.md", "TICKET-002.md", "TICKET-003.md"]

    content = (tickets / "TICKET-001.md").read_text(encoding="utf-8")
    assert "Inserted" in content
    assert 'agent: "bot"' in content


def test_insert_without_title_warns_next_step(repo: Path) -> None:
    tickets = repo / ".codex-autorunner" / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)

    _run(repo, "create", "--title", "Only", "--agent", "codex")

    res = _run(repo, "insert", "--after", "1")
    assert res.returncode == 0
    assert "run create --at 2" in res.stdout

    ticket_paths = sorted(
        p.name for p in tickets.iterdir() if p.name.startswith("TICKET-")
    )
    assert ticket_paths == ["TICKET-001.md"]


def test_insert_rejects_title_with_count_gt_one(repo: Path) -> None:
    tickets = repo / ".codex-autorunner" / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)

    _run(repo, "create", "--title", "Only", "--agent", "codex")

    res = _run(repo, "insert", "--before", "1", "--count", "2", "--title", "Nope")
    assert res.returncode != 0
    assert "--title is only supported with --count 1" in res.stderr


def test_import_zip_normalizes_missing_frontmatter(repo: Path, tmp_path: Path) -> None:
    zip_path = tmp_path / "tickets.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TICKET-001.md", "## Goal\n- Import me\n")
        zf.writestr(
            "TICKET-002.md",
            "---\nagent: codex\ndone: false\ntitle: Existing\n---\n\nBody\n",
        )

    res = _run(repo, "import-zip", "--zip", str(zip_path))
    assert res.returncode == 0
    assert "Imported 2 ticket(s)" in res.stdout

    content = (repo / ".codex-autorunner" / "tickets" / "TICKET-001.md").read_text(
        encoding="utf-8"
    )
    assert 'agent: "codex"' in content
    assert "done: false" in content
    assert 'title: "TICKET-001"' in content

    lint = _run(repo, "lint")
    assert lint.returncode == 0


def test_import_zip_no_normalize_rejects_missing_frontmatter(
    repo: Path, tmp_path: Path
) -> None:
    zip_path = tmp_path / "tickets.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TICKET-001.md", "## Goal\n- Missing frontmatter\n")

    res = _run(repo, "import-zip", "--zip", str(zip_path), "--no-normalize")
    assert res.returncode != 0
    assert "Missing YAML frontmatter" in res.stderr
