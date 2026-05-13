from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

import uvicorn
from fastapi import FastAPI, Request

from customer_agent.config import Settings
from customer_agent.factory import build_agent
from customer_agent.schemas import IncomingMessage
from customer_agent.translator import (
    PrivateNoteTranslator,
    contains_chinese,
    get_translation_skip_reason,
    guess_language,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
DEFAULT_PORT = 9090
SYNC_EVENTS = {
    "conversation_created",
    "conversation_status_changed",
    "conversation_updated",
    "message_created",
    "message_updated",
    "conversation_opened",
    "webwidget_triggered",
}

settings = Settings()
agent = build_agent(settings)
translator = PrivateNoteTranslator(settings)
conversation_languages: dict[str, str] = {}
conversation_locks: dict[str, asyncio.Lock] = {}

app = FastAPI(title="Chatwoot DeepSeek Agent Gateway")


def _spawn_task(coro: Any, task_name: str) -> None:
    task = asyncio.create_task(coro)
    task.add_done_callback(lambda done: _log_task_result(done, task_name))


def _log_task_result(task: asyncio.Task[Any], task_name: str) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.warning("Background task was cancelled task=%s", task_name)
    except Exception:
        logger.exception("Background task failed task=%s", task_name)


async def handle_incoming_message_task(payload: dict[str, Any], incoming_message: IncomingMessage) -> None:
    conversation_id = incoming_message.conversation_id
    async with _conversation_lock(conversation_id):
        await translate_private_note_task(payload)
        await process_message_task(incoming_message)


def _conversation_lock(conversation_id: str) -> asyncio.Lock:
    lock = conversation_locks.get(conversation_id)
    if lock is None:
        lock = asyncio.Lock()
        conversation_locks[conversation_id] = lock
    return lock


async def process_message_task(incoming_message: IncomingMessage) -> None:
    try:
        logger.info("Processing Chatwoot conversation_id=%s", incoming_message.conversation_id)
        if settings.chatwoot_open_on_incoming:
            await agent.open_conversation(incoming_message.conversation_id)

        user_language = await _resolve_user_language(incoming_message)
        should_translate_reply = (
            settings.translation_outgoing_enabled
            and user_language
            and not _is_chinese_language(user_language)
        )
        result = await agent.handle_message(
            incoming_message,
            send_public_reply=not should_translate_reply,
        )

        if should_translate_reply and result.action.type == "reply":
            translated_reply = await asyncio.wait_for(
                translator.translate(result.reply, target=user_language),
                timeout=settings.translation_timeout_seconds,
            )
            if translated_reply:
                await agent.send_public_reply(incoming_message.conversation_id, translated_reply)
                await agent.send_private_note(
                    incoming_message.conversation_id,
                    f"[Original AI reply]\n{result.reply}",
                )
                logger.info(
                    "Sent translated Agent reply conversation_id=%s target_language=%s",
                    incoming_message.conversation_id,
                    user_language,
                )
            else:
                logger.warning(
                    "Translated Agent reply was empty; original reply was not sent conversation_id=%s",
                    incoming_message.conversation_id,
                )

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


async def translate_private_note_task(payload: dict[str, Any]) -> None:
    content = str(payload.get("content") or "").strip()
    if not _is_contact_incoming_message(payload):
        logger.info(
            "Translation skipped because payload is not a public contact incoming message: "
            "event=%s message_type=%s private=%s sender_type=%s",
            payload.get("event"),
            payload.get("message_type"),
            payload.get("private"),
            _extract_sender_type(payload) or "unknown",
        )
        return

    conversation_id = _extract_conversation_id(payload)
    if not conversation_id:
        logger.warning("Translation skipped because conversation_id is missing")
        return

    try:
        if settings.translation_private_note_enabled or settings.translation_outgoing_enabled:
            detected_language = await asyncio.wait_for(
                translator.detect_language(content),
                timeout=settings.translation_timeout_seconds,
            )
            if detected_language:
                conversation_languages[conversation_id] = detected_language
                logger.info(
                    "Detected conversation language conversation_id=%s language=%s",
                    conversation_id,
                    detected_language,
                )

        skip_reason = get_translation_skip_reason(content, settings)
        if skip_reason:
            logger.info("Translation skipped reason=%s", skip_reason)
            return

        translated_text = await asyncio.wait_for(
            translator.translate_to_target(content),
            timeout=settings.translation_timeout_seconds,
        )
        if not translated_text:
            logger.warning("Translation skipped because translated text is empty")
            return

        await agent.send_private_note(
            conversation_id,
            f"[AI translation]\n{translated_text}",
        )
        logger.info("Sent translation private note conversation_id=%s", conversation_id)
    except TimeoutError:
        logger.warning("Translation timed out conversation_id=%s", conversation_id)
    except Exception:
        logger.exception("Failed to create translation private note conversation_id=%s", conversation_id)


async def translate_outgoing_to_user_language_task(payload: dict[str, Any]) -> None:
    if not settings.translation_outgoing_enabled:
        return

    if not _is_translatable_outgoing_message(payload):
        return

    content = str(payload.get("content") or "").strip()
    if not contains_chinese(content):
        return

    conversation_id = _extract_conversation_id(payload)
    if not conversation_id:
        logger.warning("Outgoing translation skipped because conversation_id is missing")
        return

    target_language = conversation_languages.get(conversation_id) or settings.translation_default_user_lang
    if not target_language:
        logger.info("Outgoing translation skipped because no user language is known")
        return

    if target_language.lower() in ("zh", "zh-cn", "zh-tw", "zh-hans", "zh-hant"):
        logger.info("Outgoing translation skipped because target language is Chinese")
        return

    try:
        translated_text = await asyncio.wait_for(
            translator.translate(content, target=target_language),
            timeout=settings.translation_timeout_seconds,
        )
        if not translated_text:
            logger.warning("Outgoing translation skipped because translated text is empty")
            return

        if not payload.get("private"):
            await agent.send_private_note(
                conversation_id,
                f"[Auto translated to {target_language}]\n{translated_text}",
            )
        await agent.send_public_reply(conversation_id, translated_text)
        logger.info(
            "Sent outgoing translation conversation_id=%s target_language=%s",
            conversation_id,
            target_language,
        )
    except TimeoutError:
        logger.warning("Outgoing translation timed out conversation_id=%s", conversation_id)
    except Exception:
        logger.exception("Failed to translate outgoing message conversation_id=%s", conversation_id)


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

    _spawn_task(sync_chatwoot_event_task(payload), "sync_chatwoot_event")

    agent_ignore_reason = _get_agent_ignore_reason(payload)
    if agent_ignore_reason:
        logger.info("Skipped Agent processing reason=%s", agent_ignore_reason)
        _spawn_task(translate_outgoing_to_user_language_task(payload), "translate_outgoing")
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
    _spawn_task(handle_incoming_message_task(payload, incoming_message), "handle_incoming_message")
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


def _is_contact_incoming_message(payload: dict[str, Any]) -> bool:
    sender_type = _extract_sender_type(payload).lower()
    if payload.get("event") != "message_created":
        return False

    # Chatwoot's incoming message_type is the reliable signal for visitor
    # messages. Some webhook payloads omit sender.type, so treat unknown sender
    # type as acceptable here while still rejecting user/bot outgoing messages.
    if payload.get("message_type") != "incoming":
        return False

    if payload.get("private"):
        return False

    if sender_type and sender_type not in ("contact", "contact_inbox", "unknown"):
        return False

    return bool(str(payload.get("content") or "").strip())


def _is_public_outgoing_message(payload: dict[str, Any]) -> bool:
    return (
        payload.get("event") == "message_created"
        and payload.get("message_type") == "outgoing"
        and not payload.get("private")
        and bool(str(payload.get("content") or "").strip())
    )


def _is_translatable_outgoing_message(payload: dict[str, Any]) -> bool:
    if payload.get("event") != "message_created":
        return False

    if payload.get("message_type") != "outgoing":
        return False

    content = str(payload.get("content") or "").strip()
    if not content:
        return False

    # Do not translate notes created by this gateway, otherwise private-note
    # audit messages can become public replies and create confusing duplicates.
    system_prefixes = (
        "[AI translation]",
        "[Original AI reply]",
        "[Auto translated to",
    )
    if any(content.startswith(prefix) for prefix in system_prefixes):
        return False

    return True


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
            "user_language": guess_language(content),
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


def _extract_sender_type(payload: dict[str, Any]) -> str:
    sender = payload.get("sender") or {}
    return _string_id(sender.get("type") or payload.get("sender_type"))


async def _resolve_user_language(message: IncomingMessage) -> str:
    known_language = conversation_languages.get(message.conversation_id)
    if known_language:
        return known_language

    guessed_language = str(message.metadata.get("user_language") or "")
    if guessed_language:
        conversation_languages[message.conversation_id] = guessed_language
        return guessed_language

    if not settings.translation_outgoing_enabled:
        return ""

    try:
        detected_language = await asyncio.wait_for(
            translator.detect_language(message.content),
            timeout=settings.translation_timeout_seconds,
        )
    except TimeoutError:
        logger.warning("Language detection timed out conversation_id=%s", message.conversation_id)
        return ""

    if detected_language:
        conversation_languages[message.conversation_id] = detected_language
        logger.info(
            "Detected conversation language conversation_id=%s language=%s",
            message.conversation_id,
            detected_language,
        )
    return detected_language


def _is_chinese_language(language: str) -> bool:
    return language.lower() in ("zh", "zh-cn", "zh-tw", "zh-hans", "zh-hant")


def _string_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=DEFAULT_PORT, reload=True)
