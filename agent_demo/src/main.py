from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

import uvicorn
from fastapi import FastAPI, Request

from customer_agent.config import Settings
from customer_agent.dashboard import build_dashboard_router
from customer_agent.factory import build_agent
from customer_agent.faq_config import (
    find_faq_command,
    get_faq_answer,
    get_faq_intro,
    get_faq_menu_text,
    is_faq_menu_trigger,
    is_supported_faq_language,
    normalize_faq_language,
)
from customer_agent.message_guard import GuardResult, inspect_message
from customer_agent.schemas import IncomingMessage
from customer_agent.support_templates import PUBLIC_REPLY_FALLBACKS
from customer_agent.translator import (
    PrivateNoteTranslator,
    contains_chinese,
    get_translation_skip_reason,
    guess_language,
)
from customer_agent.workflow import AI_HANDOFF_NOTE_PREFIX


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
DEFAULT_PORT = 9090
AI_GUARD_NOTE_PREFIX = "[AI guard note]"
AI_HANDOFF_CUSTOM_ATTRIBUTE = "ai_handoff"
AI_HANDOFF_REASON_CUSTOM_ATTRIBUTE = "ai_handoff_reason"
AI_HANDOFF_AT_CUSTOM_ATTRIBUTE = "ai_handoff_at"
AI_UNMATCHED_FALLBACK_REPLY_PREFIXES = (
    "Cau hoi ban nhap hien khong khop voi menu cau hoi thuong gap",
    "Câu hỏi bạn nhập hiện không khớp với menu câu hỏi thường gặp",
)
ATTACHMENT_MESSAGE_PLACEHOLDER = "[attachment]"
IMAGE_MESSAGE_PLACEHOLDER = "[attachment:image]"
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
faq_menu_sent_conversations: set[str] = set()
human_handoff_conversations: set[str] = set()
ai_fallback_replied_conversations: set[str] = set()

app = FastAPI(title="Chatwoot DeepSeek Agent Gateway")
app.include_router(build_dashboard_router(settings, agent, translator))


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
        if _is_conversation_handed_off(conversation_id):
            logger.info("Skipped Agent processing because conversation already handed off conversation_id=%s", conversation_id)
            return
        user_language = await _resolve_user_language(incoming_message)
        guarded_message = await apply_message_guard_task(incoming_message, user_language)
        if guarded_message:
            await process_message_task(guarded_message)


async def handle_faq_command_task(conversation_id: str, answer: str) -> None:
    try:
        logger.info("Handling FAQ command conversation_id=%s", conversation_id)
        if settings.chatwoot_open_on_incoming:
            await agent.open_conversation(conversation_id)
        await _send_public_reply(conversation_id, answer)
    except Exception:
        logger.exception("Failed to handle FAQ command conversation_id=%s", conversation_id)


async def send_standard_faq_menu_task(conversation_id: str, language: str = "") -> None:
    if conversation_id in faq_menu_sent_conversations:
        logger.info("FAQ menu already sent conversation_id=%s", conversation_id)
        return

    try:
        public_language = _public_template_language(conversation_id, language)
        logger.info("Sending FAQ menu conversation_id=%s language=%s", conversation_id, public_language)
        await _send_public_reply(conversation_id, get_faq_intro(public_language), public_language)
        await _send_public_reply(conversation_id, get_faq_menu_text(public_language), public_language)
        faq_menu_sent_conversations.add(conversation_id)
    except Exception:
        logger.exception("Failed to send FAQ menu conversation_id=%s", conversation_id)


