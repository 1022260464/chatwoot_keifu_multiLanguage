# RAG Database Scripts

This directory stores PostgreSQL scripts for the RAG knowledge base.

Run order:

```bash
psql "$DATABASE_URL" -f agent_demo/db/001_create_knowledge_chunks.sql
psql "$DATABASE_URL" -f agent_demo/db/002_create_knowledge_indexes.sql
psql "$DATABASE_URL" -f agent_demo/db/003_create_knowledge_chunk_upsert.sql
psql "$DATABASE_URL" -f agent_demo/db/004_sample_inserts.sql
```

The application currently expects the table `knowledge_chunks` with these fields:

```text
id
chunk_text
metadata
search_vector
```

The table also includes `embedding vector(1536)` for future pgvector semantic search. If your embedding model uses a different dimension, update `VECTOR(1536)` before creating the table.

Recommended insert shape for imported document chunks:

```text
source_doc_id
source_name
chunk_index
chunk_text
embedding
metadata
language
user_level
tags
token_count
```

Keep `metadata.user_level` in sync with the `user_level` column because the current `PgVectorRagStore` filters by `metadata->>'user_level'`.

Import scripts should call `upsert_knowledge_chunk(...)` instead of repeating raw `INSERT ... ON CONFLICT` SQL. This keeps conflict handling, defaults, and update behavior in one place.

System insertion logic lives in:

```text
src/customer_agent/knowledge_ingestion.py
```

Use `PgKnowledgeChunkWriter.import_chunks(...)` from API handlers, background jobs, or admin tools. The command-line script below is a thin wrapper around that module.

Runtime insert path should pass already-split chunk objects directly to `PgKnowledgeChunkWriter`; it should not read SQL or JSON files on every request. The files in this directory are for database initialization, examples, and offline batch imports only.

Document reading and chunking logic lives in:

```text
src/customer_agent/document_chunking.py
```

Use `build_knowledge_chunks(...)` when the system has raw document text and needs to split it before calling `PgKnowledgeChunkWriter`.

Dashboard API:

```text
POST /dashboard/knowledge/chunk-document
Header: X-Dashboard-Token: <DASHBOARD_API_TOKEN>
```

Set `import_to_db=false` to preview chunks only. Set `import_to_db=true` to split and write chunks to PostgreSQL.

Python import:

```bash
python agent_demo/scripts/import_knowledge_chunks.py --file agent_demo/db/sample_chunks.json --dry-run
python agent_demo/scripts/import_knowledge_chunks.py --file agent_demo/db/sample_chunks.json
```

Manual UI test document:

```text
db/test_knowledge_document.md
```

Upload this file in the dashboard "知识库入库" page to test document reading, chunk preview, and database import.

To replace one document's active chunks before importing new chunks:

```bash
python agent_demo/scripts/import_knowledge_chunks.py \
  --file agent_demo/db/sample_chunks.json \
  --deactivate-source loan_faq_v1
```
