from __future__ import annotations

import logging

from .clients import (
    ChatwootGateway,
    DeepSeekLLMClient,
    InMemoryRagStore,
    LLMClient,
    MockLLMClient,
    NullChatwootClient,
    PgVectorRagStore,
    RagStore,
)
from .chatwoot import ChatwootClient
from .config import Settings
from .workflow import CustomerSupportAgent


logger = logging.getLogger(__name__)


def build_agent(settings: Settings) -> CustomerSupportAgent:
    return CustomerSupportAgent(
        settings=settings,
        llm=build_llm(settings),
        rag_store=build_rag_store(settings),
        chatwoot=build_chatwoot(settings),
    )


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider.lower() == "deepseek":
        return DeepSeekLLMClient(settings)
    return MockLLMClient()


def build_rag_store(settings: Settings) -> RagStore:
    if getattr(settings, "rag_provider", "memory").lower() == "pgvector":
        return PgVectorRagStore(settings)

    return InMemoryRagStore(
        documents=[
            (
                "refund_policy",
                "用户在付款后 7 天内可以申请退款。已使用的增值服务、定制开发服务和人工代办服务不支持无理由退款。",
                {"category": "售后", "user_level": "all"},
            ),
            (
                "business_hours",
                "人工客服在线时间为工作日 09:00-18:00。非工作时间会由 AI 助手先记录问题并创建待跟进会话。",
                {"category": "客服", "user_level": "all"},
            ),
            (
                "vip_support",
                "VIP 客户可以获得专属客服、优先排队和工单加急处理。",
                {"category": "会员", "user_level": "VIP"},
            ),
        ]
    )


def build_chatwoot(settings: Settings) -> ChatwootGateway:
    if (
        settings.chatwoot_base_url
        and settings.chatwoot_account_id
        and settings.chatwoot_api_access_token
    ):
        logger.info("Using real Chatwoot client")
        return ChatwootClient(settings)

    logger.warning("Chatwoot settings are incomplete; using NullChatwootClient")
    return NullChatwootClient()
