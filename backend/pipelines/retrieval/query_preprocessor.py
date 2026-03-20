"""Query preprocessing utilities for retrieval robustness.

Applies conservative normalization and typo correction only for retrieval embeddings,
without mutating the original user query saved to history.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import get_close_matches

_COMMON_FINANCE_TERMS: frozenset[str] = frozenset(
    {
        "amount",
        "analysis",
        "analyze",
        "analyse",
        "average",
        "balance",
        "budget",
        "breakdown",
        "category",
        "compare",
        "cost",
        "credit",
        "currency",
        "debit",
        "distribution",
        "expense",
        "expenses",
        "finance",
        "highest",
        "insight",
        "insights",
        "invest",
        "investment",
        "lowest",
        "monthly",
        "overview",
        "performance",
        "portfolio",
        "price",
        "profit",
        "recommendation",
        "risk",
        "score",
        "sector",
        "spend",
        "spending",
        "stock",
        "stocks",
        "summary",
        "top",
        "total",
        "transaction",
        "transactions",
        "trend",
        "trends",
        "value",
        "volatility",
        "warning",
        "yearly",
    }
)

# Small explicit map for common keyboard typos seen in production-like prompts.
_DIRECT_TYPOS: dict[str, str] = {
    "buget": "budget",
    "budet": "budget",
    "stocj": "stock",
    "stcok": "stock",
    "transections": "transactions",
    "ammount": "amount",
    "reccomendation": "recommendation",
    "analys": "analysis",
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u00A0", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _correct_token(token: str, vocabulary: set[str]) -> str:
    if token in _DIRECT_TYPOS:
        return _DIRECT_TYPOS[token]

    if len(token) < 4 or not token.isalpha():
        return token

    if token in vocabulary:
        return token

    candidates = get_close_matches(token, vocabulary, n=1, cutoff=0.84)
    if not candidates:
        return token

    return candidates[0]


def normalize_query_for_retrieval(query: str, domain: str = "finance") -> str:
    """Normalize and typo-correct user query for retrieval embedding only.

    The correction is conservative and domain-aware. It does not alter numerics,
    symbols, or short words where aggressive correction often causes false matches.
    """
    text = _normalize_text(query)

    if domain != "finance":
        return text

    vocab = set(_COMMON_FINANCE_TERMS)

    tokens = re.findall(r"[A-Za-z]+|\d+(?:[.,]\d+)?|[^\w\s]|\s+", text)
    corrected_tokens: list[str] = []
    corrections = 0
    max_corrections = 6

    for token in tokens:
        if token.isspace() or re.fullmatch(r"\d+(?:[.,]\d+)?", token) or re.fullmatch(r"[^\w\s]", token):
            corrected_tokens.append(token)
            continue

        lower_token = token.lower()
        corrected = _correct_token(lower_token, vocab)

        if corrected != lower_token and corrections < max_corrections:
            corrections += 1
            corrected_tokens.append(corrected)
        else:
            corrected_tokens.append(lower_token)

    return "".join(corrected_tokens)
