-- Add editable display name for chat sessions.

ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS session_name TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_name
    ON chat_sessions(session_name);
