"""
Codex configuration and discovery routes.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from fastapi import APIRouter, HTTPException, Request

from ..codex_cli import (
    DEFAULT_MODELS,
    DEFAULT_REASONING_LEVELS,
    extract_flag_value,
    strip_flag,
)
from ..config import CONFIG_FILENAME, ConfigError, load_config
from ..utils import atomic_write


def _config_path(config_root: Path) -> Path:
    return config_root / CONFIG_FILENAME


def _read_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise HTTPException(status_code=404, detail="Config not found")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_config(path: Path, data: Dict[str, Any]) -> None:
    text = yaml.safe_dump(data, sort_keys=False)
    atomic_write(path, text)


def _normalize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed if trimmed else None


def build_codex_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/codex/options")
    def get_codex_options(request: Request):
        config = request.app.state.config
        raw_codex = (config.raw or {}).get("codex") or {}
        if not isinstance(raw_codex, dict):
            raw_codex = {}
        args = raw_codex.get("args") if isinstance(raw_codex.get("args"), list) else []
        current_model = raw_codex.get("model") or extract_flag_value(args, "--model")
        current_reasoning = raw_codex.get("reasoning") or extract_flag_value(
            args, "--reasoning"
        )

        models = list(DEFAULT_MODELS)
        if current_model and current_model not in models:
            models.append(current_model)
        reasoning = list(DEFAULT_REASONING_LEVELS)
        if current_reasoning and current_reasoning not in reasoning:
            reasoning.append(current_reasoning)

        return {
            "current_model": current_model,
            "current_reasoning": current_reasoning,
            "models": models,
            "reasoning_levels": reasoning,
            "discovery": {
                "models_source": "static",
                "models_error": None,
                "reasoning_source": "static",
                "reasoning_error": None,
            },
        }

    @router.put("/api/codex/options")
    def update_codex_options(request: Request, payload: Optional[dict] = None):
        payload = payload or {}
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        config = request.app.state.config
        config_path = _config_path(config.root)
        data = _read_config(config_path)

        codex = data.get("codex")
        if not isinstance(codex, dict):
            codex = {}
            data["codex"] = codex

        args = codex.get("args")
        if not isinstance(args, list):
            args = []
        args = strip_flag(args, "--model")
        args = strip_flag(args, "--reasoning")
        codex["args"] = args

        model = _normalize_optional(payload.get("model"))
        reasoning = _normalize_optional(payload.get("reasoning"))
        codex["model"] = model
        codex["reasoning"] = reasoning

        _write_config(config_path, data)

        try:
            new_config = load_config(config.root)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        request.app.state.config = new_config
        request.app.state.engine.config = new_config
        request.app.state.engine.docs.config = new_config

        return {
            "current_model": model,
            "current_reasoning": reasoning,
        }

    return router


__all__ = ["build_codex_routes"]
