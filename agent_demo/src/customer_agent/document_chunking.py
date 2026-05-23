from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .knowledge_ingestion import KnowledgeChunkInput


class DocumentChunkOptions(BaseModel):
    max_chars: int = Field(default=900, ge=200, le=4000)
    overlap_chars: int = Field(default=120, ge=0, le=1000)

    @field_validator("overlap_chars")
    @classmethod
    def validate_overlap(cls, value: int, info: Any) -> int:
        max_chars = info.data.get("max_chars", 900)
        if value >= max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")
        return value


class DocumentChunkBuildRequest(BaseModel):
    source_doc_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

    source_name: str = ""
    source_type: str = "text"
    source_url: str = ""
    language: str = "zh-CN"
    user_level: str = "all"
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    options: DocumentChunkOptions = Field(default_factory=DocumentChunkOptions)

    @field_validator("source_doc_id", "content", "source_name", "source_type", "source_url", "language", "user_level")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class DocumentChunkPreview(BaseModel):
    source_doc_id: str
    chunk_index: int
    chunk_text: str
    chunk_hash: str
    token_count: int
    char_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


def load_text_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in {".txt", ".md", ".markdown", ".csv", ".json", ".log"}:
        raise ValueError(f"Unsupported document type: {suffix or 'unknown'}")
    return path.read_text(encoding="utf-8")


def build_knowledge_chunks(request: DocumentChunkBuildRequest) -> list[KnowledgeChunkInput]:
    parts = split_text(request.content, request.options)
    chunks: list[KnowledgeChunkInput] = []
    base_metadata = dict(request.metadata)
    if not base_metadata.get("user_level"):
        base_metadata["user_level"] = request.user_level

    for index, text in enumerate(parts):
        metadata = dict(base_metadata)
        metadata["chunk_index"] = index
        metadata["chunk_count"] = len(parts)

        chunks.append(
            KnowledgeChunkInput(
                source_doc_id=request.source_doc_id,
                source_name=request.source_name,
                source_type=request.source_type,
                source_url=request.source_url,
                chunk_index=index,
                chunk_text=text,
                chunk_hash=hash_text(text),
                metadata=metadata,
                language=request.language,
                user_level=request.user_level,
                tags=request.tags,
                token_count=estimate_token_count(text),
            )
        )
    return chunks


def preview_chunks(chunks: list[KnowledgeChunkInput]) -> list[DocumentChunkPreview]:
    return [
        DocumentChunkPreview(
            source_doc_id=chunk.source_doc_id,
            chunk_index=chunk.chunk_index,
            chunk_text=chunk.chunk_text,
            chunk_hash=chunk.chunk_hash,
            token_count=chunk.token_count or estimate_token_count(chunk.chunk_text),
            char_count=len(chunk.chunk_text),
            metadata=chunk.metadata,
        )
        for chunk in chunks
    ]


def split_text(text: str, options: DocumentChunkOptions | None = None) -> list[str]:
    opts = options or DocumentChunkOptions()
    normalized = normalize_text(text)
    if not normalized:
        return []

    blocks = split_blocks(normalized)
    chunks: list[str] = []
    current = ""

    for block in blocks:
        if len(block) > opts.max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(split_long_block(block, opts.max_chars, opts.overlap_chars))
            continue

        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= opts.max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current.strip())
        current = apply_overlap(chunks[-1], opts.overlap_chars) + block if chunks and opts.overlap_chars else block
        if len(current) > opts.max_chars:
            chunks.extend(split_long_block(current, opts.max_chars, opts.overlap_chars))
            current = ""

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk.strip()]


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_blocks(text: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if len(blocks) > 1:
        return blocks
    return split_sentences(text)


def split_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[。！？!?；;])\s*", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def split_long_block(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


def apply_overlap(previous: str, overlap_chars: int) -> str:
    if overlap_chars <= 0:
        return ""
    overlap = previous[-overlap_chars:].strip()
    return f"{overlap}\n\n" if overlap else ""


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_token_count(text: str) -> int:
    ascii_count = sum(1 for char in text if ord(char) < 128)
    non_ascii_count = len(text) - ascii_count
    return max(1, non_ascii_count + ascii_count // 4)
