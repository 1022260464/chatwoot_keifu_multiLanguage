-- Indexes for the RAG knowledge base.
-- Run after 001_create_knowledge_chunks.sql.

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_search_vector
ON knowledge_chunks USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_metadata
ON knowledge_chunks USING GIN (metadata);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_tags
ON knowledge_chunks USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_user_level
ON knowledge_chunks (user_level);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_language
ON knowledge_chunks (language);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source_doc_id
ON knowledge_chunks (source_doc_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_active
ON knowledge_chunks (is_active);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_active_level_language
ON knowledge_chunks (is_active, user_level, language);

-- HNSW vector index for cosine similarity search.
-- Requires pgvector. Rows without embeddings are skipped by the partial index.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding_hnsw
ON knowledge_chunks
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
