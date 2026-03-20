"""Token-bounded prompt builder for the query pipeline.

Constructs the final LLM prompt by filling each slot up to its token budget
(PRD Section 7.2). Truncation is from the oldest end of each slot (PRD 7.4).
"""

import logging
from typing import Any

import tiktoken

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts — verbatim from PRD Section 7.1
# ---------------------------------------------------------------------------

_FINANCE_SYSTEM_PROMPT = """You are a financial analysis assistant. Your task is to analyze financial data provided
in the context and produce structured insights. You must ALWAYS respond in valid JSON
following the exact schema: {"insights": [], "warnings": [], "recommendations": [], "data": {}}.

Rules:
- Base insights ONLY on the provided context chunks. Do not invent figures.
- Interpret informal or typo-prone user phrasing conservatively; rely on context evidence, not guesses.
- If data is insufficient, populate "warnings" with "Insufficient data" — do not guess.
- "insights" should describe trends, anomalies, and summaries from the data.
- "warnings" should highlight risky patterns, missing data, or unusual values.
- "recommendations" should suggest specific, actionable next steps.
- For stock/market datasets, use neutral terms like "price", "movement", or "series" instead of assuming spending semantics.
- "data" may contain structured sub-objects if relevant (e.g., summary stats).
- Do NOT produce narrative-only text. JSON only."""

_LAW_SYSTEM_PROMPT = """You are a legal document analysis assistant. Your task is to analyze legal text provided
in the context and produce structured findings. You must ALWAYS respond in valid JSON
following the exact schema: {"insights": [], "warnings": [], "recommendations": [], "data": {}}.

Rules:
- Base analysis ONLY on the provided context chunks. Do not invent clauses.
- If context is insufficient, populate "warnings" with "Insufficient context" — do not guess.
- "insights" should describe key clauses, defined terms, and obligations identified.
- For explain/define queries, write plain-language insights (2-4 concise points), not headings or labels.
- Keep the answer tightly focused on the asked concept; do not include unrelated clauses from the same section.
- "warnings" should list high-risk clauses, missing standard protections, or ambiguous language.
- "recommendations" should suggest specific review actions or redlines.
- "data" may include structured objects like {"clauses": [], "risks": [], "checklist": []}.
- If returning data.clauses, each clause object should include both a short "name" and a meaningful "description".
- Do NOT produce narrative-only text. JSON only."""

_GLOBAL_SYSTEM_PROMPT = """You are a document analysis assistant for mixed knowledge-base files.
You may receive context from CSV, PDF, or TXT extractions. You must ALWAYS respond in valid JSON
following the exact schema: {"insights": [], "warnings": [], "recommendations": [], "data": {}}.

Rules:
- Base findings ONLY on provided context chunks. Do not invent facts.
- For broad explain/summarize prompts, produce concise, user-friendly findings, not raw section dumps.
- If data is insufficient, add a warning "Insufficient context".
- "insights" should answer the user's question directly using concrete evidence from context.
- "warnings" should call out ambiguity, missing information, or conflicting snippets.
- "recommendations" should suggest practical next steps.
- "data" may include structured supporting objects when useful.
- Do NOT produce narrative-only text. JSON only."""

# Repair prompt used on first JSON validation failure (PRD 8.5)
REPAIR_PROMPT = (
    "Your previous response was not valid JSON. "
    "Return ONLY valid JSON with keys: "
    "insights (array), warnings (array), recommendations (array), data (object). "
    "Do not include markdown fences or commentary. "
    "Keep response compact: max 8 insights, max 4 warnings, max 6 recommendations, short strings only. "
    "No other text, no markdown, no explanation."
)

# Token budgets (PRD 7.2)
_SYSTEM_BUDGET = 400
_SUMMARY_BUDGET = 300
_HISTORY_BUDGET = 400
_CHUNKS_BUDGET = 1200
_QUERY_BUDGET = 200

_ENCODER: tiktoken.Encoding | None = None


def _enc() -> tiktoken.Encoding:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def _count(text: str) -> int:
    return len(_enc().encode(text))


def _truncate_to_budget(text: str, budget: int) -> str:
    """Truncate text to fit within token budget, trimming from the oldest (front) end."""
    tokens = _enc().encode(text)
    if len(tokens) <= budget:
        return text
    # Keep the newest (most recent) tokens — trim from the start (PRD 7.4)
    kept = tokens[-budget:]
    return _enc().decode(kept)


class PromptBuilder:
    """Build a token-bounded prompt for the LLM.

    Slot allocation (PRD 7.2):
      System    ~400 tokens (fixed)
      Summary   ≤300 tokens
      History   ≤400 tokens (last 2 turns)
      Chunks    ≤1200 tokens (up to 4 chunks × ~300 tokens each)
      Query     ≤200 tokens
    """

    def build(
        self,
        domain: str,
        query: str,
        chunks: list[dict[str, Any]],
        summary: str | None,
        recent_messages: list[dict[str, Any]],
    ) -> str:
        if domain == "finance":
            system = _FINANCE_SYSTEM_PROMPT
        elif domain == "law":
            system = _LAW_SYSTEM_PROMPT
        else:
            system = _GLOBAL_SYSTEM_PROMPT

        parts: list[str] = [system, ""]

        # Memory summary — truncate to 300 tokens (PRD 7.2)
        if summary:
            truncated_summary = _truncate_to_budget(summary, _SUMMARY_BUDGET)
            parts.append(f"[Memory Summary]\n{truncated_summary}\n")

        # Recent message history — truncate each message to fit ≤400 total
        if recent_messages:
            history_block = self._format_history(recent_messages, _HISTORY_BUDGET)
            parts.append(f"[Recent Conversation]\n{history_block}\n")

        # Retrieved context chunks — up to 4, each capped at ~300 tokens (PRD 7.2)
        if chunks:
            chunk_block = self._format_chunks(chunks, _CHUNKS_BUDGET)
            parts.append(f"[Context]\n{chunk_block}\n")

        # User query — cap at 200 tokens (PRD 7.2)
        truncated_query = _truncate_to_budget(query, _QUERY_BUDGET)
        parts.append(f"[Query]\n{truncated_query}")

        return "\n".join(parts)

    def _format_history(
        self, messages: list[dict[str, Any]], budget: int
    ) -> str:
        """Format recent messages and truncate from oldest end to fit budget."""
        lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            # For assistant messages content is a JSON string — keep as-is
            lines.append(f"{role.upper()}: {content}")

        full = "\n".join(lines)
        return _truncate_to_budget(full, budget)

    def _format_chunks(
        self, chunks: list[dict[str, Any]], budget: int
    ) -> str:
        """Number each chunk and truncate individual chunks to ~300 tokens (PRD 7.4)."""
        per_chunk_budget = 300
        lines: list[str] = []
        total_used = 0

        for i, chunk in enumerate(chunks, start=1):
            text = chunk.get("chunk_text", "")
            truncated = _truncate_to_budget(text, per_chunk_budget)
            chunk_tokens = _count(truncated)

            if total_used + chunk_tokens > budget:
                break  # Stop adding chunks if overall budget exhausted

            lines.append(f"[{i}] {truncated}")
            total_used += chunk_tokens

        return "\n\n".join(lines)