async def handle_first_incoming_faq_menu_task(
    payload: dict[str, Any],
    incoming_message: IncomingMessage,
) -> None:
    conversation_id = incoming_message.conversation_id
    async with _conversation_lock(conversation_id):
        await translate_private_note_task(payload)
        if _is_conversation_handed_off(conversation_id):
            logger.info("Skipped first-message automation because conversation already handed off conversation_id=%s", conversation_id)
            return
        user_language = await _resolve_user_language(incoming_message)
        menu_sent = False
        if is_supported_faq_language(user_language):
            await send_standard_faq_menu_task(conversation_id, user_language)
            menu_sent = True

        guarded_message = await apply_message_guard_task(
            incoming_message,
            user_language,
            suppress_low_value_reply=menu_sent,
        )
        if guarded_message is None:
            return

        if menu_sent:
            return

        logger.info(
            "FAQ menu skipped because language is not supported conversation_id=%s language=%s",
            conversation_id,
            user_language or "unknown",
        )
        await process_message_task(guarded_message)


async def apply_message_guard_task(
    incoming_message: IncomingMessage,
    user_language: str,
    suppress_low_value_reply: bool = False,
) -> IncomingMessage | None:
    guard_result = inspect_message(incoming_message.content, user_language)
    if guard_result.action == "reply":
        if guard_result.reason == "low_value_message" and suppress_low_value_reply:
            logger.info(
                "Message guard low-value reply skipped because initial FAQ menu was sent conversation_id=%s",
                incoming_message.conversation_id,
            )
            return None
        logger.info(
            "Message guard replied conversation_id=%s reason=%s",
            incoming_message.conversation_id,
            guard_result.reason,
        )
        await _send_public_reply(incoming_message.conversation_id, guard_result.reply, user_language)
        if guard_result.reason == "low_value_message":
            await send_standard_faq_menu_task(incoming_message.conversation_id, user_language)
        return None

    if guard_result.action == "handoff":
        await _mark_conversation_handoff(incoming_message.conversation_id, guard_result.reason)
        logger.info(
            "Message guard handed off conversation_id=%s reason=%s",
            incoming_message.conversation_id,
            guard_result.reason,
        )
        if guard_result.private_note:
            await agent.send_private_note(
                incoming_message.conversation_id,
                f"{AI_GUARD_NOTE_PREFIX}\n{guard_result.private_note}",
            )
        await agent.open_conversation(incoming_message.conversation_id)
        await _send_public_reply(incoming_message.conversation_id, guard_result.reply, user_language)
        return None

    if guard_result.private_note:
        await agent.send_private_note(
            incoming_message.conversation_id,
            f"{AI_GUARD_NOTE_PREFIX}\n{guard_result.private_note}",
        )

    if guard_result.sanitized_content and guard_result.sanitized_content != incoming_message.content:
        logger.info(
            "Message guard sanitized content conversation_id=%s reason=%s",
            incoming_message.conversation_id,
            guard_result.reason,
        )
        return _copy_incoming_message(incoming_message, guard_result)

    return incoming_message


def _conversation_lock(conversation_id: str) -> asyncio.Lock:
    lock = conversation_locks.get(conversation_id)
    if lock is None:
        lock = asyncio.Lock()
        conversation_locks[conversation_id] = lock
    return lock


def _is_unmatched_fallback_reply(reply: str) -> bool:
    normalized_reply = reply.strip()
    return any(normalized_reply.startswith(prefix) for prefix in AI_UNMATCHED_FALLBACK_REPLY_PREFIXES)


def _mark_ai_fallback_replied(conversation_id: str, reply: str) -> None:
    if _is_unmatched_fallback_reply(reply):
        ai_fallback_replied_conversations.add(conversation_id)


