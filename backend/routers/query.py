"""Query router — POST /api/v1/query

PRD Section 5.3, 3.2, 13.4
"""

import json
import logging
import re
import time
from typing import Any

from fastapi import APIRouter

from config import settings
from core import database
from core.exceptions import FileNotFoundError, FileSessionMismatchError
from core.schemas import LLMResponse, QueryRequest, QueryResponse
from pipelines.generation.pipeline import GenerationPipeline
from pipelines.ingestion.embedder import HFEmbedder
from pipelines.memory.summarizer import Summarizer
from pipelines.retrieval.query_preprocessor import normalize_query_for_retrieval
from pipelines.retrieval.pipeline import RetrievalPipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["query"])

_embedder = HFEmbedder()
_retrieval = RetrievalPipeline()
_generation = GenerationPipeline()
_summarizer = Summarizer()

# Keywords that indicate the user wants chart data returned (Finance domain only).
# PRD Section 9.1 marks the trigger logic as UNSPECIFIED — this is the agreed heuristic.
_CHART_KEYWORDS: frozenset[str] = frozenset(
    {
        "chart",
        "graph",
        "plot",
        "trend",
        "trends",
        "breakdown",
        "distribution",
        "category",
        "categories",
        "spending",
        "monthly",
        "visualize",
        "visualise",
        "show me",
        "total",
        "totals",
        "summary",
        "overview",
        "highlights",
        "usage",
        "behavior",
        "insights",
    }
)

# Insufficient-data response — returned when retrieval returns no usable chunks (PRD 13.4)
_INSUFFICIENT_DATA_RESPONSE = {
    "insights": [],
    "warnings": ["Insufficient data to generate insights."],
    "recommendations": [],
    "data": {},
}

def _wants_chart(query: str) -> bool:
    """Return True if query contains a chart-related keyword."""
    lower = query.lower()
    return any(kw in lower for kw in _CHART_KEYWORDS)


