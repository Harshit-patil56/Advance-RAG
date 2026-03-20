-- Supabase PostgreSQL migration script
-- Phase 2 update: folders + exploration retrieval support.

-- ============================================================
-- folders
-- ============================================================
CREATE TABLE IF NOT EXISTS folders (
    folder_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT        NOT NULL,
    parent_id    UUID        NULL REFERENCES folders(folder_id) ON DELETE CASCADE,
    user_id      TEXT        NULL,
    shared_by    TEXT        NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_folders_parent_id ON folders(parent_id);
CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders(user_id);

-- ============================================================
-- uploaded_files enhancements
-- ============================================================
ALTER TABLE uploaded_files
    ADD COLUMN IF NOT EXISTS folder_id UUID NULL REFERENCES folders(folder_id) ON DELETE SET NULL;

ALTER TABLE uploaded_files
    ADD COLUMN IF NOT EXISTS full_markdown TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_uploaded_files_folder_id ON uploaded_files(folder_id);

-- Keep updated_at current for folders.
CREATE OR REPLACE FUNCTION set_folders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_folders_updated_at ON folders;
CREATE TRIGGER trg_folders_updated_at
BEFORE UPDATE ON folders
FOR EACH ROW
EXECUTE FUNCTION set_folders_updated_at();
