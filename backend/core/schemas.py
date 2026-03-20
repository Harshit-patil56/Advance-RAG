"""Pydantic request/response schemas for all API endpoints.

Models match PRD Section 5 (API Design) and Section 8 (Structured Output Format) exactly.
No extra fields are added beyond what the PRD specifies.
"""

from datetime import datetime
from typing import Literal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Domain literal
# ---------------------------------------------------------------------------

VALID_DOMAINS: frozenset[str] = frozenset({"finance", "law", "global"})


def validate_domain(value: str) -> str:
    if value not in VALID_DOMAINS:
        raise ValueError(f"domain must be 'finance', 'law', or 'global', got '{value}'")
    return value


# ---------------------------------------------------------------------------
# Session schemas  (PRD 5.1, 5.6)
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    domain: str
    user_id: str | None = None

    @field_validator("domain")
    @classmethod
    def check_domain(cls, v: str) -> str:
        return validate_domain(v)


class CreateSessionResponse(BaseModel):
    session_id: UUID
    domain: str
    session_name: str | None = None
    created_at: datetime


class DeleteSessionResponse(BaseModel):
    session_id: UUID
    deleted: bool


class UpdateSessionRequest(BaseModel):
    session_name: str = Field(..., min_length=1, max_length=120)


class UpdateSessionResponse(BaseModel):
    session_id: UUID
    session_name: str


# ---------------------------------------------------------------------------
# Ingest schemas  (PRD 5.2)
# ---------------------------------------------------------------------------


class IngestResponse(BaseModel):
    file_id: UUID
    filename: str
    domain: str
    chunk_count: int
    status: str  # "indexed"
    folder_id: UUID | None = None


# ---------------------------------------------------------------------------
# Query schemas  (PRD 5.3, 8.1)
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    session_id: UUID
    domain: str
    query: str = Field(..., min_length=1, max_length=2000)
    file_id: UUID | None = None

    @field_validator("domain")
    @classmethod
    def check_domain(cls, v: str) -> str:
        return validate_domain(v)


class LLMResponse(BaseModel):
    """Structured output exactly matching PRD Section 8.1 mandatory schema."""

    insights: list[str]
    warnings: list[str]
    recommendations: list[str]
    data: dict[str, Any]


class QueryResponse(BaseModel):
    session_id: UUID
    query: str
    domain: str
    llm_provider: str  # "gemini" | "groq"
    response: LLMResponse
    chart_data: dict[str, Any] | None = None
    retrieval_score_avg: float
    retrieval_confidence: Literal["insufficient", "low", "normal"]
    latency_ms: int


# ---------------------------------------------------------------------------
# History schemas  (PRD 5.4)
# ---------------------------------------------------------------------------


class MessageRecord(BaseModel):
    message_id: UUID
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime
    llm_provider: str | None = None
    retrieval_score_avg: float | None = None
    latency_ms: int | None = None


class HistoryResponse(BaseModel):
    session_id: UUID
    messages: list[MessageRecord]
    total: int


# ---------------------------------------------------------------------------
# Memory schemas  (PRD 5.5)
# ---------------------------------------------------------------------------


class MemoryResponse(BaseModel):
    session_id: UUID
    summary_text: str
    message_count_at_summary: int
    updated_at: datetime


# ---------------------------------------------------------------------------
# Health schemas  (PRD 5.7, 5.8)
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


class DeepHealthResponse(BaseModel):
    supabase: str   # "ok" | "error"
    qdrant: str     # "ok" | "error"
    huggingface: str
    gemini: str
    groq: str


# ---------------------------------------------------------------------------
# Standard error envelope  (PRD 13.1)
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    error: str
    error_code: str
    details: dict[str, Any] = Field(default_factory=dict)
