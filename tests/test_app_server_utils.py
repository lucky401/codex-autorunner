import os
from pathlib import Path

from codex_autorunner.core.app_server_utils import app_server_env, build_app_server_env


def _path_entries(value: str) -> list[str]:
    return [entry for entry in value.split(os.pathsep) if entry]


def test_build_app_server_env_prepends_workspace_shim_without_git_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    shim_dir = workspace / ".codex-autorunner" / "bin"
    shim_dir.mkdir(parents=True)
    state_dir = tmp_path / "state"

    env = build_app_server_env(
        ["/bin/sh", "-c", "true"],
        workspace,
        state_dir,
        base_env={"PATH": "/usr/bin"},
    )

    entries = _path_entries(env["PATH"])
    assert entries[0] == str(shim_dir)
    assert env["CODEX_HOME"] == str(state_dir / "codex_home")


def test_app_server_env_includes_workspace_root_only_when_root_car_exists(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    env_without_root_car = app_server_env(
        ["/bin/sh", "-c", "true"],
        workspace,
        base_env={"PATH": "/usr/bin"},
    )
    entries_without_root_car = _path_entries(env_without_root_car["PATH"])
    assert str(workspace) not in entries_without_root_car

    (workspace / "car").write_text("#!/bin/sh\n", encoding="utf-8")
    env_with_root_car = app_server_env(
        ["/bin/sh", "-c", "true"],
        workspace,
        base_env={"PATH": "/usr/bin"},
    )
    entries_with_root_car = _path_entries(env_with_root_car["PATH"])
    assert str(workspace) in entries_with_root_car
    assert entries_with_root_car.index(str(workspace)) < entries_with_root_car.index(
        "/usr/bin"
    )


def test_app_server_env_workspace_shim_precedes_global_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    shim_dir = workspace / ".codex-autorunner" / "bin"
    shim_dir.mkdir(parents=True)
    global_dir = tmp_path / "global-bin"
    global_dir.mkdir()

    env = app_server_env(
        ["/bin/sh", "-c", "true"],
        workspace,
        base_env={"PATH": f"{global_dir}{os.pathsep}/usr/bin"},
    )
    entries = _path_entries(env["PATH"])
    assert str(shim_dir) in entries
    assert str(global_dir) in entries
    assert entries.index(str(shim_dir)) < entries.index(str(global_dir))
