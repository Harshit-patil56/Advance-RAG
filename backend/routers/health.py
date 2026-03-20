"""Health routers.

GET /api/v1/health       — PRD 5.7 (liveness)
GET /api/v1/health/deep  — PRD 5.8 (dependency connectivity checks)
"""

import logging
from datetime import datetime, timezone

import httpx
import google.generativeai as genai
from fastapi import APIRouter
from fastapi.responses import Response

from config import settings
from core.schemas import DeepHealthResponse, HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    """Liveness check (PRD 5.7). Always returns 200 while the process is alive."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )


@router.head("/health", status_code=200)
async def health_head() -> Response:
    """HEAD liveness check for uptime monitors. Returns 200 with empty body."""
    return Response(status_code=200)


@router.get("/health/deep", response_model=DeepHealthResponse)
async def health_deep():
    """Check connectivity to all 5 external dependencies (PRD 5.8).

    Each check is a lightweight ping. All results are reported even if some fail.
    HTTP status is always 200 — report all, do not mask failures (PRD 5.8).
    """
    results: dict[str, str] = {
        "supabase": "error",
        "qdrant": "error",
        "huggingface": "error",
        "gemini": "error",
        "groq": "error",
    }

    # Supabase — attempt a trivial DB query
    try:
        from core.database import get_client
        client = get_client()
        client.table("chat_sessions").select("session_id").limit(1).execute()
        results["supabase"] = "ok"
    except Exception as exc:
        logger.warning("Deep health: Supabase check failed: %s", exc)

    # Qdrant — check if the client can list collections
    try:
        from core.qdrant import get_client as get_qdrant
        qdrant = get_qdrant()
        await qdrant.get_collections()
        results["qdrant"] = "ok"
    except Exception as exc:
        logger.warning("Deep health: Qdrant check failed: %s", exc)

    # HuggingFace — lightweight GET to the model endpoint
    try:
        url = f"https://api-inference.huggingface.co/models/{settings.huggingface_model}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.huggingface_api_token}"},
            )
        if resp.status_code < 500:
            results["huggingface"] = "ok"
    except Exception as exc:
        logger.warning("Deep health: HuggingFace check failed: %s", exc)

    # Gemini — list models (lightweight introspection call)
    try:
        genai.configure(api_key=settings.gemini_api_key)
        # list_models is a synchronous generator; just call next() once
        models_gen = genai.list_models()
        next(models_gen)
        results["gemini"] = "ok"
    except Exception as exc:
        logger.warning("Deep health: Gemini check failed: %s", exc)

    # Groq — list models API
    try:
        from groq import AsyncGroq
        async with AsyncGroq(api_key=settings.groq_api_key) as groq_client:
            await groq_client.models.list()
        results["groq"] = "ok"
    except Exception as exc:
        logger.warning("Deep health: Groq check failed: %s", exc)

    return DeepHealthResponse(**results)
