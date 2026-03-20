"""Supabase client wrapper.

Provides typed functions for every database operation the application needs.
All operations raise DatabaseError on failure — no silent swallowing (PRD 13.3).

Uses the synchronous supabase-py Client which is the stable export in v2.5.x.
Functions remain async so the caller interface stays consistent.
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from supabase import create_client, Client

from config import settings
from core.exceptions import (
    DatabaseError,
    FileNotFoundError,
    FolderCycleError,
    FolderNotFoundError,
    FolderPermissionError,
    SessionNotFoundError,
)

logger = logging.getLogger(__name__)

_client: Client | None = None


def _strip_nul_chars(value: Any) -> Any:
    """Recursively remove NUL characters unsupported by Postgres text/json parsing."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [_strip_nul_chars(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_strip_nul_chars(v) for v in value)
    if isinstance(value, dict):
        return {k: _strip_nul_chars(v) for k, v in value.items()}
    return value


def _is_missing_column_error(exc: Exception, table: str, column: str) -> bool:
    """Return True when PostgREST reports a missing column in schema cache."""
    err = str(exc)
    return (
        "PGRST204" in err
        and f"'{column}'" in err
        and f"'{table}'" in err
        and "schema cache" in err
    )


def get_client() -> Client:
    """Return the shared Supabase client, creating it on first call."""
    global _client
    if _client is None:
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _client


# ---------------------------------------------------------------------------
# Session operations
# ---------------------------------------------------------------------------


async def create_session(domain: str, user_id: str | None) -> dict[str, Any]:
    """Insert a new row into chat_sessions and return it."""
    client = get_client()
    payload: dict[str, Any] = {"domain": domain}
    if user_id:
        payload["user_id"] = user_id
    try:
        response = client.table("chat_sessions").insert(payload).execute()
        return response.data[0]
    except Exception as exc:
        err = str(exc)
        if "chat_sessions_domain_check" in err or "violates check constraint" in err:
            raise DatabaseError(
                "create_session",
                "Database domain constraint is outdated for 'global'. Apply migration 004_allow_global_domain.sql.",
            ) from exc
        logger.error("create_session failed: %s", exc)
        raise DatabaseError("create_session", err) from exc


