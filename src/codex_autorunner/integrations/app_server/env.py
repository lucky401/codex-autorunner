from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

from ...core.app_server_utils import build_app_server_env as _build_app_server_env


def build_app_server_env(
    command: Sequence[str],
    workspace_root: Path,
    state_dir: Path,
    *,
    logger: Any = None,
    event_prefix: str = "app_server",
    base_env: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Build app-server env with workspace-local CAR shim precedence in PATH."""
    return _build_app_server_env(
        command,
        workspace_root,
        state_dir,
        logger=logger,
        event_prefix=event_prefix,
        base_env=base_env,
    )


__all__ = ["build_app_server_env"]
