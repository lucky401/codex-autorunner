import json
import os
import shutil
from pathlib import Path
from typing import Optional


class RepoNotFoundError(Exception):
    pass


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    raise RepoNotFoundError("Could not find .git directory in current or parent paths")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        f.write(content)
    tmp_path.replace(path)


def read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_executable(binary: str) -> bool:
    return shutil.which(binary) is not None


def default_editor() -> str:
    return os.environ.get("EDITOR") or "vi"