async def _mark_conversation_handoff(conversation_id: str, reason: str = "") -> None:
    human_handoff_conversations.add(conversation_id)
    try:
        await agent.update_conversation_custom_attributes(
            conversation_id,
            {
                AI_HANDOFF_CUSTOM_ATTRIBUTE: True,
                AI_HANDOFF_REASON_CUSTOM_ATTRIBUTE: reason,
                AI_HANDOFF_AT_CUSTOM_ATTRIBUTE: datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        logger.exception("Failed to persist handoff custom attribute conversation_id=%s", conversation_id)


def _sync_handoff_state_from_payload(conversation_id: str, payload: dict[str, Any]) -> None:
    if not conversation_id:
        return

    custom_attributes = _conversation_custom_attributes(payload)
    if AI_HANDOFF_CUSTOM_ATTRIBUTE not in custom_attributes:
        return

    if _is_truthy_custom_attribute(custom_attributes.get(AI_HANDOFF_CUSTOM_ATTRIBUTE)):
        human_handoff_conversations.add(conversation_id)
    else:
        human_handoff_conversations.discard(conversation_id)


def _is_conversation_handed_off(conversation_id: str) -> bool:
    return conversation_id in human_handoff_conversations


def _conversation_custom_attributes(payload: dict[str, Any]) -> dict[str, Any]:
    conversation = payload.get("conversation") or {}
    attributes = conversation.get("custom_attributes") or {}
    return attributes if isinstance(attributes, dict) else {}


def _is_truthy_custom_attribute(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return False


async def _send_public_reply(
    conversation_id: str,
    content: str,
    target_language: str = "",
) -> None:
    public_text = await _ensure_public_text(conversation_id, content, target_language)
    await agent.send_public_reply(conversation_id, public_text)


async def _ensure_public_text(
    conversation_id: str,
    content: str,
    target_language: str = "",
) -> str:
    public_text = str(content or "").strip()
    if not public_text:
        return _public_reply_fallback_text()

    if not contains_chinese(public_text):
        return public_text

    public_language = _resolve_public_target_language(conversation_id, target_language)
    try:
        translated_text = await asyncio.wait_for(
            translator.translate(public_text, target=public_language),
            timeout=settings.translation_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "Public reply translation timed out; trying DeepSeek conversation_id=%s target_language=%s",
            conversation_id,
            public_language,
        )
        deepseek_translated_text = await _translate_public_reply_with_deepseek(
            conversation_id,
            public_text,
            public_language,
        )
        if deepseek_translated_text:
            return deepseek_translated_text
        return _public_reply_fallback_text()
    except Exception:
        logger.exception(
            "Public reply translation failed; trying DeepSeek conversation_id=%s target_language=%s",
            conversation_id,
            public_language,
        )
        deepseek_translated_text = await _translate_public_reply_with_deepseek(
            conversation_id,
            public_text,
            public_language,
        )
        if deepseek_translated_text:
            return deepseek_translated_text
        return _public_reply_fallback_text()

    if translated_text and not contains_chinese(translated_text):
        logger.info(
            "Translated Chinese public reply before sending conversation_id=%s target_language=%s",
            conversation_id,
            public_language,
        )
        return translated_text

    logger.warning(
        "Public reply translation returned empty or Chinese text; trying DeepSeek conversation_id=%s target_language=%s",
        conversation_id,
        public_language,
    )
    deepseek_translated_text = await _translate_public_reply_with_deepseek(
        conversation_id,
        public_text,
        public_language,
    )
    if deepseek_translated_text:
        return deepseek_translated_text

    return _public_reply_fallback_text()


async def _translate_public_reply_with_deepseek(
    conversation_id: str,
    content: str,
    target_language: str,
) -> str:
    if not settings.deepseek_api_key:
        logger.warning("Public reply DeepSeek fallback skipped because DEEPSEEK_API_KEY is empty conversation_id=%s", conversation_id)
        return ""

    try:
        translated_text = await asyncio.wait_for(
            translator.translate_with_deepseek(content, target=target_language),
            timeout=settings.translation_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "Public reply DeepSeek fallback timed out conversation_id=%s target_language=%s",
            conversation_id,
            target_language,
        )
        return ""
    except Exception:
        logger.exception(
            "Public reply DeepSeek fallback failed conversation_id=%s target_language=%s",
            conversation_id,
            target_language,
        )
        return ""

    if translated_text and not contains_chinese(translated_text):
        logger.info(
            "Translated Chinese public reply with DeepSeek fallback conversation_id=%s target_language=%s",
            conversation_id,
            target_language,
        )
        return translated_text

    logger.warning(
        "Public reply DeepSeek fallback returned empty or Chinese text conversation_id=%s target_language=%s",
        conversation_id,
        target_language,
    )
    return ""


def _public_template_language(conversation_id: str, language: str = "") -> str:
    public_language = _resolve_public_target_language(conversation_id, language)
    normalized_language = normalize_faq_language(public_language)
    if normalized_language and normalized_language != "zh":
        return normalized_language

    fallback_language = normalize_faq_language(settings.public_reply_fallback_language)
    if fallback_language and fallback_language != "zh":
        return fallback_language

    return "vi"


def _resolve_public_target_language(conversation_id: str, target_language: str = "") -> str:
    language = (
        str(target_language or "").strip()
        or conversation_languages.get(conversation_id, "")
        or settings.translation_default_user_lang.strip()
        or settings.public_reply_fallback_language.strip()
        or "vi"
    )
    if _is_chinese_language(language):
        fallback_language = settings.public_reply_fallback_language.strip() or "vi"
        if _is_chinese_language(fallback_language):
            return "vi"
        return fallback_language
    return language


def _public_reply_fallback_text() -> str:
    language = settings.public_reply_fallback_language.strip().lower()
    return PUBLIC_REPLY_FALLBACKS.get(language) or PUBLIC_REPLY_FALLBACKS["vi"]


async def process_message_task(incoming_message: IncomingMessage) -> None:
    conversation_id = incoming_message.conversation_id
    if _is_conversation_handed_off(conversation_id):
        logger.info("Skipped Agent processing because conversation already handed off conversation_id=%s", conversation_id)
        return

    try:
        logger.info("Processing Chatwoot conversation_id=%s", conversation_id)
        if settings.chatwoot_open_on_incoming:
            await agent.open_conversation(conversation_id)

        user_language = await _resolve_user_language(incoming_message)
        result = await agent.handle_message(
            incoming_message,
            send_public_reply=False,
        )

        if result.action.type == "handoff":
            await _mark_conversation_handoff(conversation_id, result.action.reason)
            logger.info("Marked conversation as handed off conversation_id=%s reason=%s", conversation_id, result.action.reason)
        elif result.action.type == "reply":
            if _is_unmatched_fallback_reply(result.reply) and conversation_id in ai_fallback_replied_conversations:
                logger.info("Skipped repeated unmatched fallback reply conversation_id=%s", conversation_id)
            else:
                await _send_public_reply(conversation_id, result.reply, user_language)
                _mark_ai_fallback_replied(conversation_id, result.reply)

        logger.info(
            "Processed Chatwoot conversation_id=%s intent=%s action=%s",
            result.conversation_id,
            result.intent,
            result.action.type,
        )
    except Exception:
        logger.exception(
            "Failed to process Chatwoot conversation_id=%s",
            conversation_id,
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
        configured_language = _configured_channel_language(payload)
        if _uses_inbox_language():
            if not configured_language:
                logger.warning(
                    "No configured channel language found while CHATWOOT_LANGUAGE_SOURCE=inbox "
                    "conversation_id=%s",
                    conversation_id,
                )
                await _detect_and_cache_conversation_language(conversation_id, content)
            else:
                conversation_languages[conversation_id] = configured_language
                logger.info(
                    "Using configured channel language conversation_id=%s language=%s",
                    conversation_id,
                    configured_language,
                )
        if not content:
            logger.info("Translation skipped reason=Empty content")
            return

        if not _uses_inbox_language() and (
            settings.translation_private_note_enabled or settings.translation_outgoing_enabled
        ):
            await _detect_and_cache_conversation_language(conversation_id, content)

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

        await _send_public_reply(conversation_id, translated_text, target_language)
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

    conversation_id = _extract_conversation_id(payload)
    configured_language = _configured_channel_language(payload)
    if conversation_id and configured_language:
        conversation_languages[conversation_id] = configured_language
    _sync_handoff_state_from_payload(conversation_id, payload)

    _spawn_task(sync_chatwoot_event_task(payload), "sync_chatwoot_event")

    if event in ("webwidget_triggered", "conversation_created"):
        if conversation_id and _is_conversation_handed_off(conversation_id):
            logger.info("Skipped FAQ menu because conversation already handed off conversation_id=%s", conversation_id)
            return {"status": "synced", "agent": "skipped", "reason": "Conversation already handed off"}

        language = conversation_languages.get(conversation_id)
        if conversation_id and is_supported_faq_language(language):
            _spawn_task(send_standard_faq_menu_task(conversation_id, language), "send_faq_menu")
            return {"status": "synced", "agent": "faq_menu_queued"}
        logger.warning(
            "Skipped FAQ menu because conversation_id or language is missing event=%s conversation_id=%s language=%s",
            event,
            conversation_id or "unknown",
            language or "unknown",
        )

    if conversation_id and _is_conversation_handed_off(conversation_id) and _is_contact_incoming_message(payload):
        logger.info("Skipped automated handling because conversation already handed off conversation_id=%s", conversation_id)
        _spawn_task(translate_private_note_task(payload), "translate_private_note_after_handoff")
        return {"status": "synced", "agent": "skipped", "reason": "Conversation already handed off"}

    submitted_faq_command = _extract_faq_command(payload)
    if submitted_faq_command:
        conversation_id = _extract_conversation_id(payload)
        if conversation_id and _is_conversation_handed_off(conversation_id):
            logger.info(
                "Skipped FAQ command because conversation already handed off conversation_id=%s command=%s",
                conversation_id,
                submitted_faq_command,
            )
            return {"status": "synced", "agent": "skipped", "reason": "Conversation already handed off"}
        if conversation_id:
            faq_answer = get_faq_answer(submitted_faq_command, conversation_languages.get(conversation_id, ""))
            if faq_answer:
                logger.info(
                    "Queued FAQ command from Chatwoot submission conversation_id=%s command=%s",
                    conversation_id,
                    submitted_faq_command,
                )
                _spawn_task(
                    handle_faq_command_task(conversation_id, faq_answer),
                    "handle_faq_command",
                )
                return {"status": "synced", "agent": "faq_handled"}
        logger.warning("FAQ command was submitted but conversation_id is missing command=%s", submitted_faq_command)

    agent_ignore_reason = _get_agent_ignore_reason(payload)
    if agent_ignore_reason:
        logger.info("Skipped Agent processing reason=%s", agent_ignore_reason)
        _spawn_task(translate_outgoing_to_user_language_task(payload), "translate_outgoing")
        return {"status": "synced", "agent": "skipped", "reason": agent_ignore_reason}

    incoming_message = _to_incoming_message(payload)
    if incoming_message is None:
        logger.warning("Skipped Agent processing because required fields are missing")
        return {"status": "synced", "agent": "skipped", "reason": "Missing required fields"}

    faq_command = _extract_faq_command(payload, incoming_message.content)
    faq_language = _known_or_guessed_language(incoming_message)
    faq_answer = get_faq_answer(faq_command, faq_language)
    if faq_answer:
        _spawn_task(
            handle_faq_command_task(incoming_message.conversation_id, faq_answer),
            "handle_faq_command",
        )
        return {"status": "synced", "agent": "faq_handled"}

    if is_faq_menu_trigger(incoming_message.content):
        _spawn_task(
            handle_first_incoming_faq_menu_task(payload, incoming_message),
            "send_faq_menu",
        )
        return {"status": "synced", "agent": "faq_menu_queued"}

    if incoming_message.conversation_id not in faq_menu_sent_conversations:
        _spawn_task(
            handle_first_incoming_faq_menu_task(payload, incoming_message),
            "send_faq_menu",
        )
        return {"status": "synced", "agent": "faq_menu_queued"}

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

    if (
        not str(payload.get("content") or "").strip()
        and not _extract_faq_command(payload)
        and not _has_message_attachments(payload)
    ):
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

    return bool(str(payload.get("content") or "").strip() or _has_message_attachments(payload))


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

    if not payload.get("private"):
        return False

    content = str(payload.get("content") or "").strip()
    if not content:
        return False

    # Human agents use private notes as Chinese drafts for visitor-facing
    # translations. Public outgoing messages are already visible to visitors,
    # so translating them again would duplicate replies and can self-trigger.
    system_prefixes = (
        "[AI translation]",
        AI_HANDOFF_NOTE_PREFIX,
        AI_GUARD_NOTE_PREFIX,
        "[Original AI reply]",
        "[Auto translated to",
    )
    if any(content.startswith(prefix) for prefix in system_prefixes):
        return False

    return True


def _extract_message_attachments(payload: dict[str, Any]) -> list[Any]:
    message = payload.get("message")
    candidates = [
        payload.get("attachments"),
        message.get("attachments") if isinstance(message, dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate
    return []


def _has_message_attachments(payload: dict[str, Any]) -> bool:
    return bool(_extract_message_attachments(payload))


def _attachment_content_placeholder(payload: dict[str, Any]) -> str:
    for attachment in _extract_message_attachments(payload):
        if not isinstance(attachment, dict):
            continue
        file_type = str(
            attachment.get("file_type")
            or attachment.get("fileType")
            or attachment.get("type")
            or ""
        ).lower()
        content_type = str(
            attachment.get("content_type")
            or attachment.get("contentType")
            or attachment.get("mime_type")
            or attachment.get("mimeType")
            or ""
        ).lower()
        if file_type == "image" or content_type.startswith("image/"):
            return IMAGE_MESSAGE_PLACEHOLDER
    return ATTACHMENT_MESSAGE_PLACEHOLDER


def _attachment_types(payload: dict[str, Any]) -> list[str]:
    attachment_types: list[str] = []
    for attachment in _extract_message_attachments(payload):
        if not isinstance(attachment, dict):
            continue
        attachment_type = str(
            attachment.get("file_type")
            or attachment.get("fileType")
            or attachment.get("type")
            or attachment.get("content_type")
            or attachment.get("mime_type")
            or "unknown"
        ).strip()
        if attachment_type:
            attachment_types.append(attachment_type)
    return attachment_types


def _to_incoming_message(payload: dict[str, Any]) -> IncomingMessage | None:
    content = str(payload.get("content") or "").strip()
    is_attachment_only = False
    faq_command = _extract_faq_command(payload)
    if not content and faq_command:
        content = faq_command
    elif not content and _has_message_attachments(payload):
        content = _attachment_content_placeholder(payload)
        is_attachment_only = True
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

    configured_language = _configured_channel_language(payload)
    custom_attributes = _conversation_custom_attributes(payload)
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
            "configured_language": configured_language,
            "ai_handoff": _is_truthy_custom_attribute(custom_attributes.get(AI_HANDOFF_CUSTOM_ATTRIBUTE)),
            "attachment_count": len(_extract_message_attachments(payload)),
            "attachment_types": _attachment_types(payload),
            "user_language": "" if _uses_inbox_language() or is_attachment_only else guess_language(content),
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


def _configured_channel_language(payload: dict[str, Any]) -> str:
    if not _uses_inbox_language():
        return ""

    inbox = payload.get("inbox") or {}
    conversation = payload.get("conversation") or {}
    inbox_id = _string_id(
        inbox.get("id")
        or conversation.get("inbox_id")
        or payload.get("inbox_id")
    )
    if inbox_id:
        language = str(settings.chatwoot_inbox_language_map.get(inbox_id, "")).strip()
        if language:
            return language

    website_token = _extract_website_token(payload)
    if website_token:
        return str(settings.chatwoot_website_token_language_map.get(website_token, "")).strip()
    return ""


def _extract_website_token(payload: dict[str, Any]) -> str:
    inbox = payload.get("inbox") or {}
    return _string_id(inbox.get("website_token") or payload.get("website_token"))


def _uses_inbox_language() -> bool:
    return settings.chatwoot_language_source.strip().lower() == "inbox"


def _extract_faq_command(payload: dict[str, Any], fallback: str = "") -> str:
    fallback_command = find_faq_command(fallback)
    if fallback_command:
        return fallback_command

    return _find_submitted_faq_command(payload)


def _find_submitted_faq_command(value: Any, parent_key: str = "") -> str:
    if isinstance(value, str):
        if _is_submission_key(parent_key):
            return find_faq_command(value)
        return ""

    if isinstance(value, dict):
        for key, nested_value in value.items():
            key_text = str(key)
            if key_text in ("items", "raw"):
                continue
            command = _find_submitted_faq_command(nested_value, key_text)
            if command:
                return command
        return ""

    if isinstance(value, list):
        for item in value:
            command = _find_submitted_faq_command(item, parent_key)
            if command:
                return command
        return ""

    return ""


def _is_submission_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in {
        "submitted_values",
        "submitted_value",
        "submitted_options",
        "submitted_option",
        "selected_values",
        "selected_value",
        "selected_option",
        "selected_item",
        "postback",
        "postback_data",
        "payload",
        "value",
        "title",
    }


def _known_or_guessed_language(message: IncomingMessage) -> str:
    configured_language = str(message.metadata.get("configured_language") or "")
    if _uses_inbox_language():
        if configured_language:
            conversation_languages[message.conversation_id] = configured_language
        return configured_language or conversation_languages.get(message.conversation_id, "")

    if configured_language:
        conversation_languages[message.conversation_id] = configured_language
        return configured_language
    return conversation_languages.get(message.conversation_id) or str(
        message.metadata.get("user_language") or ""
    )


def _copy_incoming_message(message: IncomingMessage, guard_result: GuardResult) -> IncomingMessage:
    metadata = dict(message.metadata)
    metadata["guard_reason"] = guard_result.reason
    metadata["original_content_masked"] = True
    return IncomingMessage(
        conversation_id=message.conversation_id,
        contact_id=message.contact_id,
        content=guard_result.sanitized_content,
        user_level=message.user_level,
        metadata=metadata,
    )


async def _resolve_user_language(message: IncomingMessage) -> str:
    configured_language = str(message.metadata.get("configured_language") or "")
    if _uses_inbox_language():
        if configured_language:
            conversation_languages[message.conversation_id] = configured_language
            return configured_language

        known_language = conversation_languages.get(message.conversation_id)
        if known_language:
            return known_language

        return await _detect_and_cache_conversation_language(message.conversation_id, message.content)

    if configured_language:
        conversation_languages[message.conversation_id] = configured_language
        return configured_language

    known_language = conversation_languages.get(message.conversation_id)
    if known_language:
        return known_language

    guessed_language = str(message.metadata.get("user_language") or "")
    if guessed_language:
        conversation_languages[message.conversation_id] = guessed_language
        return guessed_language

    if not (settings.translation_private_note_enabled or settings.translation_outgoing_enabled):
        return ""

    return await _detect_and_cache_conversation_language(message.conversation_id, message.content)


async def _detect_and_cache_conversation_language(conversation_id: str, content: str) -> str:
    if not content or not (settings.translation_private_note_enabled or settings.translation_outgoing_enabled):
        return ""

    try:
        detected_language = await asyncio.wait_for(
            translator.detect_language(content),
            timeout=settings.translation_timeout_seconds,
        )
    except TimeoutError:
        logger.warning("Language detection timed out conversation_id=%s", conversation_id)
        return ""

    if detected_language:
        conversation_languages[conversation_id] = detected_language
        logger.info(
            "Detected conversation language conversation_id=%s language=%s",
            conversation_id,
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
