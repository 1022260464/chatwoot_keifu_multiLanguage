from __future__ import annotations

from typing import Any

from .clients import ChatwootGateway, LLMClient, RagStore
from .config import Settings
from .llm_response import sanitize_public_reply
from .schemas import AgentAction, AgentResult, AgentState, IncomingMessage, Intent
from .support_templates import PUBLIC_REPLY_FALLBACKS


_PUBLIC_REPLY_FALLBACK = PUBLIC_REPLY_FALLBACKS["vi"]
_UNMATCHED_FAQ_REPLY = (
    "Câu hỏi bạn nhập hiện không khớp với menu câu hỏi thường gặp, "
    "hiện tại trợ lý AI sẽ phục vụ bạn. Vui lòng mô tả chi tiết vấn đề của bạn, "
    "tôi sẽ cố gắng hết sức để hỗ trợ bạn."
)
_HANDOFF_PUBLIC_REPLY = (
    "Vấn đề này cần nhân viên hỗ trợ xác nhận thêm. "
    "Tôi đã chuyển cho nhân viên hỗ trợ, vui lòng chờ trong giây lát."
)
AI_HANDOFF_NOTE_PREFIX = "[AI handoff note]"


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

    async def update_conversation_custom_attributes(
        self,
        conversation_id: str,
        custom_attributes: dict[str, Any],
    ) -> None:
        await self._chatwoot.update_conversation_custom_attributes(conversation_id, custom_attributes)

    async def send_public_reply(self, conversation_id: str, content: str) -> None:
        public_reply = sanitize_public_reply(content) or _PUBLIC_REPLY_FALLBACK
        await self._chatwoot.send_public_reply(conversation_id, public_reply)

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

        angry_markers = (
            "complaint",
            "scam",
            "fraud",
            "refund",
            "khiếu nại",
            "lừa đảo",
            "gian lận",
            "hoàn tiền",
        )
        if any(marker in state.message.content.lower() for marker in angry_markers):
            state.intent = Intent.HUMAN_HANDOFF
            state.needs_human = True
            state.handoff_reason = "Detected complaint or high-risk negative sentiment"

        return state

    async def _execute_domain_node(self, state: AgentState) -> AgentState:
        if state.needs_human or state.intent == Intent.HUMAN_HANDOFF:
            state.needs_human = True
            state.handoff_reason = state.handoff_reason or "User explicitly requested human support"
            return state

        if state.intent in (Intent.FAQ, Intent.UNKNOWN):
            state.retrieved_chunks = await self._rag_store.search(
                query=state.message.content,
                user_level=state.message.user_level,
                limit=self._settings.max_context_chunks,
            )
            state.confidence = state.retrieved_chunks[0].score if state.retrieved_chunks else 0.0
            state.draft_reply = (
                sanitize_public_reply(await self._llm.generate_answer(state.message, state.retrieved_chunks))
                or _PUBLIC_REPLY_FALLBACK
            )
            return state

        if state.intent == Intent.BUSINESS:
            state.needs_human = True
            state.handoff_reason = "Business query API is not connected"
            return state

        state.confidence = 0.72
        state.draft_reply = _UNMATCHED_FAQ_REPLY
        return state

    async def _confidence_guard(self, state: AgentState) -> AgentState:
        if state.needs_human:
            return state

        if state.intent in (Intent.FAQ, Intent.UNKNOWN) and state.confidence < self._settings.rag_min_confidence:
            state.needs_human = True
            state.handoff_reason = f"Knowledge base confidence is too low: {state.confidence:.2f}"

        return state

    async def _finalize_action(self, state: AgentState, send_public_reply: bool = True) -> AgentState:
        if state.needs_human:
            handoff_summary = await self._llm.summarize_handoff(state.message, state.handoff_reason)
            state.private_note = f"{AI_HANDOFF_NOTE_PREFIX}\n{handoff_summary}"
            state.draft_reply = state.draft_reply or _HANDOFF_PUBLIC_REPLY
            await self._chatwoot.handoff_to_human(state.message.conversation_id, state.private_note)
            return state

        if send_public_reply:
            await self.send_public_reply(state.message.conversation_id, state.draft_reply)
        return state
