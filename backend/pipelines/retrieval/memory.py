"""Memory fetcher: retrieves memory summary and recent messages from Supabase.

Both fetches are run in parallel by the retrieval pipeline (PRD 3.2, 7.1).
"""

import logging

from core import database

logger = logging.getLogger(__name__)


class MemoryFetcher:
    """Fetch the memory context for a session from Supabase.

    Returns:
      - summary_text: str | None  (None when no summary generated yet)
      - recent_messages: list[dict]  (last 2 messages in chronological order)
    """

    async def fetch(
        self, session_id: str
    ) -> tuple[str | None, list[dict]]:
        """Fetch memory summary and the last 2 messages for the session."""
        summary_row = await database.get_memory_summary(session_id)
        recent = await database.get_recent_messages(session_id, limit=2)

        summary_text = summary_row["summary_text"] if summary_row else None
        logger.debug(
            "Memory fetch for session='%s': summary=%s, recent_messages=%d",
            session_id,
            "yes" if summary_text else "none",
            len(recent),
        )
        return summary_text, recent
