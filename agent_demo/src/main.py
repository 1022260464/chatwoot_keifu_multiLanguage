from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Request

from customer_agent.config import Settings
from customer_agent.factory import build_agent
from customer_agent.schemas import IncomingMessage


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
DEFAULT_PORT = 9090
SYNC_EVENTS = {
    "conversation_created",
    "conversation_status_changed",
    "conversation_updated",
    "message_created",
    "message_updated",
    "webwidget_triggered",
}

settings = Settings()
agent = build_agent(settings)

app = FastAPI(title="Chatwoot DeepSeek Agent Gateway")


async def process_message_task(incoming_message: IncomingMessage) -> None:
    try:
        logger.info("Processing Chatwoot conversation_id=%s", incoming_message.conversation_id)
        if settings.chatwoot_open_on_incoming:
            await agent.open_conversation(incoming_message.conversation_id)

        result = await agent.handle_message(incoming_message)
        logger.info(
            "Processed Chatwoot conversation_id=%s intent=%s action=%s",
            result.conversation_id,
            result.intent,
            result.action.type,
        )
    except Exception:
        logger.exception(
            "Failed to process Chatwoot conversation_id=%s",
            incoming_message.conversation_id,
        )


async def sync_chatwoot_event_task(payload: dict[str, Any]) -> None:
    event = str(payload.get("event") or "")
    conversation_id = _extract_conversation_id(payload)
    message_type = payload.get("message_type")
    sender = payload.get("sender") or {}
    sender_type = sender.get("type")
    sync_payload = _build_admin_sync_payload(payload)

    logger.info(
        "Synced Chatwoot event=%s conversation_id=%s message_type=%s sender_type=%s",
        event,
        conversation_id or "unknown",
        message_type or "unknown",
        sender_type or "unknown",
    )
    await _forward_to_admin_backend(sync_payload)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/chatwoot")
async def chatwoot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Ignored Chatwoot webhook with invalid JSON")
        return {"status": "error", "reason": "Invalid JSON"}

    event = str(payload.get("event") or "")
    if event not in SYNC_EVENTS:
        logger.info("Ignored unsupported Chatwoot event=%s", event or "unknown")
        return {"status": "ignored", "reason": "Unsupported event"}

    background_tasks.add_task(sync_chatwoot_event_task, payload)

    agent_ignore_reason = _get_agent_ignore_reason(payload)
    if agent_ignore_reason:
        logger.info("Skipped Agent processing reason=%s", agent_ignore_reason)
        return {"status": "synced", "agent": "skipped", "reason": agent_ignore_reason}

    incoming_message = _to_incoming_message(payload)
    if incoming_message is None:
        logger.warning("Skipped Agent processing because required fields are missing")
        return {"status": "synced", "agent": "skipped", "reason": "Missing required fields"}

    logger.info(
        "Queued Agent processing conversation_id=%s contact_id=%s content=%s",
        incoming_message.conversation_id,
        incoming_message.contact_id,
        incoming_message.content[:40],
    )
    background_tasks.add_task(process_message_task, incoming_message)
    return {"status": "synced", "agent": "queued"}


def _get_agent_ignore_reason(payload: dict[str, Any]) -> str:
    if payload.get("event") != "message_created":
        return "Not a message_created event"

    if payload.get("message_type") != "incoming":
        return "Not an incoming user message"

    if payload.get("private"):
        return "Private note"

    if not str(payload.get("content") or "").strip():
        return "Empty content"

    return ""


def _to_incoming_message(payload: dict[str, Any]) -> IncomingMessage | None:
    content = str(payload.get("content") or "").strip()
    conversation = payload.get("conversation") or {}
    sender = payload.get("sender") or {}

    conversation_id = _extract_conversation_id(payload)
    contact_id = _string_id(
        sender.get("id")
        or payload.get("sender_id")
        or conversation.get("contact_id")
        or "unknown"
    )
    if not conversation_id or not content:
        return None

    custom_attributes = conversation.get("custom_attributes") or {}
    contact_custom_attributes = sender.get("custom_attributes") or {}
    user_level = str(
        custom_attributes.get("user_level")
        or contact_custom_attributes.get("user_level")
        or "all"
    )

    return IncomingMessage(
        conversation_id=conversation_id,
        contact_id=contact_id,
        content=content,
        user_level=user_level,
        metadata={
            "chatwoot_message_id": payload.get("id"),
            "chatwoot_inbox_id": payload.get("inbox_id"),
            "chatwoot_account_id": payload.get("account", {}).get("id"),
        },
    )


def _build_admin_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    conversation = payload.get("conversation") or {}
    sender = payload.get("sender") or {}
    account = payload.get("account") or {}

    return {
        "source": "chatwoot",
        "event": payload.get("event"),
        "message_id": payload.get("id"),
        "message_type": payload.get("message_type"),
        "private": bool(payload.get("private")),
        "content": payload.get("content"),
        "created_at": payload.get("created_at"),
        "conversation": {
            "id": _extract_conversation_id(payload),
            "status": conversation.get("status"),
            "inbox_id": conversation.get("inbox_id") or payload.get("inbox_id"),
            "contact_id": conversation.get("contact_id"),
            "custom_attributes": conversation.get("custom_attributes") or {},
        },
        "sender": {
            "id": _string_id(sender.get("id") or payload.get("sender_id")),
            "type": sender.get("type"),
            "name": sender.get("name"),
            "email": sender.get("email"),
            "custom_attributes": sender.get("custom_attributes") or {},
        },
        "account": {
            "id": account.get("id"),
            "name": account.get("name"),
        },
        "raw": payload,
    }


async def _forward_to_admin_backend(payload: dict[str, Any]) -> None:
    if not settings.admin_webhook_url:
        logger.info("ADMIN_WEBHOOK_URL is empty; Chatwoot event was not forwarded")
        return

    def send() -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if settings.admin_webhook_token:
            headers["Authorization"] = f"Bearer {settings.admin_webhook_token}"

        req = request.Request(
            settings.admin_webhook_url,
            data=body,
            method="POST",
            headers=headers,
        )
        try:
            with request.urlopen(req, timeout=10) as response:
                response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Admin webhook error {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Admin webhook request failed: {exc.reason}") from exc

    try:
        await asyncio.to_thread(send)
        logger.info("Forwarded Chatwoot event to admin backend")
    except Exception:
        logger.exception("Failed to forward Chatwoot event to admin backend")


def _extract_conversation_id(payload: dict[str, Any]) -> str:
    conversation = payload.get("conversation") or {}
    return _string_id(conversation.get("id") or payload.get("conversation_id"))


def _string_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=DEFAULT_PORT, reload=True)
