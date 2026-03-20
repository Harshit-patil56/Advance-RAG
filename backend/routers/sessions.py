"""Sessions router — POST /api/v1/sessions, DELETE /api/v1/sessions/{session_id}

PRD Sections 5.1, 5.6
"""

import logging
from uuid import UUID

from fastapi import APIRouter

from core import database, qdrant as qdrant_client
from core.exceptions import SessionNotFoundError
from core.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    DeleteSessionResponse,
    UpdateSessionRequest,
    UpdateSessionResponse,
)
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(body: CreateSessionRequest):
    """Create a new chat session for the given domain (PRD 5.1).

    Domain validation is enforced by the Pydantic model.
    Returns HTTP 201 with session_id, domain, created_at.
    """
    row = await database.create_session(body.domain, body.user_id)
    return CreateSessionResponse(
        session_id=row["session_id"],
        domain=row["domain"],
        session_name=row.get("session_name"),
        created_at=row["created_at"],
    )


@router.patch("/sessions/{session_id}", response_model=UpdateSessionResponse)
async def rename_session(session_id: UUID, body: UpdateSessionRequest):
    """Rename a session for display in the sidebar."""
    sid = str(session_id)
    await database.get_session(sid)
    updated = await database.update_session_name(sid, body.session_name)
    return UpdateSessionResponse(
        session_id=session_id,
        session_name=updated["session_name"],
    )


@router.get("/sessions")
async def list_user_sessions(user_id: str):
    """Retrieve all active chat sessions belonging to the user."""
    from fastapi import HTTPException
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id query parameter is required")
    
    rows = await database.get_user_sessions(user_id)
    # Re-use CreateSessionResponse structurally or return plain dicts
    return {"sessions": rows}


@router.get("/sessions/{session_id}/files")
async def get_session_files(session_id: UUID):
    """Retrieve all files uploaded in a session."""
    sid = str(session_id)
    # Validate session exists
    await database.get_session(sid)
    return await database.get_session_files(sid)


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(session_id: UUID):
    """Soft-delete a session and remove its Qdrant points (PRD 5.6).

    Sets deleted_at on the session row. Deletes Qdrant points in finance,
    law, and global collections filtered by session_id.
    """
    sid = str(session_id)

    # Verify session exists before deleting
    await database.get_session(sid)

    # Soft-delete the session row
    await database.soft_delete_session(sid)

    # Delete Qdrant points in both collections (session may have used either domain)
    for collection in (
        settings.qdrant_finance_collection,
        settings.qdrant_law_collection,
        settings.qdrant_global_collection,
    ):
        try:
            await qdrant_client.delete_points_by_session(collection, sid)
        except Exception as exc:
            # Log but do not fail the delete response
            logger.error(
                "delete_points_by_session failed for collection '%s', session '%s': %s",
                collection, sid, exc,
            )

    return DeleteSessionResponse(session_id=session_id, deleted=True)
