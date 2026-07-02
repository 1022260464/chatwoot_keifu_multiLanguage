from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

from .clients import ChatwootGateway
from .config import Settings
from .support_templates import PUBLIC_REPLY_FALLBACKS
from .translator import contains_chinese


logger = logging.getLogger(__name__)


class ChatwootClient(ChatwootGateway):
    def __init__(self, settings: Settings) -> None:
        if not settings.chatwoot_base_url:
            raise ValueError("CHATWOOT_BASE_URL is required when using ChatwootClient")
        if not settings.chatwoot_account_id:
            raise ValueError("CHATWOOT_ACCOUNT_ID is required when using ChatwootClient")
        if not settings.chatwoot_api_access_token:
            raise ValueError("CHATWOOT_API_ACCESS_TOKEN is required when using ChatwootClient")

        self._base_url = settings.chatwoot_base_url.rstrip("/")
        self._account_id = settings.chatwoot_account_id
        self._api_access_token = settings.chatwoot_api_access_token
        self._default_assignee_id = settings.chatwoot_default_assignee_id
        self._public_reply_fallback_language = settings.public_reply_fallback_language

    async def open_conversation(self, conversation_id: str) -> None:
        await self._toggle_status(conversation_id, status="open")

    async def send_public_reply(self, conversation_id: str, content: str) -> None:
        await self._send_message(conversation_id, content, is_private=False)

    async def send_private_note(self, conversation_id: str, content: str) -> None:
        await self._send_message(conversation_id, content, is_private=True)

    async def send_interactive_message(
        self,
        conversation_id: str,
        content: str,
        content_type: str,
        content_attributes: dict[str, Any],
    ) -> None:
        await self._send_message(
            conversation_id,
            content,
            is_private=False,
            content_type=content_type,
            content_attributes=content_attributes,
        )

    async def handoff_to_human(self, conversation_id: str, private_note: str) -> None:
        await self.open_conversation(conversation_id)
        if self._default_assignee_id:
            await self._assign_conversation(conversation_id, self._default_assignee_id)
        await self.send_private_note(conversation_id, private_note)

    async def update_conversation_custom_attributes(
        self,
        conversation_id: str,
        custom_attributes: dict[str, Any],
    ) -> None:
        await self._post(
            f"/api/v1/accounts/{self._account_id}/conversations/{conversation_id}/custom_attributes",
            {"custom_attributes": custom_attributes},
            timeout=5,
        )
        logger.info(
            "Updated Chatwoot conversation custom attributes conversation_id=%s keys=%s",
            conversation_id,
            ",".join(sorted(custom_attributes.keys())),
        )

    async def _send_message(
        self,
        conversation_id: str,
        content: str,
        is_private: bool,
        content_type: str = "text",
        content_attributes: dict[str, Any] | None = None,
    ) -> None:
        if not is_private and (contains_chinese(content) or _contains_chinese_value(content_attributes)):
            logger.warning(
                "Blocked Chinese public Chatwoot message; using fallback conversation_id=%s",
                conversation_id,
            )
            content = self._public_reply_fallback()
            content_type = "text"
            content_attributes = None

        payload = {
            "content": content,
            "message_type": "outgoing",
            "private": is_private,
            "content_type": content_type,
        }
        if content_attributes is not None:
            payload["content_attributes"] = content_attributes

        await self._post(
            f"/api/v1/accounts/{self._account_id}/conversations/{conversation_id}/messages",
            payload,
            timeout=10,
        )
        logger.info("Sent Chatwoot message conversation_id=%s private=%s", conversation_id, is_private)

    async def _toggle_status(self, conversation_id: str, status: str) -> None:
        await self._post(
            f"/api/v1/accounts/{self._account_id}/conversations/{conversation_id}/toggle_status",
            {"status": status},
            timeout=5,
        )
        logger.info("Set Chatwoot conversation status conversation_id=%s status=%s", conversation_id, status)

    async def _assign_conversation(self, conversation_id: str, assignee_id: str) -> None:
        await self._post(
            f"/api/v1/accounts/{self._account_id}/conversations/{conversation_id}/assignments",
            {"assignee_id": int(assignee_id)},
            timeout=5,
        )
        logger.info(
            "Assigned Chatwoot conversation conversation_id=%s assignee_id=%s",
            conversation_id,
            assignee_id,
        )

    async def _post(self, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        def send() -> dict[str, Any]:
            body = json.dumps(payload).encode("utf-8")
            headers = {
                "api_access_token": self._api_access_token,
                "Content-Type": "application/json",
            }
            url = f"{self._base_url}{path}"

            for redirect_count in range(4):
                req = request.Request(
                    url,
                    data=body,
                    method="POST",
                    headers=headers,
                )

                try:
                    with request.urlopen(req, timeout=timeout) as response:
                        raw = response.read().decode("utf-8")
                    break
                except HTTPError as exc:
                    location = exc.headers.get("Location")
                    if exc.code in (301, 302, 307, 308) and location and redirect_count < 3:
                        next_url = urljoin(url, location)
                        logger.warning(
                            "Chatwoot API redirected; retrying POST code=%s url=%s",
                            exc.code,
                            next_url,
                        )
                        url = next_url
                        continue

                    detail = exc.read().decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Chatwoot API error {exc.code}: {detail}") from exc
                except URLError as exc:
                    raise RuntimeError(f"Chatwoot API request failed: {exc.reason}") from exc
            else:
                raise RuntimeError("Chatwoot API redirect limit exceeded")

            return json.loads(raw) if raw else {}

        return await asyncio.to_thread(send)

    def _public_reply_fallback(self) -> str:
        language = self._public_reply_fallback_language.strip().lower()
        return PUBLIC_REPLY_FALLBACKS.get(language) or PUBLIC_REPLY_FALLBACKS["vi"]


def _contains_chinese_value(value: Any) -> bool:
    if isinstance(value, str):
        return contains_chinese(value)
    if isinstance(value, dict):
        return any(_contains_chinese_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_chinese_value(item) for item in value)
    return False
