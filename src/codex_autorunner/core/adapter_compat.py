"""
Temporary compatibility module for core/engine.py.

This module provides backward-compatible access to adapter implementations
while documenting the path forward: core should use AgentBackend/RunEvent interfaces
instead of directly importing adapter implementations.

TODO: Refactor Engine to use AgentBackend interface directly.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, MutableMapping, Optional, Sequence

# Direct imports for runtime use - TODO: Remove these and use AgentBackend interface
from ...agents.opencode.logging import OpenCodeEventFormatter
from ...agents.opencode.runtime import (
    OpenCodeTurnOutput,
    build_turn_id,
    collect_opencode_output,
    extract_session_id,
    map_approval_policy_to_permission,
    opencode_missing_env,
    parse_message_response,
    split_model_id,
)
from ...agents.opencode.supervisor import (
    OpenCodeSupervisor,
    OpenCodeSupervisorError,
)
from ...agents.registry import validate_agent_id
from ...integrations.app_server.client import (
    CodexAppServerError,
    _extract_thread_id,
    _extract_thread_id_for_turn,
    _extract_turn_id,
)
from ...integrations.app_server.env import build_app_server_env
from ...integrations.app_server.supervisor import WorkspaceAppServerSupervisor

# Re-export from utils for backward compatibility
from .utils import build_opencode_supervisor

EnvBuilder = Callable[[Path, str, Path], Dict[str, str]]

_logger = logging.getLogger(__name__)

__all__ = [
    "OpenCodeEventFormatter",
    "OpenCodeTurnOutput",
    "build_turn_id",
    "collect_opencode_output",
    "extract_session_id",
    "map_approval_policy_to_permission",
    "opencode_missing_env",
    "parse_message_response",
    "split_model_id",
    "OpenCodeSupervisor",
    "OpenCodeSupervisorError",
    "validate_agent_id",
    "CodexAppServerError",
    "_extract_thread_id",
    "_extract_thread_id_for_turn",
    "_extract_turn_id",
    "build_app_server_env",
    "WorkspaceAppServerSupervisor",
    "build_opencode_supervisor",
]
