-- Supabase PostgreSQL migration script
-- Run this in the Supabase SQL editor to create all tables for the
-- Adaptive Domain-Aware RAG backend.
-- Schema is derived directly from PRD Section 6.1.

-- ============================================================
-- chat_sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    domain      TEXT        NOT NULL CHECK (domain IN ('finance', 'law', 'global')),
    user_id     TEXT        NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ NULL
);

-- ============================================================
-- uploaded_files
-- ============================================================
CREATE TABLE IF NOT EXISTS uploaded_files (
    file_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES chat_sessions(session_id),
    domain          TEXT        NOT NULL CHECK (domain IN ('finance', 'law', 'global')),
    filename        TEXT        NOT NULL,
    storage_path    TEXT        NOT NULL,
    file_size_bytes BIGINT      NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'indexed', 'failed')),
    chunk_count     INTEGER     NULL,
    chart_data      JSONB       NULL,
    error_message   TEXT        NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at      TIMESTAMPTZ NULL
);

-- ============================================================
-- messages
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    message_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID        NOT NULL REFERENCES chat_sessions(session_id),
    role                TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content             TEXT        NOT NULL,
    llm_provider        TEXT        NULL,
    retrieval_score_avg FLOAT       NULL,
    latency_ms          INTEGER     NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index specified in PRD Section 6.1
CREATE INDEX IF NOT EXISTS idx_messages_session_created
    ON messages(session_id, created_at DESC);

-- ============================================================
-- memory_summaries
-- ============================================================
CREATE TABLE IF NOT EXISTS memory_summaries (
    summary_id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              UUID        NOT NULL UNIQUE REFERENCES chat_sessions(session_id),
    summary_text            TEXT        NOT NULL,
    message_count_at_summary INTEGER    NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- embedding_cache
-- ============================================================
CREATE TABLE IF NOT EXISTS embedding_cache (
    cache_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    text_hash        TEXT        NOT NULL UNIQUE,
    embedding_vector JSONB       NOT NULL,
    model_name       TEXT        NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
