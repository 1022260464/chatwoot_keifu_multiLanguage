-- RAG knowledge base table for PostgreSQL + pgvector.
-- Run this file before enabling RAG_PROVIDER=pgvector.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,

    -- Source document identity. Multiple chunks from one document share this id.
    source_doc_id TEXT NOT NULL,
    source_name TEXT,
    source_type TEXT NOT NULL DEFAULT 'text',
    source_url TEXT,

    -- Chunk identity and content.
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_hash TEXT,

    -- Semantic vector. Change 1536 if the embedding model uses another dimension.
    embedding VECTOR(1536),

    -- Full-text search vector used by the current PgVectorRagStore implementation.
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(chunk_text, ''))
    ) STORED,

    -- Flexible business metadata. Keep metadata.user_level for current code compatibility.
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    language TEXT NOT NULL DEFAULT 'zh-CN',
    user_level TEXT NOT NULL DEFAULT 'all',
    tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

    token_count INTEGER,
    char_count INTEGER GENERATED ALWAYS AS (char_length(chunk_text)) STORED,

    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_knowledge_chunks_source_chunk UNIQUE (source_doc_id, chunk_index),
    CONSTRAINT chk_knowledge_chunks_chunk_index CHECK (chunk_index >= 0),
    CONSTRAINT chk_knowledge_chunks_chunk_text CHECK (length(trim(chunk_text)) > 0),
    CONSTRAINT chk_knowledge_chunks_token_count CHECK (token_count IS NULL OR token_count >= 0)
);

COMMENT ON TABLE knowledge_chunks IS 'One row per RAG text chunk. Stores source metadata, text, full-text vector, and optional embedding vector.';
COMMENT ON COLUMN knowledge_chunks.source_doc_id IS 'Stable source document id, for example loan_faq_v1.';
COMMENT ON COLUMN knowledge_chunks.chunk_index IS 'Zero-based chunk order inside the source document.';
COMMENT ON COLUMN knowledge_chunks.chunk_text IS 'Text passed to RAG/LLM as retrieved context.';
COMMENT ON COLUMN knowledge_chunks.embedding IS 'Semantic embedding vector for pgvector similarity search.';
COMMENT ON COLUMN knowledge_chunks.search_vector IS 'Generated PostgreSQL full-text search vector from chunk_text.';
COMMENT ON COLUMN knowledge_chunks.metadata IS 'Flexible JSON metadata. Current code reads metadata->>user_level.';
COMMENT ON COLUMN knowledge_chunks.user_level IS 'Indexed copy of user visibility level, such as all, new_user, vip, internal.';
COMMENT ON COLUMN knowledge_chunks.is_active IS 'Soft-delete flag. Keep false rows for audit or rollback.';

CREATE OR REPLACE FUNCTION set_knowledge_chunks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_knowledge_chunks_updated_at ON knowledge_chunks;

CREATE TRIGGER trg_knowledge_chunks_updated_at
BEFORE UPDATE ON knowledge_chunks
FOR EACH ROW
EXECUTE FUNCTION set_knowledge_chunks_updated_at();
