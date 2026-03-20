"""Retrieval pipeline orchestrator.

Runs Qdrant vector search and Supabase memory fetch in parallel (PRD 3.2)
using asyncio.gather to minimize total latency.
"""

import asyncio
import logging

from pipelines.retrieval.memory import MemoryFetcher
from pipelines.retrieval.retriever import QdrantRetriever

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    """Orchestrate parallel retrieval of chunks and memory context."""

    def __init__(self) -> None:
        self._retriever = QdrantRetriever()
        self._memory_fetcher = MemoryFetcher()

    async def run(
        self,
        query_vector: list[float],
        domain: str,
        session_id: str,
        file_id: str | None = None,
    ) -> tuple[list[dict], str | None, list[dict]]:
        """Run retrieval and memory fetch concurrently.

        Returns:
            chunks         — list of retrieved chunks (may be empty)
            summary_text   — memory summary string or None
            recent_messages — last 2 messages in chronological order
        """
        chunks, (summary_text, recent_messages) = await asyncio.gather(
            self._retriever.retrieve(query_vector, domain, session_id=session_id, file_id=file_id),
            self._memory_fetcher.fetch(session_id),
        )
        logger.debug(
            "RetrievalPipeline: %d chunk(s), summary=%s, messages=%d",
            len(chunks),
            "yes" if summary_text else "none",
            len(recent_messages),
        )
        return chunks, summary_text, recent_messages
