"""Folder and exploration retrieval routers.

Implements folder CRUD plus Claude-code-style exploration tools backed by DB queries.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from core import database

router = APIRouter(prefix="/api/v1", tags=["folders", "exploration"])


class CreateFolderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    user_id: str = Field(..., min_length=1)
    parent_id: UUID | None = None


class UpdateFolderRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None


class ShareFolderRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


@router.post("/folders")
async def create_folder(body: CreateFolderRequest) -> dict[str, Any]:
    return await database.create_folder(
        name=body.name,
        user_id=body.user_id,
        parent_id=str(body.parent_id) if body.parent_id else None,
    )


@router.get("/folders")
async def list_folders(
    user_id: str = Query(..., min_length=1),
    parent_id: UUID | None = None,
) -> list[dict[str, Any]]:
    return await database.list_folders(
        user_id=user_id,
        parent_id=str(parent_id) if parent_id else None,
    )


@router.get("/folders/{folder_id}")
async def get_folder(folder_id: UUID) -> dict[str, Any]:
    return await database.get_folder(str(folder_id))


@router.patch("/folders/{folder_id}")
async def update_folder(folder_id: UUID, body: UpdateFolderRequest) -> dict[str, Any]:
    return await database.update_folder(
        folder_id=str(folder_id),
        user_id=body.user_id,
        name=body.name,
        parent_id=str(body.parent_id) if body.parent_id else None,
    )


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: UUID,
    user_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    await database.delete_folder(str(folder_id), user_id=user_id)
    return {"deleted": True, "folder_id": str(folder_id)}


@router.post("/folders/{folder_id}/share")
async def share_folder(folder_id: UUID, body: ShareFolderRequest) -> dict[str, Any]:
    folder = await database.set_folder_global_state(
        folder_id=str(folder_id),
        user_id=body.user_id,
        make_global=True,
    )
    return {"folder": folder, "shared": True}


@router.post("/folders/{folder_id}/private")
async def make_folder_private(folder_id: UUID, body: ShareFolderRequest) -> dict[str, Any]:
    folder = await database.set_folder_global_state(
        folder_id=str(folder_id),
        user_id=body.user_id,
        make_global=False,
    )
    return {"folder": folder, "shared": False}


@router.get("/tools/ls")
async def tool_ls(
    user_id: str = Query(..., min_length=1),
    folder_id: UUID | None = None,
) -> dict[str, Any]:
    folders = await database.list_folders(
        user_id=user_id,
        parent_id=str(folder_id) if folder_id else None,
    )
    files = await database.list_files_in_folder(
        folder_id=str(folder_id) if folder_id else None,
        user_id=user_id,
    )
    return {
        "folder_id": str(folder_id) if folder_id else None,
        "folders": [{"folder_id": f["folder_id"], "name": f["name"]} for f in folders],
        "files": [{"file_id": f["file_id"], "filename": f["filename"]} for f in files],
    }


@router.get("/tools/tree")
async def tool_tree(
    user_id: str = Query(..., min_length=1),
    root_folder_id: UUID | None = None,
    max_depth: int = Query(default=6, ge=1, le=20),
    max_items: int = Query(default=500, ge=10, le=5000),
) -> dict[str, Any]:
    return await database.get_folder_tree(
        user_id=user_id,
        root_folder_id=str(root_folder_id) if root_folder_id else None,
        max_depth=max_depth,
        max_items=max_items,
    )


@router.get("/tools/glob")
async def tool_glob(
    user_id: str = Query(..., min_length=1),
    pattern: str = Query(..., min_length=1),
    folder_id: UUID | None = None,
) -> dict[str, Any]:
    matches = await database.glob_documents(
        pattern=pattern,
        user_id=user_id,
        folder_id=str(folder_id) if folder_id else None,
    )
    return {"pattern": pattern, "matches": matches}


@router.get("/tools/gp")
async def tool_gp(
    user_id: str = Query(..., min_length=1),
    pattern: str = Query(..., min_length=1),
    folder_id: UUID | None = None,
    is_regex: bool = False,
) -> dict[str, Any]:
    matches = await database.grep_documents(
        pattern=pattern,
        user_id=user_id,
        folder_id=str(folder_id) if folder_id else None,
        use_regex=is_regex,
    )
    return {"pattern": pattern, "is_regex": is_regex, "matches": matches}


@router.get("/tools/read")
async def tool_read(
    user_id: str = Query(..., min_length=1),
    file_id: UUID = Query(...),
    start_line: int | None = Query(default=None, ge=1),
    end_line: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    if (start_line is None) ^ (end_line is None):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="start_line and end_line must be provided together")
    return await database.read_document(
        file_id=str(file_id),
        user_id=user_id,
        start_line=start_line,
        end_line=end_line,
    )