async def get_user_sessions(user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Fetch paginated chat sessions belonging to a specific user_id."""
    client = get_client()
    try:
        response = (
            client.table("chat_sessions")
            .select("*")
            .eq("user_id", user_id)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return response.data
    except Exception as exc:
        logger.error("get_user_sessions failed: %s", exc)
        raise DatabaseError("get_user_sessions", str(exc)) from exc


async def get_session(session_id: str | UUID) -> dict[str, Any]:
    """Fetch a session by ID. Raises SessionNotFoundError if absent or soft-deleted."""
    client = get_client()
    try:
        response = (
            client.table("chat_sessions")
            .select("*")
            .eq("session_id", str(session_id))
            .is_("deleted_at", "null")
            .single()
            .execute()
        )
    except Exception as exc:
        err_str = str(exc)
        if "PGRST116" in err_str or "No rows" in err_str:
            raise SessionNotFoundError(str(session_id)) from exc
        logger.error("get_session failed: %s", exc)
        raise DatabaseError("get_session", err_str) from exc

    # .single() returns a dict directly in response.data, not a list.
    # It raises PGRST116 if no rows found, so response.data should never be None here.
    if not response.data:
        raise SessionNotFoundError(str(session_id))
    # response.data is already a dict when using .single()
    return response.data if isinstance(response.data, dict) else response.data[0]


async def soft_delete_session(session_id: str | UUID) -> None:
    """Set deleted_at on chat_sessions row (soft delete — PRD 5.6)."""
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
    try:
        client.table("chat_sessions").update({"deleted_at": now}).eq(
            "session_id", str(session_id)
        ).execute()
    except Exception as exc:
        logger.error("soft_delete_session failed: %s", exc)
        raise DatabaseError("soft_delete_session", str(exc)) from exc


async def update_session_name(session_id: str | UUID, session_name: str) -> dict[str, Any]:
    """Update a session display name and return updated row."""
    client = get_client()
    try:
        client.table("chat_sessions").update({"session_name": session_name.strip()}).eq(
            "session_id", str(session_id)
        ).execute()

        response = (
            client.table("chat_sessions")
            .select("session_id,session_name")
            .eq("session_id", str(session_id))
            .single()
            .execute()
        )

        if not response.data:
            raise SessionNotFoundError(str(session_id))
        return response.data
    except Exception as exc:
        err = str(exc)
        if "PGRST116" in err or "No rows" in err:
            raise SessionNotFoundError(str(session_id)) from exc
        if _is_missing_column_error(exc, "chat_sessions", "session_name"):
            raise DatabaseError(
                "update_session_name",
                "chat_sessions.session_name not visible in PostgREST schema cache. "
                "Apply migration 003 on the active database and run: NOTIFY pgrst, 'reload schema';",
            ) from exc
        logger.error("update_session_name failed: %s", exc)
        raise DatabaseError("update_session_name", err) from exc


# ---------------------------------------------------------------------------
# Uploaded files operations
# ---------------------------------------------------------------------------


async def insert_uploaded_file(
    session_id: str | UUID,
    domain: str,
    filename: str,
    storage_path: str,
    file_size_bytes: int,
    folder_id: str | UUID | None = None,
) -> dict[str, Any]:
    """Insert file metadata with status='pending'."""
    client = get_client()
    payload = {
        "session_id": str(session_id),
        "domain": domain,
        "filename": filename,
        "storage_path": storage_path,
        "file_size_bytes": file_size_bytes,
        "status": "pending",
    }
    if folder_id is not None:
        payload["folder_id"] = str(folder_id)
    try:
        response = client.table("uploaded_files").insert(payload).execute()
        return response.data[0]
    except Exception as exc:
        logger.error("insert_uploaded_file failed: %s", exc)
        raise DatabaseError("insert_uploaded_file", str(exc)) from exc


async def update_file_status(
    file_id: str | UUID,
    status: str,
    chunk_count: int | None = None,
    error_message: str | None = None,
    chart_data: dict[str, Any] | None = None,
    full_markdown: str | None = None,
) -> None:
    """Update an uploaded_files row after ingestion succeeds or fails."""
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {"status": status}
    if status == "indexed":
        payload["indexed_at"] = now
    if chunk_count is not None:
        payload["chunk_count"] = chunk_count
    if error_message is not None:
        payload["error_message"] = error_message
    if chart_data is not None:
        payload["chart_data"] = chart_data
    if full_markdown is not None:
        payload["full_markdown"] = full_markdown

    payload = _strip_nul_chars(payload)
    try:
        client.table("uploaded_files").update(payload).eq(
            "file_id", str(file_id)
        ).execute()
    except Exception as exc:
        # Backward-compatibility: if migration adding full_markdown was not applied,
        # persist remaining status fields so ingestion does not fail.
        if "full_markdown" in payload and _is_missing_column_error(exc, "uploaded_files", "full_markdown"):
            logger.warning(
                "update_file_status: uploaded_files.full_markdown missing in schema; retrying without full_markdown"
            )
            payload_without_markdown = dict(payload)
            payload_without_markdown.pop("full_markdown", None)
            try:
                client.table("uploaded_files").update(payload_without_markdown).eq(
                    "file_id", str(file_id)
                ).execute()
                return
            except Exception as retry_exc:
                logger.error("update_file_status retry failed: %s", retry_exc)
                raise DatabaseError("update_file_status", str(retry_exc)) from retry_exc

        logger.error("update_file_status failed: %s", exc)
        raise DatabaseError("update_file_status", str(exc)) from exc


async def get_file_chart_data(file_id: str | UUID) -> dict[str, Any] | None:
    """Fetch chart_data JSONB for a given file. Returns None if column is null."""
    client = get_client()
    try:
        response = (
            client.table("uploaded_files")
            .select("chart_data")
            .eq("file_id", str(file_id))
            .single()
            .execute()
        )
        return response.data.get("chart_data") if response.data else None
    except Exception as exc:
        logger.error("get_file_chart_data failed: %s", exc)
        raise DatabaseError("get_file_chart_data", str(exc)) from exc


async def get_session_files(session_id: str) -> list[dict]:
    """Retrieve all uploaded files tracking records for a specific session."""
    client = get_client()
    try:
        response = (
            client.table("uploaded_files")
            .select("file_id, filename, domain, chunk_count, status, folder_id")
            .eq("session_id", session_id)
            .execute()
        )
        return response.data
    except Exception as exc:
        logger.error("get_session_files failed: %s", exc)
        raise DatabaseError("get_session_files", str(exc)) from exc


async def get_file(file_id: str | UUID) -> dict[str, Any] | None:
    """Fetch file metadata by ID."""
    client = get_client()
    try:
        response = (
            client.table("uploaded_files")
            .select("*")
            .eq("file_id", str(file_id))
            .single()
            .execute()
        )
        return response.data
    except Exception as exc:
        logger.error("get_file failed: %s", exc)
        return None


async def delete_file(file_id: str | UUID) -> None:
    """Delete a file record from DB and its bytes from Storage."""
    client = get_client()
    
    # 1. Get the storage_path so we can delete the physical bytes
    file_record = await get_file(file_id)
    
    # 2. Delete the DB record (this should generally happen even if storage delete fails)
    try:
        client.table("uploaded_files").delete().eq("file_id", str(file_id)).execute()
    except Exception as exc:
        logger.error("delete_file database record failed: %s", exc)
        raise DatabaseError("delete_file", str(exc)) from exc

    # 3. Delete from Supabase Storage
    if file_record and "storage_path" in file_record:
        try:
            from config import settings
            client.storage.from_(settings.storage_bucket).remove([file_record["storage_path"]])
        except Exception as exc:
            logger.warning("delete_file storage removal failed: %s", exc)


# ---------------------------------------------------------------------------
# Folder and exploration operations
# ---------------------------------------------------------------------------


def _is_folder_visible(folder: dict[str, Any], user_id: str) -> bool:
    owner = folder.get("user_id")
    return owner is None or owner == user_id


async def create_folder(
    name: str,
    user_id: str,
    parent_id: str | UUID | None = None,
) -> dict[str, Any]:
    """Create a folder owned by user_id under optional parent_id."""
    client = get_client()
    if parent_id:
        parent = await get_folder(str(parent_id))
        if not _is_folder_visible(parent, user_id):
            raise FolderPermissionError("create subfolder")

    payload: dict[str, Any] = {
        "name": name,
        "user_id": user_id,
    }
    if parent_id:
        payload["parent_id"] = str(parent_id)

    try:
        response = client.table("folders").insert(payload).execute()
        return response.data[0]
    except Exception as exc:
        logger.error("create_folder failed: %s", exc)
        raise DatabaseError("create_folder", str(exc)) from exc


async def get_folder(folder_id: str | UUID) -> dict[str, Any]:
    """Fetch a folder row by ID."""
    client = get_client()
    try:
        response = (
            client.table("folders")
            .select("*")
            .eq("folder_id", str(folder_id))
            .single()
            .execute()
        )
    except Exception as exc:
        err = str(exc)
        if "PGRST116" in err or "No rows" in err:
            raise FolderNotFoundError(str(folder_id)) from exc
        logger.error("get_folder failed: %s", exc)
        raise DatabaseError("get_folder", err) from exc

    if not response.data:
        raise FolderNotFoundError(str(folder_id))
    return response.data


async def list_folders(
    user_id: str,
    parent_id: str | UUID | None = None,
) -> list[dict[str, Any]]:
    """List folders at one level for a user including global folders."""
    client = get_client()
    try:
        query = (
            client.table("folders")
            .select("*")
            .or_(f"user_id.eq.{user_id},user_id.is.null")
            .order("name")
        )
        if parent_id is None:
            query = query.is_("parent_id", "null")
        else:
            query = query.eq("parent_id", str(parent_id))

        response = query.execute()
        return response.data
    except Exception as exc:
        logger.error("list_folders failed: %s", exc)
        raise DatabaseError("list_folders", str(exc)) from exc


async def _collect_descendant_folder_ids(folder_id: str) -> list[str]:
    """Collect all descendant folder IDs including self via iterative BFS."""
    client = get_client()
    collected: list[str] = []
    queue: list[str] = [folder_id]

    while queue:
        current = queue.pop(0)
        collected.append(current)
        try:
            response = (
                client.table("folders")
                .select("folder_id")
                .eq("parent_id", current)
                .execute()
            )
        except Exception as exc:
            logger.error("_collect_descendant_folder_ids failed: %s", exc)
            raise DatabaseError("collect_descendants", str(exc)) from exc
        queue.extend([row["folder_id"] for row in response.data])

    return collected


async def update_folder(
    folder_id: str,
    user_id: str,
    name: str | None = None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Update folder name and/or parent with ownership and cycle checks."""
    client = get_client()
    folder = await get_folder(folder_id)

    if folder.get("user_id") != user_id:
        raise FolderPermissionError("update")

    updates: dict[str, Any] = {}
    if name is not None:
        updates["name"] = name

    if parent_id is not None:
        if parent_id == folder_id:
            raise FolderCycleError(folder_id=folder_id, parent_id=parent_id)
        parent = await get_folder(parent_id)
        if not _is_folder_visible(parent, user_id):
            raise FolderPermissionError("move")

        descendants = await _collect_descendant_folder_ids(folder_id)
        if parent_id in descendants:
            raise FolderCycleError(folder_id=folder_id, parent_id=parent_id)

        updates["parent_id"] = parent_id

    if not updates:
        return folder

    try:
        response = (
            client.table("folders")
            .update(updates)
            .eq("folder_id", folder_id)
            .execute()
        )
        return response.data[0]
    except Exception as exc:
        logger.error("update_folder failed: %s", exc)
        raise DatabaseError("update_folder", str(exc)) from exc


async def delete_folder(folder_id: str, user_id: str) -> None:
    """Delete a folder (cascade on descendants handled by DB FK)."""
    client = get_client()
    folder = await get_folder(folder_id)
    if folder.get("user_id") != user_id:
        raise FolderPermissionError("delete")

    try:
        client.table("folders").delete().eq("folder_id", folder_id).execute()
    except Exception as exc:
        logger.error("delete_folder failed: %s", exc)
        raise DatabaseError("delete_folder", str(exc)) from exc


async def set_folder_global_state(folder_id: str, user_id: str, make_global: bool) -> dict[str, Any]:
    """Share folder globally or make it private recursively for descendants."""
    client = get_client()
    folder = await get_folder(folder_id)
    if folder.get("user_id") != user_id and folder.get("shared_by") != user_id:
        raise FolderPermissionError("change sharing")

    ids = await _collect_descendant_folder_ids(folder_id)
    for fid in ids:
        payload = {
            "user_id": None,
            "shared_by": user_id,
        } if make_global else {
            "user_id": user_id,
            "shared_by": None,
        }
        try:
            client.table("folders").update(payload).eq("folder_id", fid).execute()
        except Exception as exc:
            logger.error("set_folder_global_state failed for %s: %s", fid, exc)
            raise DatabaseError("set_folder_global_state", str(exc)) from exc

    return await get_folder(folder_id)


async def list_files_in_folder(
    folder_id: str | None,
    user_id: str,
) -> list[dict[str, Any]]:
    """List files directly under a folder visible to user."""
    client = get_client()
    try:
        query = client.table("uploaded_files").select(
            "file_id,filename,folder_id,status,created_at,session_id"
        )
        if folder_id is None:
            query = query.is_("folder_id", "null")
        else:
            query = query.eq("folder_id", folder_id)
        response = query.order("filename").execute()

        # Visibility filter: file is visible if its folder is global/owned
        # or if it belongs to a user-owned session.
        visible: list[dict[str, Any]] = []
        for row in response.data:
            if row.get("folder_id"):
                try:
                    folder = await get_folder(row["folder_id"])
                    if _is_folder_visible(folder, user_id):
                        visible.append(row)
                except FolderNotFoundError:
                    continue
            else:
                session = await get_session(row["session_id"])
                if session.get("user_id") == user_id:
                    visible.append(row)

        return visible
    except Exception as exc:
        logger.error("list_files_in_folder failed: %s", exc)
        raise DatabaseError("list_files_in_folder", str(exc)) from exc


async def get_folder_tree(
    user_id: str,
    root_folder_id: str | None = None,
    max_depth: int = 6,
    max_items: int = 500,
) -> dict[str, Any]:
    """Return nested folder/file tree for visible folders with safety limits."""
    client = get_client()
    try:
        response = (
            client.table("folders")
            .select("folder_id,name,parent_id,user_id,shared_by")
            .or_(f"user_id.eq.{user_id},user_id.is.null")
            .execute()
        )
        folders = response.data

        files_response = client.table("uploaded_files").select(
            "file_id,filename,folder_id,session_id"
        ).execute()
        files = files_response.data
    except Exception as exc:
        logger.error("get_folder_tree failed: %s", exc)
        raise DatabaseError("get_folder_tree", str(exc)) from exc

    folder_children: dict[str | None, list[dict[str, Any]]] = {}
    for folder in folders:
        key = folder.get("parent_id")
        folder_children.setdefault(key, []).append(folder)

    count = 0
    truncated = False

    def build_node(folder: dict[str, Any], depth: int) -> dict[str, Any]:
        nonlocal count, truncated
        count += 1
        if count > max_items:
            truncated = True
            return {"folder_id": folder["folder_id"], "name": folder["name"], "truncated": True}

        node = {
            "folder_id": folder["folder_id"],
            "name": folder["name"],
            "shared": folder.get("user_id") is None,
            "children": [],
            "files": [
                {"file_id": f["file_id"], "filename": f["filename"]}
                for f in files
                if f.get("folder_id") == folder["folder_id"]
            ],
        }
        if depth >= max_depth:
            if folder_children.get(folder["folder_id"]):
                node["truncated"] = True
            return node

        children = folder_children.get(folder["folder_id"], [])
        for child in children:
            node["children"].append(build_node(child, depth + 1))
        return node

    roots = folder_children.get(root_folder_id, []) if root_folder_id else folder_children.get(None, [])
    tree = [build_node(root, 1) for root in roots]
    return {
        "root_folder_id": root_folder_id,
        "max_depth": max_depth,
        "truncated": truncated,
        "items": tree,
    }


async def glob_documents(pattern: str, user_id: str, folder_id: str | None = None) -> list[dict[str, Any]]:
    """Find documents by filename pattern over visible files."""
    files = await list_files_in_folder(folder_id, user_id)
    regex = re.compile(pattern.replace("*", ".*"), re.IGNORECASE)
    return [f for f in files if regex.search(f.get("filename", ""))]


async def grep_documents(
    pattern: str,
    user_id: str,
    folder_id: str | None = None,
    use_regex: bool = False,
) -> list[dict[str, Any]]:
    """Search pattern against full markdown over visible files."""
    client = get_client()
    base_files = await list_files_in_folder(folder_id, user_id)
    ids = [f["file_id"] for f in base_files]
    if not ids:
        return []

    try:
        response = (
            client.table("uploaded_files")
            .select("file_id,filename,full_markdown,folder_id")
            .in_("file_id", ids)
            .execute()
        )
    except Exception as exc:
        if _is_missing_column_error(exc, "uploaded_files", "full_markdown"):
            logger.warning(
                "grep_documents: uploaded_files.full_markdown missing in schema; returning no text matches"
            )
            return []
        logger.error("grep_documents failed: %s", exc)
        raise DatabaseError("grep_documents", str(exc)) from exc

    matches: list[dict[str, Any]] = []
    for row in response.data:
        text = row.get("full_markdown") or ""
        if not text:
            continue
        if use_regex:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append({"file_id": row["file_id"], "filename": row["filename"], "folder_id": row.get("folder_id")})
        else:
            if pattern.lower() in text.lower():
                matches.append({"file_id": row["file_id"], "filename": row["filename"], "folder_id": row.get("folder_id")})
    return matches


async def read_document(file_id: str, user_id: str, start_line: int | None = None, end_line: int | None = None) -> dict[str, Any]:
    """Read full markdown for a file, optionally with line range."""
    client = get_client()
    try:
        response = (
            client.table("uploaded_files")
            .select("file_id,filename,folder_id,full_markdown,session_id")
            .eq("file_id", file_id)
            .single()
            .execute()
        )
    except Exception as exc:
        if _is_missing_column_error(exc, "uploaded_files", "full_markdown"):
            logger.warning(
                "read_document: uploaded_files.full_markdown missing in schema; returning empty document content"
            )
            try:
                response = (
                    client.table("uploaded_files")
                    .select("file_id,filename,folder_id,session_id")
                    .eq("file_id", file_id)
                    .single()
                    .execute()
                )
            except Exception as fallback_exc:
                logger.error("read_document fallback failed: %s", fallback_exc)
                raise DatabaseError("read_document", str(fallback_exc)) from fallback_exc
        else:
            logger.error("read_document failed: %s", exc)
            raise DatabaseError("read_document", str(exc)) from exc

    if not response.data:
        raise FileNotFoundError(file_id)

    row = response.data
    allowed = False
    folder_id = row.get("folder_id")
    if folder_id:
        folder = await get_folder(folder_id)
        allowed = _is_folder_visible(folder, user_id)
    else:
        session = await get_session(row["session_id"])
        allowed = session.get("user_id") == user_id

    if not allowed:
        raise FolderPermissionError("read")

    full_text = row.get("full_markdown") or ""
    lines = full_text.splitlines()
    if start_line is not None and end_line is not None:
        start = max(1, start_line)
        end = min(len(lines), end_line)
        selected = "\n".join(lines[start - 1:end])
    else:
        selected = full_text

    return {
        "file_id": row["file_id"],
        "filename": row["filename"],
        "line_count": len(lines),
        "content": selected,
    }


# ---------------------------------------------------------------------------
# Message operations
# ---------------------------------------------------------------------------


async def insert_message(
    session_id: str | UUID,
    role: str,
    content: str,
    llm_provider: str | None = None,
    retrieval_score_avg: float | None = None,
    latency_ms: int | None = None,
) -> dict[str, Any]:
    """Insert one message row into the messages table."""
    client = get_client()
    payload: dict[str, Any] = {
        "session_id": str(session_id),
        "role": role,
        "content": content,
    }
    if llm_provider is not None:
        payload["llm_provider"] = llm_provider
    if retrieval_score_avg is not None:
        payload["retrieval_score_avg"] = retrieval_score_avg
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    try:
        response = client.table("messages").insert(payload).execute()
        return response.data[0]
    except Exception as exc:
        logger.error("insert_message failed: %s", exc)
        raise DatabaseError("insert_message", str(exc)) from exc


async def count_user_messages(session_id: str | UUID) -> int:
    """Return the number of user-role messages in a session (PRD 7.3 trigger)."""
    client = get_client()
    try:
        response = (
            client.table("messages")
            .select("message_id", count="exact")
            .eq("session_id", str(session_id))
            .eq("role", "user")
            .execute()
        )
        return response.count or 0
    except Exception as exc:
        logger.error("count_user_messages failed: %s", exc)
        raise DatabaseError("count_user_messages", str(exc)) from exc


async def get_recent_messages(
    session_id: str | UUID, limit: int = 2
) -> list[dict[str, Any]]:
    """Fetch the most recent N messages ordered by created_at DESC then reversed."""
    client = get_client()
    try:
        response = (
            client.table("messages")
            .select("*")
            .eq("session_id", str(session_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Return in chronological order (oldest first)
        return list(reversed(response.data))
    except Exception as exc:
        logger.error("get_recent_messages failed: %s", exc)
        raise DatabaseError("get_recent_messages", str(exc)) from exc


async def get_messages_paginated(
    session_id: str | UUID, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated messages and total count for the history endpoint."""
    client = get_client()
    try:
        response = (
            client.table("messages")
            .select("*", count="exact")
            .eq("session_id", str(session_id))
            .order("created_at", desc=False)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return response.data, response.count or 0
    except Exception as exc:
        logger.error("get_messages_paginated failed: %s", exc)
        raise DatabaseError("get_messages_paginated", str(exc)) from exc


async def get_last_n_messages(
    session_id: str | UUID, n: int
) -> list[dict[str, Any]]:
    """Fetch last N messages in chronological order (for summarization)."""
    client = get_client()
    try:
        response = (
            client.table("messages")
            .select("*")
            .eq("session_id", str(session_id))
            .order("created_at", desc=True)
            .limit(n)
            .execute()
        )
        return list(reversed(response.data))
    except Exception as exc:
        logger.error("get_last_n_messages failed: %s", exc)
        raise DatabaseError("get_last_n_messages", str(exc)) from exc


# ---------------------------------------------------------------------------
# Memory summary operations
# ---------------------------------------------------------------------------


async def upsert_memory_summary(
    session_id: str | UUID,
    summary_text: str,
    message_count: int,
) -> None:
    """Upsert memory summary keyed by session_id (PRD 7.3)."""
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "session_id": str(session_id),
        "summary_text": summary_text,
        "message_count_at_summary": message_count,
        "updated_at": now,
    }
    try:
        client.table("memory_summaries").upsert(
            payload, on_conflict="session_id"
        ).execute()
    except Exception as exc:
        logger.error("upsert_memory_summary failed: %s", exc)
        raise DatabaseError("upsert_memory_summary", str(exc)) from exc


async def get_memory_summary(session_id: str | UUID) -> dict[str, Any] | None:
    """Return the memory summary for a session, or None if none exists."""
    client = get_client()
    try:
        response = (
            client.table("memory_summaries")
            .select("*")
            .eq("session_id", str(session_id))
            .single()
            .execute()
        )
        return response.data or None
    except Exception as exc:
        err_str = str(exc)
        # PGRST116 means no rows found — that is an expected 404 state
        if "PGRST116" in err_str or "No rows" in err_str:
            return None
        logger.error("get_memory_summary failed: %s", exc)
        raise DatabaseError("get_memory_summary", err_str) from exc


# ---------------------------------------------------------------------------
# Embedding cache operations  (PRD 6.1 embedding_cache table)
# ---------------------------------------------------------------------------


def _cache_key(text: str, model_name: str) -> str:
    """SHA-256 of (text + '||' + model_name) to avoid prefix collisions.

    Using a separator prevents two different (text, model) pairs from
    producing the same hash via concatenation (e.g. text='ab', model='cdef'
    vs text='abc', model='def' would collide without the separator).
    """
    raw = (text + "||" + model_name).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def get_embedding_cache(
    text: str, model_name: str
) -> list[float] | None:
    """Look up a cached embedding. Returns the vector or None on miss."""
    client = get_client()
    key = _cache_key(text, model_name)
    try:
        response = (
            client.table("embedding_cache")
            .select("embedding_vector")
            .eq("text_hash", key)
            .eq("model_name", model_name)
            .single()
            .execute()
        )
        if response.data and response.data.get("embedding_vector"):
            return json.loads(response.data["embedding_vector"])
        return None
    except Exception as exc:
        err_str = str(exc)
        if "PGRST116" in err_str or "No rows" in err_str:
            return None
        # Cache miss is non-fatal; log and proceed
        logger.warning("get_embedding_cache error (non-fatal): %s", exc)
        return None


async def set_embedding_cache(
    text: str, model_name: str, vector: list[float]
) -> None:
    """Store an embedding in the cache. Non-fatal on failure."""
    client = get_client()
    key = _cache_key(text, model_name)
    payload = {
        "text_hash": key,
        "model_name": model_name,
        "embedding_vector": json.dumps(vector),
    }
    try:
        client.table("embedding_cache").upsert(
            payload, on_conflict="text_hash"
        ).execute()
    except Exception as exc:
        # Cache write failure must not crash the request
        logger.warning("set_embedding_cache failed (non-fatal): %s", exc)
