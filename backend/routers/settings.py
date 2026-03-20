"""Runtime settings router.

Exposes LLM controls for frontend Settings modal.
"""

from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException

from core.runtime_llm_settings import (
    get_runtime_llm_settings,
    update_runtime_llm_settings,
)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("/llm")
async def get_llm_settings() -> dict[str, Any]:
    """Return current runtime-editable LLM settings."""
    return get_runtime_llm_settings()


@router.put("/llm")
async def put_llm_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace runtime-editable LLM settings."""
    try:
        return update_runtime_llm_settings(payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid settings payload: {exc}") from exc
