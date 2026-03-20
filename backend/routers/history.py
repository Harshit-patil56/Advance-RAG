"""History and Memory routers.

GET /api/v1/sessions/{session_id}/history  — PRD 5.4
GET /api/v1/sessions/{session_id}/memory   — PRD 5.5
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from core import database
from core.schemas import HistoryResponse, MemoryResponse, MessageRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["history"])


@router.get(
    "/sessions/{session_id}/history",
    response_model=HistoryResponse,
)
async def get_history(
    session_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return paginated message history for a session (PRD 5.4).

    limit: 1–100 (default 20)
    offset: 0+ (default 0)
    """
    sid = str(session_id)
    await database.get_session(sid)  # raises SessionNotFoundError if missing

    messages, total = await database.get_messages_paginated(sid, limit, offset)

    records = [
        MessageRecord(
            message_id=msg["message_id"],
            role=msg["role"],
            content=msg["content"],
            created_at=msg["created_at"],
            llm_provider=msg.get("llm_provider"),
            retrieval_score_avg=msg.get("retrieval_score_avg"),
            latency_ms=msg.get("latency_ms"),
        )
        for msg in messages
    ]

    return HistoryResponse(
        session_id=session_id,
        messages=records,
        total=total,
    )


@router.get(
    "/sessions/{session_id}/memory",
    response_model=MemoryResponse,
)
async def get_memory(session_id: UUID):
    """Return the memory summary for a session (PRD 5.5).

    Returns 404 if no summary has been generated yet.
    """
    sid = str(session_id)
    await database.get_session(sid)

    summary = await database.get_memory_summary(sid)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "No memory summary generated yet for this session.",
                "error_code": "MEMORY_NOT_FOUND",
                "details": {"session_id": sid},
            },
        )

    return MemoryResponse(
        session_id=session_id,
        summary_text=summary["summary_text"],
        message_count_at_summary=summary["message_count_at_summary"],
        updated_at=summary["updated_at"],
    )
