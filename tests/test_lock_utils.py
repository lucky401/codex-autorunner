from pathlib import Path

from codex_autorunner.lock_utils import read_lock_info, write_lock_info


def test_read_lock_info_pid_text(tmp_path: Path) -> None:
    lock_path = tmp_path / "lock"
    lock_path.write_text("12345", encoding="utf-8")
    info = read_lock_info(lock_path)
    assert info.pid == 12345
    assert info.started_at is None


def test_write_lock_info_roundtrip(tmp_path: Path) -> None:
    lock_path = tmp_path / "lock"
    write_lock_info(lock_path, 999, started_at="2025-01-01T00:00:00Z")
    info = read_lock_info(lock_path)
    assert info.pid == 999
    assert info.started_at == "2025-01-01T00:00:00Z"
    assert info.host
