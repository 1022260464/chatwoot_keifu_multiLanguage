from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .config import Settings


class KnowledgeChunkInput(BaseModel):
    source_doc_id: str = Field(..., min_length=1)
    chunk_index: int = Field(..., ge=0)
    chunk_text: str = Field(..., min_length=1)

    source_name: str = ""
    source_type: str = "text"
    source_url: str = ""
    chunk_hash: str = ""

    embedding: list[float] | str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    language: str = "zh-CN"
    user_level: str = "all"
    tags: list[str] = Field(default_factory=list)
    token_count: int | None = Field(default=None, ge=0)

    @field_validator("source_doc_id", "chunk_text", "source_name", "source_type", "source_url", "chunk_hash", "language", "user_level")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    def to_db_params(self) -> dict[str, Any]:
        metadata = dict(self.metadata)
        if not metadata.get("user_level"):
            metadata["user_level"] = self.user_level or "all"

        return {
            "source_doc_id": self.source_doc_id,
            "source_name": self.source_name or None,
            "source_type": self.source_type or "text",
            "source_url": self.source_url or None,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "chunk_hash": self.chunk_hash or None,
            "embedding": format_embedding(self.embedding),
            "metadata": json.dumps(metadata, ensure_ascii=False),
            "language": self.language or "zh-CN",
            "user_level": self.user_level or str(metadata.get("user_level") or "all"),
            "tags": self.tags,
            "token_count": self.token_count,
        }


class KnowledgeChunkImportResult(BaseModel):
    total: int
    upserted_ids: list[int] = Field(default_factory=list)
    deactivated: dict[str, int] = Field(default_factory=dict)


class PgKnowledgeChunkWriter:
    def __init__(
        self,
        database_url: str,
        schema: str = "public",
        table_name: str = "knowledge_chunks",
    ) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self._database_url = database_url
        self._schema = schema or "public"
        self._table_name = table_name or "knowledge_chunks"

    @classmethod
    def from_settings(cls, settings: Settings) -> "PgKnowledgeChunkWriter":
        if not settings.resolved_database_url:
            raise ValueError("DATABASE_URL or DB_* settings are required")
        return cls(
            settings.resolved_database_url,
            schema=settings.knowledge_schema,
            table_name=settings.knowledge_table_name,
        )

    async def import_chunks(
        self,
        chunks: list[KnowledgeChunkInput],
        deactivate_sources: list[str] | None = None,
    ) -> KnowledgeChunkImportResult:
        return await asyncio.to_thread(self.import_chunks_sync, chunks, deactivate_sources)

    def import_chunks_sync(
        self,
        chunks: list[KnowledgeChunkInput],
        deactivate_sources: list[str] | None = None,
    ) -> KnowledgeChunkImportResult:
        import psycopg
        from psycopg import sql

        result = KnowledgeChunkImportResult(total=len(chunks))
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cur:
                for source_doc_id in deactivate_sources or []:
                    cur.execute(self._deactivate_sql(sql), {"source_doc_id": source_doc_id})
                    result.deactivated[source_doc_id] = int(cur.fetchone()[0])

                for chunk in chunks:
                    cur.execute(self._upsert_sql(sql), chunk.to_db_params())
                    result.upserted_ids.append(int(cur.fetchone()[0]))

            conn.commit()

        return result

    async def deactivate_document(self, source_doc_id: str) -> int:
        return await asyncio.to_thread(self.deactivate_document_sync, source_doc_id)

    def deactivate_document_sync(self, source_doc_id: str) -> int:
        import psycopg
        from psycopg import sql

        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(self._deactivate_sql(sql), {"source_doc_id": source_doc_id})
                count = int(cur.fetchone()[0])
            conn.commit()
        return count

    def _table_identifier(self, sql_module: Any) -> Any:
        return sql_module.Identifier(self._schema, self._table_name)

    def _upsert_sql(self, sql_module: Any) -> Any:
        return sql_module.SQL("""
            INSERT INTO {table} (
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
                %(source_doc_id)s,
                %(source_name)s,
                %(source_type)s,
                %(source_url)s,
                %(chunk_index)s,
                %(chunk_text)s,
                %(chunk_hash)s,
                %(embedding)s::vector,
                %(metadata)s::jsonb,
                %(language)s,
                %(user_level)s,
                %(tags)s,
                %(token_count)s
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
                token_count = EXCLUDED.token_count,
                is_active = true
            RETURNING id
        """).format(table=self._table_identifier(sql_module))

    def _deactivate_sql(self, sql_module: Any) -> Any:
        return sql_module.SQL("""
            WITH updated AS (
                UPDATE {table}
                SET is_active = false
                WHERE source_doc_id = %(source_doc_id)s
                  AND is_active = true
                RETURNING id
            )
            SELECT count(*) FROM updated
        """).format(table=self._table_identifier(sql_module))


def load_knowledge_chunks(path: Path) -> list[KnowledgeChunkInput]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, list):
        raw_chunks = payload
    elif isinstance(payload, dict) and isinstance(payload.get("chunks"), list):
        raw_chunks = payload["chunks"]
    else:
        raise ValueError("JSON must be an array or an object with a chunks array.")

    chunks: list[KnowledgeChunkInput] = []
    for index, item in enumerate(raw_chunks):
        if not isinstance(item, dict):
            raise ValueError("Every chunk item must be an object.")
        normalized = dict(item)
        normalized.setdefault("chunk_index", index)
        chunks.append(KnowledgeChunkInput.model_validate(normalized))
    return chunks


def build_database_url_from_env() -> str:
    if os.getenv("DATABASE_URL"):
        return str(os.getenv("DATABASE_URL"))

    host = os.getenv("DB_HOST", "")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASS", "")
    if not all([host, name, user, password]):
        return ""
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def format_embedding(value: list[float] | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return "[" + ",".join(str(float(number)) for number in value) + "]"
