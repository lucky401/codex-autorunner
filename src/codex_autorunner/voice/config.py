from __future__ import annotations

import dataclasses
import os
from typing import Any, Dict, Mapping, MutableMapping, Optional

LatencyMode = str  # Alias to keep config typed without importing Literal everywhere


DEFAULT_PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "openai_whisper": {
        "api_key_env": "OPENAI_API_KEY",
        "model": "whisper-1",
        "base_url": None,
        "temperature": 0,
        "language": None,
        "redact_request": True,
    }
}


@dataclasses.dataclass
class PushToTalkConfig:
    max_ms: int = 15_000
    silence_auto_stop_ms: int = 1_200
    min_hold_ms: int = 150


@dataclasses.dataclass
class VoiceConfig:
    enabled: bool
    provider: Optional[str]
    latency_mode: LatencyMode
    chunk_ms: int
    sample_rate: int
    warn_on_remote_api: bool
    push_to_talk: PushToTalkConfig
    providers: Dict[str, Dict[str, Any]]

    @classmethod
    def from_raw(
        cls,
        raw: Optional[Mapping[str, Any]],
        env: Optional[Mapping[str, str]] = None,
    ) -> "VoiceConfig":
        """
        Build a normalized VoiceConfig from config.yml voice section and env overrides.
        This does not touch global config to keep voice optional until integrated.
        """
        env = env or os.environ
        merged: MutableMapping[str, Any] = {
            "enabled": False,
            "provider": "openai_whisper",
            "latency_mode": "balanced",
            "chunk_ms": 600,
            "sample_rate": 16_000,
            "warn_on_remote_api": True,
            "push_to_talk": {
                "max_ms": 15_000,
                "silence_auto_stop_ms": 1_200,
                "min_hold_ms": 150,
            },
            "providers": dict(DEFAULT_PROVIDER_CONFIG),
        }
        if isinstance(raw, Mapping):
            merged.update(raw)
            base_pt = merged.get("push_to_talk")
            pt_defaults = base_pt if isinstance(base_pt, Mapping) else {}
            pt_overrides = raw.get("push_to_talk") if isinstance(raw.get("push_to_talk"), Mapping) else {}
            merged["push_to_talk"] = {**pt_defaults, **pt_overrides}

            providers = merged.get("providers", {})
            merged["providers"] = dict(DEFAULT_PROVIDER_CONFIG)
            if isinstance(providers, Mapping):
                for key, value in providers.items():
                    if isinstance(value, Mapping):
                        merged["providers"][key] = {**merged["providers"].get(key, {}), **dict(value)}

        merged["enabled"] = _env_bool(env.get("CODEX_AUTORUNNER_VOICE_ENABLED"), merged["enabled"])
        merged["provider"] = env.get("CODEX_AUTORUNNER_VOICE_PROVIDER", merged.get("provider"))
        merged["latency_mode"] = env.get(
            "CODEX_AUTORUNNER_VOICE_LATENCY", merged.get("latency_mode", "balanced")
        )
        merged["chunk_ms"] = _env_int(env.get("CODEX_AUTORUNNER_VOICE_CHUNK_MS"), merged["chunk_ms"])
        merged["sample_rate"] = _env_int(
            env.get("CODEX_AUTORUNNER_VOICE_SAMPLE_RATE"), merged["sample_rate"]
        )
        merged["warn_on_remote_api"] = _env_bool(
            env.get("CODEX_AUTORUNNER_VOICE_WARN_REMOTE"),
            merged.get("warn_on_remote_api", True),
        )

        pt = merged.get("push_to_talk", {}) or {}
        push_to_talk = PushToTalkConfig(
            max_ms=_env_int(env.get("CODEX_AUTORUNNER_VOICE_MAX_MS"), pt.get("max_ms", 15_000)),
            silence_auto_stop_ms=_env_int(
                env.get("CODEX_AUTORUNNER_VOICE_SILENCE_MS"), pt.get("silence_auto_stop_ms", 1_200)
            ),
            min_hold_ms=_env_int(
                env.get("CODEX_AUTORUNNER_VOICE_MIN_HOLD_MS"), pt.get("min_hold_ms", 150)
            ),
        )

        providers = dict(merged.get("providers") or {})
        return cls(
            enabled=bool(merged.get("enabled")),
            provider=merged.get("provider"),
            latency_mode=str(merged.get("latency_mode", "balanced")),
            chunk_ms=int(merged.get("chunk_ms", 600)),
            sample_rate=int(merged.get("sample_rate", 16_000)),
            warn_on_remote_api=bool(merged.get("warn_on_remote_api", True)),
            push_to_talk=push_to_talk,
            providers=providers,
        )


def _env_bool(raw: Optional[str], default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(raw: Optional[str], default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default
