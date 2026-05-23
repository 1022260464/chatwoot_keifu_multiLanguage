from __future__ import annotations

import re
import json
from abc import ABC, abstractmethod
from collections import Counter
from math import sqrt
from urllib import request
from urllib.error import HTTPError, URLError
from typing import Any

from .config import Settings
from .schemas import IncomingMessage, Intent, RetrievedChunk


class LLMClient(ABC):
    @abstractmethod
    async def classify_intent(self, message: IncomingMessage) -> Intent:
        raise NotImplementedError

    @abstractmethod
    async def generate_answer(self, message: IncomingMessage, chunks: list[RetrievedChunk]) -> str:
        raise NotImplementedError

    @abstractmethod
    async def summarize_handoff(self, message: IncomingMessage, reason: str) -> str:
        raise NotImplementedError


class RagStore(ABC):
    @abstractmethod
    async def search(self, query: str, user_level: str, limit: int) -> list[RetrievedChunk]:
        raise NotImplementedError


class ChatwootGateway(ABC):
    @abstractmethod
    async def open_conversation(self, conversation_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_public_reply(self, conversation_id: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_private_note(self, conversation_id: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_interactive_message(
        self,
        conversation_id: str,
        content: str,
        content_type: str,
        content_attributes: dict[str, Any],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def handoff_to_human(self, conversation_id: str, private_note: str) -> None:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    async def classify_intent(self, message: IncomingMessage) -> Intent:
        text = message.content.lower()
        handoff_words = ("人工", "真人", "客服", "投诉", "生气", "差评", "退款不到账")
        business_words = ("订单", "物流", "发票", "账号", "套餐", "开通")
        faq_words = ("怎么", "如何", "政策", "费用", "价格", "退款", "时间", "支持")

        if any(word in text for word in handoff_words):
            return Intent.HUMAN_HANDOFF
        if any(word in text for word in business_words):
            return Intent.BUSINESS
        if any(word in text for word in faq_words):
            return Intent.FAQ
        if len(text) <= 12:
            return Intent.CHITCHAT
        return Intent.UNKNOWN

    async def generate_answer(self, message: IncomingMessage, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "这个问题我暂时没有查到可靠资料，我会为你转接人工客服继续处理。"

        facts = "\n".join(f"- {chunk.text}" for chunk in chunks)
        return f"根据当前知识库，我可以这样回答：\n{facts}"

    async def summarize_handoff(self, message: IncomingMessage, reason: str) -> str:
        return (
            f"AI 建议转人工。\n"
            f"原因：{reason}\n"
            f"用户问题：{message.content}\n"
            f"联系人：{message.contact_id}"
        )


class DeepSeekLLMClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required when using DeepSeekLLMClient")
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url.rstrip("/")
        self._model = settings.deepseek_model

    async def classify_intent(self, message: IncomingMessage) -> Intent:
        prompt = (
            "你是客服意图分类器。只输出以下枚举之一："
            "chitchat, faq, business, complaint, human_handoff, unknown。\n"
            f"用户消息：{message.content}"
        )
        raw = await self._chat(prompt)
        normalized = raw.strip().lower()
        try:
            return Intent(normalized)
        except ValueError:
            return Intent.UNKNOWN

    async def generate_answer(self, message: IncomingMessage, chunks: list[RetrievedChunk]) -> str:
        context = "\n\n".join(f"[{idx + 1}] {chunk.text}" for idx, chunk in enumerate(chunks))
        prompt = (
            "你是企业客服 AI。请只基于给定知识库上下文回答；"
            "如果上下文不足，明确说明需要人工确认。回答要简洁、准确、中文。\n\n"
            f"知识库上下文：\n{context or '无'}\n\n"
            f"用户问题：{message.content}"
        )
        return await self._chat(prompt)

    async def summarize_handoff(self, message: IncomingMessage, reason: str) -> str:
        prompt = (
            "请为人工客服生成一段内部交接备注，包含用户诉求、转人工原因、建议下一步。"
            "控制在 120 字以内。\n"
            f"转人工原因：{reason}\n"
            f"用户消息：{message.content}\n"
            f"联系人 ID：{message.contact_id}"
        )
        return await self._chat(prompt)

    async def _chat(self, prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }

        def send() -> str:
            body = json.dumps(payload).encode("utf-8")
            req = request.Request(
                f"{self._base_url}/chat/completions",
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with request.urlopen(req, timeout=45) as response:
                    data = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"DeepSeek API error {exc.code}: {detail}") from exc
            except URLError as exc:
                raise RuntimeError(f"DeepSeek API request failed: {exc.reason}") from exc

            return data["choices"][0]["message"]["content"].strip()

        import asyncio

        return await asyncio.to_thread(send)


class InMemoryRagStore(RagStore):
    def __init__(self, documents: list[tuple[str, str, dict[str, Any]]]) -> None:
        self._documents = documents

    async def search(self, query: str, user_level: str, limit: int) -> list[RetrievedChunk]:
        query_vector = _term_vector(query)
        chunks: list[RetrievedChunk] = []

        for doc_id, text, metadata in self._documents:
            allowed_level = metadata.get("user_level", "all")
            if allowed_level not in ("all", user_level):
                continue

            score = min(_cosine_similarity(query_vector, _term_vector(text)) * 6.0, 1.0)
            if score <= 0:
                continue

            chunks.append(RetrievedChunk(doc_id=doc_id, text=text, score=score, metadata=metadata))

        return sorted(chunks, key=lambda item: item.score, reverse=True)[:limit]


class PgVectorRagStore(RagStore):
    def __init__(self, settings: Settings) -> None:
        database_url = settings.resolved_database_url
        if not database_url:
            raise ValueError("DATABASE_URL or DB_* settings are required when using PgVectorRagStore")
        self._database_url = database_url
        self._knowledge_schema = settings.knowledge_schema or "public"
        self._knowledge_table_name = settings.knowledge_table_name or "knowledge_chunks"

    async def search(self, query: str, user_level: str, limit: int) -> list[RetrievedChunk]:
        import asyncio

        return await asyncio.to_thread(self._search_sync, query, user_level, limit)

    def _search_sync(self, query: str, user_level: str, limit: int) -> list[RetrievedChunk]:
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row

        query_sql = sql.SQL("""
            SELECT
                id::text AS doc_id,
                chunk_text,
                metadata,
                ts_rank_cd(search_vector, plainto_tsquery('simple', %(query)s)) AS text_score
            FROM {table}
            WHERE COALESCE(metadata->>'user_level', 'all') IN ('all', %(user_level)s)
              AND search_vector @@ plainto_tsquery('simple', %(query)s)
            ORDER BY text_score DESC
            LIMIT %(limit)s
        """).format(
            table=sql.Identifier(self._knowledge_schema, self._knowledge_table_name),
        )

        with psycopg.connect(self._database_url, row_factory=dict_row) as conn:
            rows = conn.execute(
                query_sql,
                {"query": query, "user_level": user_level, "limit": limit},
            ).fetchall()

        return [
            RetrievedChunk(
                doc_id=row["doc_id"],
                text=row["chunk_text"],
                score=float(row["text_score"] or 0.0),
                metadata=row["metadata"] or {},
            )
            for row in rows
        ]


class NullChatwootClient(ChatwootGateway):
    async def open_conversation(self, conversation_id: str) -> None:
        return None

    async def send_public_reply(self, conversation_id: str, content: str) -> None:
        return None

    async def send_private_note(self, conversation_id: str, content: str) -> None:
        return None

    async def send_interactive_message(
        self,
        conversation_id: str,
        content: str,
        content_type: str,
        content_attributes: dict[str, Any],
    ) -> None:
        return None

    async def handoff_to_human(self, conversation_id: str, private_note: str) -> None:
        return None


def _term_vector(text: str) -> Counter[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            expanded.extend(token)
            expanded.extend(token[i : i + 2] for i in range(max(len(token) - 1, 0)))
    return Counter(expanded)


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0

    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = sqrt(sum(value * value for value in left.values()))
    right_norm = sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm)
