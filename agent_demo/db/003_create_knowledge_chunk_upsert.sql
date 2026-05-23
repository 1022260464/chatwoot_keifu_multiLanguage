-- Reusable insert/upsert logic for RAG chunks.
-- Run after 001_create_knowledge_chunks.sql and before importing chunk data.

CREATE OR REPLACE FUNCTION upsert_knowledge_chunk(
    p_source_doc_id TEXT,
    p_chunk_index INTEGER,
    p_chunk_text TEXT,
    p_source_name TEXT DEFAULT NULL,
    p_source_type TEXT DEFAULT 'text',
    p_source_url TEXT DEFAULT NULL,
    p_chunk_hash TEXT DEFAULT NULL,
    p_embedding VECTOR(1536) DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::jsonb,
    p_language TEXT DEFAULT 'zh-CN',
    p_user_level TEXT DEFAULT 'all',
    p_tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    p_token_count INTEGER DEFAULT NULL
)
RETURNS BIGINT AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO knowledge_chunks (
        source_doc_id,
        source_name,
        source_type,
        source_url,
        chunk_index,
        chunk_text,
        chunk_hash,
        embedding,
        metadata,
        language,
        user_level,
        tags,
        token_count
    ) VALUES (
        p_source_doc_id,
        p_source_name,
        coalesce(p_source_type, 'text'),
        p_source_url,
        p_chunk_index,
        p_chunk_text,
        p_chunk_hash,
        p_embedding,
        coalesce(p_metadata, '{}'::jsonb),
        coalesce(p_language, 'zh-CN'),
        coalesce(p_user_level, 'all'),
        coalesce(p_tags, ARRAY[]::TEXT[]),
        p_token_count
    )
    ON CONFLICT (source_doc_id, chunk_index) DO UPDATE SET
        source_name = EXCLUDED.source_name,
        source_type = EXCLUDED.source_type,
        source_url = EXCLUDED.source_url,
        chunk_text = EXCLUDED.chunk_text,
        chunk_hash = EXCLUDED.chunk_hash,
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata,
        language = EXCLUDED.language,
        user_level = EXCLUDED.user_level,
        tags = EXCLUDED.tags,
        token_count = EXCLUDED.token_count
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION upsert_knowledge_chunk(
    TEXT,
    INTEGER,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    VECTOR(1536),
    JSONB,
    TEXT,
    TEXT,
    TEXT[],
    INTEGER
) IS 'Reusable RAG chunk upsert helper. Uses (source_doc_id, chunk_index) as the stable conflict key.';

CREATE OR REPLACE FUNCTION deactivate_knowledge_document(
    p_source_doc_id TEXT
)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE knowledge_chunks
    SET is_active = false
    WHERE source_doc_id = p_source_doc_id
      AND is_active = true;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION deactivate_knowledge_document(TEXT) IS 'Soft-deletes all chunks for one source document.';