def _parse_top_n(query: str) -> int | None:
    """Extract a numeric limit from the query, e.g. 'top 5' → 5. Returns None if not found."""
    match = re.search(r"\btop\s+(\d+)\b", query, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # Also handle phrases like 'give me 3 categories'
    match = re.search(r"\b(\d+)\s+(?:categor|item|transaction|entri)", query, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _parse_amount_thresholds(query: str) -> tuple[float | None, float | None]:
    """Extract optional absolute amount thresholds from natural-language queries.

    Examples:
    - "over 500" -> (500, None)
    - "under 1200" -> (None, 1200)
    - "between 200 and 900" -> (200, 900)
    """

    def _as_float(raw: str) -> float | None:
        cleaned = raw.replace(",", "").strip()
        try:
            value = float(cleaned)
        except (TypeError, ValueError):
            return None
        return value if value >= 0 else abs(value)

    amount_pattern = r"(?:[$€£₹]\s*)?([0-9][0-9,]*(?:\.\d+)?)"

    between = re.search(
        rf"\bbetween\s+{amount_pattern}\s+(?:and|to)\s+{amount_pattern}\b",
        query,
        flags=re.IGNORECASE,
    )
    if between:
        a = _as_float(between.group(1))
        b = _as_float(between.group(2))
        if a is not None and b is not None:
            low, high = sorted((a, b))
            return low, high

    min_match = re.search(
        rf"\b(?:over|above|greater\s+than|more\s+than|at\s+least|min(?:imum)?)\s+{amount_pattern}\b",
        query,
        flags=re.IGNORECASE,
    )
    max_match = re.search(
        rf"\b(?:under|below|less\s+than|at\s+most|max(?:imum)?)\s+{amount_pattern}\b",
        query,
        flags=re.IGNORECASE,
    )

    min_amount = _as_float(min_match.group(1)) if min_match else None
    max_amount = _as_float(max_match.group(1)) if max_match else None

    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        min_amount, max_amount = max_amount, min_amount

    return min_amount, max_amount


def _filter_chart_data(chart_data: dict | None, query: str) -> dict | None:
    """Trim chart arrays to the numeric limit if the user asked for a specific top-N."""
    if not chart_data:
        return chart_data
    n = _parse_top_n(query)
    min_amount, max_amount = _parse_amount_thresholds(query)
    has_amount_filter = min_amount is not None or max_amount is not None
    if (n is None or n <= 0) and not has_amount_filter:
        return chart_data  # No chart limit/amount filter detected — return full data

    def _within_amount(value: float) -> bool:
        magnitude = abs(float(value))
        if min_amount is not None and magnitude < min_amount:
            return False
        if max_amount is not None and magnitude > max_amount:
            return False
        return True

    filtered = dict(chart_data)  # shallow copy to avoid mutating the DB object

    # Slice pie_chart
    if "pie_chart" in filtered and filtered["pie_chart"]:
        pie = filtered["pie_chart"]
        # Rank by absolute magnitude so large debits/credits are both prioritized.
        pairs = sorted(
            zip(pie.get("labels", []), pie.get("values", [])),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        if has_amount_filter:
            pairs = [p for p in pairs if _within_amount(p[1])]
        if n is not None and n > 0:
            pairs = pairs[:n]
        filtered["pie_chart"] = {
            "labels": [p[0] for p in pairs],
            "values": [p[1] for p in pairs],
        }

    # Slice bar_chart
    if "bar_chart" in filtered and filtered["bar_chart"]:
        bar = filtered["bar_chart"]
        pairs = sorted(
            zip(bar.get("labels", []), bar.get("values", [])),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        if has_amount_filter:
            pairs = [p for p in pairs if _within_amount(p[1])]
        if n is not None and n > 0:
            pairs = pairs[:n]
        filtered["bar_chart"] = {
            "labels": [p[0] for p in pairs],
            "values": [p[1] for p in pairs],
        }

    # Slice category_totals
    if "category_totals" in filtered and filtered["category_totals"]:
        sorted_cats = sorted(
            filtered["category_totals"].items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        if has_amount_filter:
            sorted_cats = [c for c in sorted_cats if _within_amount(float(c[1]))]
        if n is not None and n > 0:
            sorted_cats = sorted_cats[:n]
        filtered["category_totals"] = dict(sorted_cats)

    # Slice top_categories
    if "top_categories" in filtered:
        top_categories = list(filtered["top_categories"] or [])
        if has_amount_filter and isinstance(filtered.get("category_totals"), dict):
            allowed = set(filtered["category_totals"].keys())
            top_categories = [cat for cat in top_categories if cat in allowed]
        if n is not None and n > 0:
            top_categories = top_categories[:n]
        filtered["top_categories"] = top_categories

    # Slice monthly series/line chart so top-N requests don't still show full trends.
    if "monthly_trends" in filtered and isinstance(filtered["monthly_trends"], list):
        if n is not None and n > 0:
            filtered["monthly_trends"] = filtered["monthly_trends"][-n:]

    if "line_chart" in filtered and filtered["line_chart"]:
        periods = list(filtered["line_chart"].get("periods", []))
        totals = list(filtered["line_chart"].get("totals", []))
        pairs = list(zip(periods, totals))
        if n is not None and n > 0:
            pairs = pairs[-n:]
        filtered["line_chart"] = {
            "periods": [p[0] for p in pairs],
            "totals": [p[1] for p in pairs],
        }

    # Recompute summary_stats to match the filtered subset
    cat_totals = filtered.get("category_totals", {})
    if cat_totals:
        values = list(cat_totals.values())
        total = sum(values)
        highest_cat = max(cat_totals, key=lambda k: cat_totals[k])
        existing_stats = chart_data.get("summary_stats", {}) or {}
        # Reuse monthly-level stats (avg_monthly) scaled proportionally if possible
        full_total = (chart_data.get("summary_stats") or {}).get("total", total) or total
        scale = total / full_total if full_total else 1.0
        avg_monthly = round((existing_stats.get("avg_monthly") or 0) * scale, 2)
        filtered["summary_stats"] = {
            "total": round(total, 2),
            "avg_monthly": avg_monthly,
            "highest_category": highest_cat,
            "currency": existing_stats.get("currency"),
            "currency_mode": existing_stats.get("currency_mode", "unknown"),
            "currency_breakdown": existing_stats.get("currency_breakdown", {}),
            "highest_single_transaction": max(values),
            "lowest_single_transaction": min(values),
        }

    return filtered


def _is_finance_analysis_query(query: str) -> bool:
    return bool(
        re.search(
            r"\b(summary|overview|analy[sz]e?|insight|trend|top|highest|lowest|stock|price|performance|compare|breakdown|recommend)\b",
            query,
            flags=re.IGNORECASE,
        )
    )


def _is_spending_summary_query(query: str) -> bool:
    return bool(
        re.search(
            r"\b(spending|spent|total\s+spent|expense|expenses)\b",
            query,
            flags=re.IGNORECASE,
        )
    )


def _is_spend_reduction_query(query: str) -> bool:
    return bool(
        re.search(
            r"\b(reduce|cut|save|saving|lower|decrease|trim|optimi[sz]e|where\s+should\s+i\s+reduce|where\s+to\s+reduce)\b",
            query,
            flags=re.IGNORECASE,
        )
    )


def _is_income_category(category: str) -> bool:
    lowered = category.strip().lower()
    return bool(
        re.search(
            r"\b(paycheck|salary|income|bonus|interest\s*income|deposit|refund\s*received|transfer\s*in|credit\s*card\s*payment|reimbursement)\b",
            lowered,
        )
    )


def _is_discretionary_category(category: str) -> bool:
    lowered = category.strip().lower()
    return bool(
        re.search(
            r"\b(alcohol|bars?|coffee|restaurant|dining|entertainment|movies?|music|shopping|fast\s*food|takeout|travel|subscription|electronics?|software|games?)\b",
            lowered,
        )
    )


def _expense_totals_from_category_totals(category_totals: dict[str, Any]) -> dict[str, float]:
    """Return normalized expense totals by category, excluding likely income categories.

    If dataset encodes expenses as negatives, use absolute value of negative sums.
    Otherwise, use positive sums while filtering out likely inflow categories.
    """
    normalized: dict[str, float] = {}
    has_negative = any(isinstance(v, (int, float)) and float(v) < 0 for v in category_totals.values())

    if has_negative:
        for category, value in category_totals.items():
            if not isinstance(value, (int, float)):
                continue
            amount = float(value)
            if amount < 0:
                normalized[str(category)] = round(abs(amount), 2)
        return normalized

    for category, value in category_totals.items():
        if not isinstance(value, (int, float)):
            continue
        amount = float(value)
        if amount <= 0:
            continue
        if _is_income_category(str(category)):
            continue
        normalized[str(category)] = round(amount, 2)
    return normalized


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return []


def _append_unique(items: list[str], candidate: str) -> None:
    if not candidate:
        return
    key = candidate.strip().lower()
    if not key:
        return
    existing = {it.strip().lower() for it in items}
    if key not in existing:
        items.append(candidate)


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[a-zA-Z]{4,}", query.lower())
    stop = {
        "explain",
        "about",
        "what",
        "does",
        "mean",
        "means",
        "please",
        "tell",
        "show",
    }
    return [t for t in terms if t not in stop]


def _is_definition_style_law_query(query: str) -> bool:
    return bool(
        re.search(
            r"^\s*(explain|what\s+is|define|meaning\s+of)\b",
            query,
            flags=re.IGNORECASE,
        )
    )


def _text_relevance_score(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def _is_low_value_law_line(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True

    # Avoid citation-only filler lines that do not explain meaning.
    citation_only_patterns = [
        r"\bis mentioned\b",
        r"\barticle\s+[ivxlcdm]+\b",
        r"\bsection\s+\d+\b",
    ]
    has_citation = any(re.search(p, lowered) for p in citation_only_patterns)
    has_explanatory_signal = bool(
        re.search(r"\b(means|allows|permits|requires|applies|only when|unless|except|during|limits|prohibits)\b", lowered)
    )
    return has_citation and not has_explanatory_signal


def _clean_line(text: str) -> str:
    line = re.sub(r"\s+", " ", text).strip(" -:\t")
    return line


def _extract_law_evidence_lines(chunks: list[dict[str, Any]], query: str, limit: int = 3) -> list[str]:
    terms = _query_terms(query)
    candidates: list[str] = []

    for chunk in chunks:
        chunk_text = str(chunk.get("chunk_text") or "")
        if not chunk_text:
            continue

        for raw_line in re.split(r"\n+", chunk_text):
            line = _clean_line(raw_line)
            if len(line) < 35:
                continue
            if len(line) > 280:
                line = line[:277].rstrip() + "..."
            if terms and not any(term in line.lower() for term in terms):
                continue
            candidates.append(line)

    if not candidates:
        for chunk in chunks:
            chunk_text = str(chunk.get("chunk_text") or "")
            for sentence in re.split(r"(?<=[.!?])\s+", chunk_text):
                line = _clean_line(sentence)
                if 35 <= len(line) <= 280:
                    candidates.append(line)

    unique: list[str] = []
    seen: set[str] = set()
    for line in candidates:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(line)
        if len(unique) >= limit:
            break

    return unique


def _is_low_information_law_response(response: dict[str, Any], query: str) -> bool:
    insights = _ensure_list(response.get("insights"))
    if len(insights) >= 2:
        return False

    if not insights:
        return True

    q = query.strip().lower()
    first = insights[0].strip().lower()
    if first == q or first in q or q in first:
        return True

    # Single ultra-short insight tends to be unhelpful for legal explain queries.
    return len(first) < 40


def _enrich_law_response_with_chunks(
    response: dict[str, Any],
    chunks: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    if not chunks:
        return response

    insights = _ensure_list(response.get("insights"))
    warnings = _ensure_list(response.get("warnings"))
    recommendations = _ensure_list(response.get("recommendations"))
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    terms = _query_terms(query)
    definition_style = _is_definition_style_law_query(query)

    if definition_style and terms:
        ranked = sorted(
            (
                (
                    item,
                    _text_relevance_score(item, terms),
                    _is_low_value_law_line(item),
                )
                for item in insights
            ),
            key=lambda x: (x[1], not x[2]),
            reverse=True,
        )
        focused = [item for item, score, low_value in ranked if score > 0 and not low_value]
        if not focused:
            focused = [item for item, score, _ in ranked if score > 0]

        evidence_lines = _extract_law_evidence_lines(chunks, query, limit=3)
        if len(focused) < 2 and evidence_lines:
            for line in evidence_lines:
                _append_unique(focused, line)
                if len(focused) >= 3:
                    break

        if focused:
            insights = focused[:4]

    evidence_lines = _extract_law_evidence_lines(chunks, query, limit=3)
    if _is_low_information_law_response(response, query) and evidence_lines:
        for line in evidence_lines:
            _append_unique(insights, line)

    clauses = data.get("clauses") if isinstance(data.get("clauses"), list) else []
    if definition_style and terms and clauses:
        normalized_clauses: list[dict[str, str]] = []
        for clause in clauses:
            if isinstance(clause, dict):
                name = str(clause.get("name") or "").strip()
                desc = str(clause.get("description") or "").strip()
            else:
                name = str(clause).strip()
                desc = ""

            full_text = f"{name} {desc}".strip()
            if not full_text:
                continue

            if _text_relevance_score(full_text, terms) == 0:
                continue

            if not desc and len(name) > 60:
                desc = name
                name = "Relevant clause"

            normalized_clauses.append({"name": name or "Relevant clause", "description": desc})

        if normalized_clauses:
            data["clauses"] = normalized_clauses[:3]
        else:
            data.pop("clauses", None)
    if not clauses and evidence_lines:
        data["clauses"] = [
            {
                "name": "Relevant extracted context",
                "description": line,
            }
            for line in evidence_lines[:2]
        ]

    if not recommendations and evidence_lines:
        _append_unique(recommendations, "Review the cited passages in full document context before final legal interpretation.")

    if definition_style and not recommendations:
        _append_unique(recommendations, "Compare this clause with adjacent provisions and exceptions before drawing legal conclusions.")

    if not evidence_lines:
        _append_unique(warnings, "Limited directly matching legal context was retrieved for this query.")

    response["insights"] = insights
    response["warnings"] = warnings
    response["recommendations"] = recommendations
    response["data"] = data
    return response


def _enrich_finance_response_with_chart_data(
    response: dict[str, Any],
    chart_data: dict[str, Any] | None,
    query: str,
) -> dict[str, Any]:
    """Deterministically enrich thin finance responses using computed chart data."""
    if not chart_data:
        return response

    summary = chart_data.get("summary_stats") or {}
    category_totals = chart_data.get("category_totals") or {}
    monthly = chart_data.get("monthly_trends") or []

    insights = _ensure_list(response.get("insights"))
    warnings = _ensure_list(response.get("warnings"))
    recommendations = _ensure_list(response.get("recommendations"))
    data = response.get("data") if isinstance(response.get("data"), dict) else {}

    total = summary.get("total")
    total_spent = summary.get("total_spent")
    avg_monthly = summary.get("avg_monthly")
    avg_monthly_spent = summary.get("avg_monthly_spent")
    highest_category = summary.get("highest_category")
    highest_single = summary.get("highest_single_transaction")
    currency = summary.get("currency")
    currency_mode = summary.get("currency_mode", "unknown")
    is_spending_query = _is_spending_summary_query(query)
    is_reduction_query = _is_spend_reduction_query(query)
    expense_totals = _expense_totals_from_category_totals(category_totals)
    top_expense = sorted(expense_totals.items(), key=lambda kv: kv[1], reverse=True)[:3]

    currency_prefix = f"{currency} " if currency and currency_mode == "single" else ""

    if is_spending_query and isinstance(total_spent, (int, float)):
        _append_unique(insights, f"Indexed total spent is {currency_prefix}{float(total_spent):,.2f}.")
    elif isinstance(total, (int, float)):
        _append_unique(insights, f"Indexed total amount is {currency_prefix}{float(total):,.2f}.")

    if is_spending_query and isinstance(avg_monthly_spent, (int, float)) and monthly:
        _append_unique(
            insights,
            f"Average monthly spending is {currency_prefix}{float(avg_monthly_spent):,.2f} across {len(monthly)} periods.",
        )
    elif isinstance(avg_monthly, (int, float)) and monthly:
        _append_unique(insights, f"Average monthly amount is {currency_prefix}{float(avg_monthly):,.2f} across {len(monthly)} periods.")

    if top_expense:
        rendered = ", ".join([f"{cat} ({currency_prefix}{amt:,.2f})" for cat, amt in top_expense])
        _append_unique(insights, f"Top expense categories are {rendered}.")
    elif highest_category:
        _append_unique(insights, f"Top category by aggregate amount is {highest_category}.")

    if isinstance(highest_single, (int, float)):
        _append_unique(insights, f"Largest single observed value is {currency_prefix}{float(highest_single):,.2f}.")

    if currency_mode == "mixed":
        _append_unique(warnings, "Multiple currencies detected. Totals combine different currencies unless filtered.")

    if is_reduction_query:
        discretionary = [(cat, amt) for cat, amt in top_expense if _is_discretionary_category(cat)]
        if discretionary:
            top_discretionary = discretionary[0]
            _append_unique(
                recommendations,
                f"Start by reducing {top_discretionary[0]} spend first; it is a high controllable expense at about {currency_prefix}{top_discretionary[1]:,.2f}.",
            )
        elif top_expense:
            _append_unique(
                recommendations,
                f"Prioritize optimization in {top_expense[0][0]} because it is your largest expense category at about {currency_prefix}{top_expense[0][1]:,.2f}.",
            )
        _append_unique(recommendations, "Set a monthly cap for the top 2-3 expense categories and track variance weekly.")

    if _is_finance_analysis_query(query):
        _append_unique(recommendations, "Filter analysis by currency and period before making budget or allocation decisions.")
        _append_unique(recommendations, "Drill into top categories and largest values to identify controllable drivers.")

    if not data.get("summary_stats") and summary:
        data["summary_stats"] = summary
    if not data.get("top_categories") and chart_data.get("top_categories"):
        data["top_categories"] = chart_data.get("top_categories")
    if expense_totals and not data.get("expense_category_totals"):
        data["expense_category_totals"] = expense_totals
    if top_expense and not data.get("top_expense_categories"):
        data["top_expense_categories"] = [cat for cat, _ in top_expense]

    response["insights"] = insights
    response["warnings"] = warnings
    response["recommendations"] = recommendations
    response["data"] = data
    return response


@router.post("/query", response_model=QueryResponse)
async def submit_query(body: QueryRequest):
    """Submit a query and receive a structured insight response (PRD 5.3).

    Full flow:
      1. Validate session exists
      2. Embed query (cache-aware)
      3. Parallel: retrieve Qdrant chunks + fetch memory
      4. Confidence check — skip LLM if no usable chunks (PRD 13.4)
      5. Build prompt + call LLM (Gemini → Groq fallback)
      6. Validate LLM output (with repair retry)
      7. For Finance: attach chart_data if query implies charts (PRD 9.1)
      8. Store messages to Supabase
      9. Trigger memory summarization (non-blocking)
      10. Return full response
    """
    start_ms = time.monotonic()

    session_id = str(body.session_id)
    domain = body.domain
    query = body.query
    retrieval_query = normalize_query_for_retrieval(query, domain=domain)
    file_id = str(body.file_id) if body.file_id else None

    # Step 1 — validate session and enforce session domain as source of truth
    session_row = await database.get_session(session_id)
    session_domain = session_row.get("domain")
    if session_domain in {"finance", "law", "global"} and session_domain != domain:
        logger.warning(
            "QUERY DEBUG: domain mismatch (request=%s, session=%s) for session_id=%s; using session domain",
            domain,
            session_domain,
            session_id,
        )
        domain = session_domain

    if file_id:
        file_row = await database.get_file(file_id)
        if not file_row:
            raise FileNotFoundError(file_id)
        if str(file_row.get("session_id")) != session_id:
            raise FileSessionMismatchError(file_id=file_id, session_id=session_id)

    # Step 2 — embed query (with cache)
    query_vector = await _embedder.embed_texts([retrieval_query])
    query_vec = query_vector[0]

    # Step 3 — parallel retrieval + memory fetch
    logger.info(
        "QUERY DEBUG: session_id=%s, domain=%s, file_id=%s, query=%s",
        session_id, domain, file_id, query[:80],
    )
    chunks, summary, recent_messages = await _retrieval.run(
        query_vector=query_vec,
        domain=domain,
        session_id=session_id,
        file_id=file_id,
    )
    logger.info("QUERY DEBUG: retrieved %d chunk(s)", len(chunks))

    # Step 4 — confidence check (PRD 13.4, 13.3)
    avg_score: float = 0.0
    retrieval_confidence = "normal"
    if not chunks:
        logger.warning("QUERY DEBUG: No chunks found — returning insufficient data")
        # No valid context — return insufficient data without calling LLM
        validated_response = _INSUFFICIENT_DATA_RESPONSE
        provider = "none"
        chart_data = None
        retrieval_confidence = "insufficient"
    else:
        avg_score = round(
            sum(c["score"] for c in chunks) / len(chunks), 4
        )
        if avg_score < settings.retrieval_score_threshold:
            retrieval_confidence = "low"

        # Step 5 & 6 — build prompt, call LLM, validate
        validated_response, provider = await _generation.run(
            domain=domain,
            query=query,
            chunks=chunks,
            summary=summary,
            recent_messages=recent_messages,
            session_id=session_id,
        )

        # Bug 8 fix: if generation returned the safe fallback (both Gemini and Groq failed),
        # mark provider as "none" so the stored message is not misleadingly attributed.
        from pipelines.generation.validator import _SAFE_FALLBACK
        if validated_response == _SAFE_FALLBACK:
            provider = "none"

        # Step 7 — chart_data for Finance only (PRD 10.4)
        chart_data = None
        if domain == "finance" and _wants_chart(query) and file_id:
            raw_chart = await database.get_file_chart_data(file_id)
            chart_data = _filter_chart_data(raw_chart, query)

        if domain == "finance":
            validated_response = _enrich_finance_response_with_chart_data(
                validated_response,
                chart_data,
                query,
            )
        elif domain == "law":
            validated_response = _enrich_law_response_with_chunks(
                validated_response,
                chunks,
                query,
            )

    latency_ms = int((time.monotonic() - start_ms) * 1000)

    # Step 8 — persist messages
    await database.insert_message(
        session_id=session_id,
        role="user",
        content=query,
    )
    await database.insert_message(
        session_id=session_id,
        role="assistant",
        content=json.dumps(validated_response),
        llm_provider=provider if provider != "none" else None,
        retrieval_score_avg=avg_score if chunks else None,
        latency_ms=latency_ms,
    )

    # Step 9 — async summarization trigger (PRD 7.3)
    # Awaited directly — summarizer never raises
    await _summarizer.maybe_summarize(session_id)

    # Step 10 — return response
    return QueryResponse(
        session_id=body.session_id,
        query=query,
        domain=domain,
        llm_provider=provider,
        response=LLMResponse(**validated_response),
        chart_data=chart_data,
        retrieval_score_avg=avg_score,
        retrieval_confidence=retrieval_confidence,
        latency_ms=latency_ms,
    )
