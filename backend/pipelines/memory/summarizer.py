"""Memory summarization — triggered every 5 user turns per session.

Implements PRD Section 7.3 and 3.3 exactly.
Uses same LLM routing as query pipeline (Gemini primary, Groq fallback).
If summarization fails, the previous summary is silently retained (PRD 7.3).
"""

import logging

from core import database
from pipelines.generation.llm_router import LLMRouter

logger = logging.getLogger(__name__)

# Summarization prompt (PRD 3.3 — verbatim)
_SUMMARIZATION_PROMPT_TEMPLATE = """\
Summarize the following conversation. Preserve:
(1) user's primary intent
(2) all key facts mentioned
(3) any explicit constraints or requirements
(4) domain-specific entities (amounts, dates, clause names, etc.)
Output: plain text summary under 300 tokens.

Conversation:
{messages}
"""


class Summarizer:
    """Produce and store a memory summary on the PRD 7.3 trigger condition."""

    def __init__(self) -> None:
        self._llm_router = LLMRouter()

    async def maybe_summarize(self, session_id: str) -> None:
        """Trigger summarization if user message count % 5 == 0 (PRD 7.3).

        On LLM failure: log and retain previous summary — do not crash (PRD 7.3).
        """
        try:
            count = await database.count_user_messages(session_id)
        except Exception as exc:
            logger.error("maybe_summarize: count_user_messages failed: %s", exc)
            return

        if count == 0 or count % 5 != 0:
            return

        logger.info(
            "Summarization triggered for session=%s at user_message_count=%d",
            session_id,
            count,
        )

        try:
            messages = await database.get_last_n_messages(session_id, n=10)
        except Exception as exc:
            logger.error("maybe_summarize: get_last_n_messages failed: %s", exc)
            return

        conversation_text = self._format_messages(messages)
        prompt = _SUMMARIZATION_PROMPT_TEMPLATE.format(messages=conversation_text)

        try:
            raw_summary, _ = await self._llm_router.call(prompt, session_id)
        except Exception as exc:
            # LLM failure: retain previous summary, no crash (PRD 7.3)
            logger.error(
                "Summarization LLM call failed for session=%s: %s. Retaining previous summary.",
                session_id,
                exc,
            )
            return

        summary_text = raw_summary.strip()
        if not summary_text:
            logger.warning("Summarization produced empty output for session=%s", session_id)
            return

        try:
            await database.upsert_memory_summary(
                session_id=session_id,
                summary_text=summary_text,
                message_count=count,
            )
        except Exception as exc:
            logger.error("upsert_memory_summary failed for session=%s: %s", session_id, exc)

    def _format_messages(self, messages: list[dict]) -> str:
        lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
