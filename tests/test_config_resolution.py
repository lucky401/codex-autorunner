from pathlib import Path

import yaml

from codex_autorunner.bootstrap import write_repo_config
from codex_autorunner.core.config import CONFIG_FILENAME, load_config


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_load_config_prefers_repo_over_root_overrides(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_yaml(repo_root / "codex-autorunner.yml", {"server": {"port": 5000}})
    _write_yaml(repo_root / "codex-autorunner.override.yml", {"server": {"port": 6000}})

    config_dir = repo_root / ".codex-autorunner"
    config_dir.mkdir()
    _write_yaml(
        config_dir / "config.yml",
        {"mode": "repo", "server": {"port": 7000}},
    )

    config = load_config(repo_root)
    assert config.server_port == 7000


def test_load_config_uses_root_override_when_repo_missing(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_yaml(repo_root / "codex-autorunner.yml", {"server": {"port": 5000}})
    _write_yaml(repo_root / "codex-autorunner.override.yml", {"server": {"port": 6000}})

    config_dir = repo_root / ".codex-autorunner"
    config_dir.mkdir()
    _write_yaml(config_dir / "config.yml", {"mode": "repo"})

    config = load_config(repo_root)
    assert config.server_port == 6000


def test_write_repo_config_includes_root_overrides(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_yaml(repo_root / "codex-autorunner.yml", {"server": {"port": 5000}})
    _write_yaml(repo_root / "codex-autorunner.override.yml", {"server": {"port": 6000}})

    config_path = write_repo_config(repo_root, force=True)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config_path == repo_root / CONFIG_FILENAME
    assert data["server"]["port"] == 6000
