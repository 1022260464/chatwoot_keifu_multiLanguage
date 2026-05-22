from __future__ import annotations

from typing import Any

from .clients import ChatwootGateway, LLMClient, RagStore
from .config import Settings
from .schemas import AgentAction, AgentResult, AgentState, IncomingMessage, Intent


class CustomerSupportAgent:
    def __init__(
        self,
        settings: Settings,
        llm: LLMClient,
        rag_store: RagStore,
        chatwoot: ChatwootGateway,
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._rag_store = rag_store
        self._chatwoot = chatwoot

    async def open_conversation(self, conversation_id: str) -> None:
        await self._chatwoot.open_conversation(conversation_id)

    async def send_private_note(self, conversation_id: str, content: str) -> None:
        await self._chatwoot.send_private_note(conversation_id, content)

    async def send_public_reply(self, conversation_id: str, content: str) -> None:
        await self._chatwoot.send_public_reply(conversation_id, content)

    async def send_interactive_message(
        self,
        conversation_id: str,
        content: str,
        content_type: str,
        content_attributes: dict[str, Any],
    ) -> None:
        await self._chatwoot.send_interactive_message(
            conversation_id,
            content,
            content_type,
            content_attributes,
        )

    async def handle_message(self, message: IncomingMessage, send_public_reply: bool = True) -> AgentResult:
        state = AgentState(message=message)

        state = await self._intent_router(state)
        state = await self._execute_domain_node(state)
        state = await self._confidence_guard(state)
        state = await self._finalize_action(state, send_public_reply=send_public_reply)

        action = AgentAction(
            type="handoff" if state.needs_human else "reply",
            reason=state.handoff_reason,
            private_note=state.private_note,
        )

        return AgentResult(
            conversation_id=message.conversation_id,
            intent=state.intent,
            confidence=state.confidence,
            reply=state.draft_reply,
            action=action,
            context_chunks=state.retrieved_chunks,
        )

    async def _intent_router(self, state: AgentState) -> AgentState:
        state.intent = await self._llm.classify_intent(state.message)

        angry_markers = ("投诉", "垃圾", "差评", "生气", "骗人", "退款不到账")
        if any(marker in state.message.content for marker in angry_markers):
            state.intent = Intent.HUMAN_HANDOFF
            state.needs_human = True
            state.handoff_reason = "检测到投诉或强负面情绪"

        return state

    async def _execute_domain_node(self, state: AgentState) -> AgentState:
        if state.needs_human or state.intent == Intent.HUMAN_HANDOFF:
            state.needs_human = True
            state.handoff_reason = state.handoff_reason or "用户明确要求人工客服"
            return state

        if state.intent in (Intent.FAQ, Intent.UNKNOWN):
            state.retrieved_chunks = await self._rag_store.search(
                query=state.message.content,
                user_level=state.message.user_level,
                limit=self._settings.max_context_chunks,
            )
            state.confidence = state.retrieved_chunks[0].score if state.retrieved_chunks else 0.0
            state.draft_reply = await self._llm.generate_answer(state.message, state.retrieved_chunks)
            return state

        if state.intent == Intent.BUSINESS:
            state.needs_human = True
            state.handoff_reason = "业务查询工具 API 尚未接入"
            return state

        state.confidence = 0.72
        state.draft_reply = "你好，我是 AI 助手。你可以直接告诉我遇到的问题，我会先帮你查资料。"
        return state

    async def _confidence_guard(self, state: AgentState) -> AgentState:
        if state.needs_human:
            return state

        if state.intent in (Intent.FAQ, Intent.UNKNOWN) and state.confidence < self._settings.rag_min_confidence:
            state.needs_human = True
            state.handoff_reason = f"知识库召回置信度过低：{state.confidence:.2f}"

        return state

    async def _finalize_action(self, state: AgentState, send_public_reply: bool = True) -> AgentState:
        if state.needs_human:
            state.private_note = await self._llm.summarize_handoff(state.message, state.handoff_reason)
            state.draft_reply = state.draft_reply or "这个问题需要人工客服进一步确认，我已经帮你转接。"
            await self._chatwoot.handoff_to_human(state.message.conversation_id, state.private_note)
            return state

        if send_public_reply:
            await self._chatwoot.send_public_reply(state.message.conversation_id, state.draft_reply)
        return state
