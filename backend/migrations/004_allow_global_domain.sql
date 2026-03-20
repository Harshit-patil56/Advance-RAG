-- Allow the new 'global' domain in existing databases.

ALTER TABLE chat_sessions
    DROP CONSTRAINT IF EXISTS chat_sessions_domain_check;

ALTER TABLE chat_sessions
    ADD CONSTRAINT chat_sessions_domain_check
    CHECK (domain IN ('finance', 'law', 'global'));

ALTER TABLE uploaded_files
    DROP CONSTRAINT IF EXISTS uploaded_files_domain_check;

ALTER TABLE uploaded_files
    ADD CONSTRAINT uploaded_files_domain_check
    CHECK (domain IN ('finance', 'law', 'global'));
