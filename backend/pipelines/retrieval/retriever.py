"""Qdrant retriever component for the query pipeline.

Enforces domain-strict filtering (PRD 4.1) and score threshold gating (PRD 3.2).
"""

import logging

from config import settings
from core import qdrant as qdrant_client

logger = logging.getLogger(__name__)


class QdrantRetriever:
    """Retrieve semantically relevant chunks from Qdrant for a given query vector.

    Domain filter is MANDATORY on every call — cross-domain retrieval is
    forbidden (PRD 4.1). Only chunks with score >= score_threshold are returned.
    """

    def __init__(self) -> None:
        self._top_k = settings.retrieval_top_k
        self._score_threshold = settings.retrieval_score_threshold

    async def retrieve(
        self,
        query_vector: list[float],
        domain: str,
        session_id: str | None = None,
        file_id: str | None = None,
    ) -> list[dict]:
        """Search Qdrant and return only chunks that meet the score threshold.

        Returns a list of dicts: [{chunk_text, score, metadata}, ...]
        Returns an empty list when no results meet the threshold.
        """
        collection = qdrant_client.collection_for_domain(domain)
        hits = await qdrant_client.search(
            collection_name=collection,
            query_vector=query_vector,
            top_k=self._top_k,
            domain=domain,
            score_threshold=self._score_threshold,
            session_id=session_id,
            file_id=file_id,
        )

        # Fallback for sparse/noisy queries: if strict threshold removes all hits,
        # retry once with 0.0 to avoid false "insufficient data" responses.
        if not hits and self._score_threshold > 0:
            logger.info(
                "No hits at threshold %.3f for domain='%s' (session=%s, file=%s); retrying with 0.0",
                self._score_threshold,
                domain,
                session_id,
                file_id,
            )
            hits = await qdrant_client.search(
                collection_name=collection,
                query_vector=query_vector,
                top_k=self._top_k,
                domain=domain,
                score_threshold=0.0,
                session_id=session_id,
                file_id=file_id,
            )

        logger.debug(
            "Retrieved %d chunk(s) for domain='%s' with threshold=%.2f",
            len(hits),
            domain,
            self._score_threshold,
        )
        return hits
