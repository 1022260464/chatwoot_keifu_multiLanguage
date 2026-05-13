from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Intent(StrEnum):
    CHITCHAT = "chitchat"
    FAQ = "faq"
    BUSINESS = "business"
    COMPLAINT = "complaint"
    HUMAN_HANDOFF = "human_handoff"
    UNKNOWN = "unknown"


class IncomingMessage(BaseModel):
    conversation_id: str
    contact_id: str
    content: str
    user_level: str = "all"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentAction(BaseModel):
    type: Literal["reply", "handoff", "ignore"]
    reason: str = ""
    private_note: str = ""


class AgentResult(BaseModel):
    conversation_id: str
    intent: Intent
    confidence: float
    reply: str
    action: AgentAction
    context_chunks: list[RetrievedChunk] = Field(default_factory=list)


class AgentState(BaseModel):
    message: IncomingMessage
    intent: Intent = Intent.UNKNOWN
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    confidence: float = 0.0
    draft_reply: str = ""
    needs_human: bool = False
    handoff_reason: str = ""
    private_note: str = ""
