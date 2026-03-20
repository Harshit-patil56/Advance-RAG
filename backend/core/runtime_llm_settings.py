"""Runtime-editable LLM settings.

These values are in-memory and apply immediately without process restart.
They are initialized from environment-backed config defaults.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from config import settings


LLMSettingsDict = dict[str, Any]


_LOCK = Lock()
_STATE: LLMSettingsDict = {
    "gemini_enabled": True,
    "groq_enabled": True,
    "gemini_model": settings.gemini_model,
    "groq_model": settings.groq_model,
    "gemini_temperature": 0.0,
    "groq_temperature": 0.0,
    "top_p": 0.8,
    "gemini_max_output_tokens": 2048,
    "groq_max_tokens": 2048,
    "llm_timeout_seconds": settings.llm_timeout_seconds,
}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError("must be boolean")


def _to_str(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be non-empty string")
    return value.strip()


def _to_float(value: Any, low: float, high: float) -> float:
    number = float(value)
    if number < low or number > high:
        raise ValueError(f"must be between {low} and {high}")
    return number


def _to_int(value: Any, low: int, high: int) -> int:
    number = int(value)
    if number < low or number > high:
        raise ValueError(f"must be between {low} and {high}")
    return number


def validate_llm_settings(payload: dict[str, Any]) -> LLMSettingsDict:
    """Validate and normalize full runtime LLM settings payload."""
    normalized: LLMSettingsDict = {
        "gemini_enabled": _to_bool(payload.get("gemini_enabled")),
        "groq_enabled": _to_bool(payload.get("groq_enabled")),
        "gemini_model": _to_str(payload.get("gemini_model")),
        "groq_model": _to_str(payload.get("groq_model")),
        "gemini_temperature": _to_float(payload.get("gemini_temperature"), 0.0, 2.0),
        "groq_temperature": _to_float(payload.get("groq_temperature"), 0.0, 2.0),
        "top_p": _to_float(payload.get("top_p"), 0.01, 1.0),
        "gemini_max_output_tokens": _to_int(payload.get("gemini_max_output_tokens"), 128, 8192),
        "groq_max_tokens": _to_int(payload.get("groq_max_tokens"), 128, 8192),
        "llm_timeout_seconds": _to_int(payload.get("llm_timeout_seconds"), 5, 120),
    }
    return normalized


def get_runtime_llm_settings() -> LLMSettingsDict:
    with _LOCK:
        return dict(_STATE)


def update_runtime_llm_settings(payload: dict[str, Any]) -> LLMSettingsDict:
    global _STATE
    normalized = validate_llm_settings(payload)
    with _LOCK:
        _STATE = normalized
        return dict(_STATE)
