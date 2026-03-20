"""Qdrant vector database client wrapper.

Provides typed functions for upsert, search, and delete operations.
Each function raises a specific AppError on failure — no silent errors (PRD 13.3).
"""

import logging
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from config import settings
from core.exceptions import IngestionFailedError

logger = logging.getLogger(__name__)

_client: AsyncQdrantClient | None = None

_PAYLOAD_INDEXES: tuple[tuple[str, PayloadSchemaType], ...] = (
    ("domain", PayloadSchemaType.KEYWORD),
    ("file_id", PayloadSchemaType.KEYWORD),
    ("session_id", PayloadSchemaType.KEYWORD),
)


def get_client() -> AsyncQdrantClient:
    """Return the shared async Qdrant client, creating it on first call."""
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    return _client


def collection_for_domain(domain: str) -> str:
    """Return the Qdrant collection name for the given domain (PRD 6.3)."""
    if domain == "finance":
        return settings.qdrant_finance_collection
    if domain == "global":
        return settings.qdrant_global_collection
    return settings.qdrant_law_collection


# ---------------------------------------------------------------------------
# Collection initialisation
# ---------------------------------------------------------------------------


async def ensure_collections_exist() -> None:
    """Create finance, law, and global collections if they do not exist.

    Called at application startup. Safe to call repeatedly.
    Collection config matches PRD Section 6.3 exactly:
    - size: 384 (all-MiniLM-L6-v2)
    - distance: Cosine
    - on_disk_payload: True
    """
    client = get_client()
    for collection_name in (
        settings.qdrant_finance_collection,
        settings.qdrant_law_collection,
        settings.qdrant_global_collection,
    ):
        exists = await client.collection_exists(collection_name)
        if not exists:
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE,
                ),
                on_disk_payload=True,
            )
            logger.info("Created Qdrant collection: %s", collection_name)

        # Ensure required payload indexes exist even for pre-existing collections.
        await _ensure_payload_indexes(collection_name)


async def _ensure_payload_indexes(collection_name: str) -> None:
    """Ensure all retrieval-critical payload indexes exist on the collection."""
    client = get_client()
    for field_name, field_schema in _PAYLOAD_INDEXES:
        try:
            await client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_schema,
            )
        except Exception as exc:
            # Index may already exist or provider may return a benign conflict.
            logger.debug(
                "create_payload_index skipped for '%s.%s': %s",
                collection_name,
                field_name,
                exc,
            )


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------


async def upsert_points(
    collection_name: str,
    points: list[dict[str, Any]],
) -> None:
    """Upsert a list of embedding points into a Qdrant collection.

    Each dict in `points` must have:
      - vector: list[float]
      - payload: dict matching PRD Section 6.3 point schema
    """
    client = get_client()
    qdrant_points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=p["vector"],
            payload=p["payload"],
        )
        for p in points
    ]
    try:
        await client.upsert(
            collection_name=collection_name,
            points=qdrant_points,
        )
    except Exception as exc:
        logger.error("upsert_points failed for collection '%s': %s", collection_name, exc)
        raise IngestionFailedError(f"Qdrant write failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Search operations
# ---------------------------------------------------------------------------


async def search(
    collection_name: str,
    query_vector: list[float],
    top_k: int,
    domain: str,
    score_threshold: float,
    session_id: str | None = None,
    file_id: str | None = None,
) -> list[dict[str, Any]]:
    """Perform a filtered vector search and return hits above score_threshold.

    Domain filter is STRICT — cross-domain retrieval is forbidden (PRD 4.1).
    Optional file_id filter is applied when the query specifies a specific file.

    Returns a list of dicts with keys: chunk_text, score, metadata.
    """
    client = get_client()

    must_conditions = [
        FieldCondition(key="domain", match=MatchValue(value=domain))
    ]
    if session_id:
        must_conditions.append(
            FieldCondition(key="session_id", match=MatchValue(value=session_id))
        )
    if file_id:
        must_conditions.append(
            FieldCondition(key="file_id", match=MatchValue(value=file_id))
        )

    query_filter = Filter(must=must_conditions)

    async def _do_search() -> list:
        return await client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

    try:
        results = await _do_search()
    except Exception as exc:
        err = str(exc)
        if "Index required but not found" in err:
            logger.warning(
                "Qdrant search missing index for '%s'. Creating payload indexes and retrying once.",
                collection_name,
            )
            try:
                await _ensure_payload_indexes(collection_name)
                results = await _do_search()
            except Exception as retry_exc:
                logger.error("Qdrant search retry failed: %s", retry_exc)
                return []
        else:
            logger.error("Qdrant search failed: %s", exc)
            # Return empty — treated as no results (PRD 13.3)
            return []

    hits = []
    for result in results:
        payload = result.payload or {}
        hits.append(
            {
                "chunk_text": payload.get("chunk_text", ""),
                "score": result.score,
                "metadata": {
                    "file_id": payload.get("file_id"),
                    "session_id": payload.get("session_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "source_filename": payload.get("source_filename"),
                    "domain": payload.get("domain"),
                },
            }
        )
    return hits


# ---------------------------------------------------------------------------
# Delete operations
# ---------------------------------------------------------------------------


async def delete_points_by_session(
    collection_name: str, session_id: str
) -> None:
    """Delete all Qdrant points whose payload.session_id matches the given value.

    Used during session deletion (PRD 5.6) and ingest rollback (PRD 5.2).
    Non-fatal on missing points.
    """
    client = get_client()
    delete_filter = Filter(
        must=[
            FieldCondition(
                key="session_id", match=MatchValue(value=session_id)
            )
        ]
    )
    try:
        await client.delete(
            collection_name=collection_name,
            points_selector=delete_filter,
        )
    except Exception as exc:
        logger.error(
            "delete_points_by_session failed for collection '%s', session '%s': %s",
            collection_name,
            session_id,
            exc,
        )
        # Non-fatal during session deletion; throw on ingest rollback context
        raise IngestionFailedError(f"Qdrant rollback failed: {exc}") from exc


async def delete_points_by_file(
    collection_name: str, file_id: str
) -> None:
    """Delete all Qdrant points for a specific file. Used in ingest rollback."""
    client = get_client()
    delete_filter = Filter(
        must=[
            FieldCondition(key="file_id", match=MatchValue(value=file_id))
        ]
    )
    try:
        await client.delete(
            collection_name=collection_name,
            points_selector=delete_filter,
        )
    except Exception as exc:
        logger.error(
            "delete_points_by_file failed for file '%s': %s", file_id, exc
        )
        raise IngestionFailedError(f"Qdrant rollback failed: {exc}") from exc
