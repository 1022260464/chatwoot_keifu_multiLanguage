from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from .clients import ChatwootGateway
from .config import Settings


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

    async def open_conversation(self, conversation_id: str) -> None:
        await self._toggle_status(conversation_id, status="open")

    async def send_public_reply(self, conversation_id: str, content: str) -> None:
        await self._send_message(conversation_id, content, is_private=False)

    async def handoff_to_human(self, conversation_id: str, private_note: str) -> None:
        await self.open_conversation(conversation_id)
        if self._default_assignee_id:
            await self._assign_conversation(conversation_id, self._default_assignee_id)
        await self._send_message(conversation_id, private_note, is_private=True)

    async def _send_message(self, conversation_id: str, content: str, is_private: bool) -> None:
        payload = {
            "content": content,
            "message_type": "outgoing",
            "private": is_private,
        }
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
            req = request.Request(
                f"{self._base_url}{path}",
                data=body,
                method="POST",
                headers={
                    "api_access_token": self._api_access_token,
                    "Content-Type": "application/json",
                },
            )

            try:
                with request.urlopen(req, timeout=timeout) as response:
                    raw = response.read().decode("utf-8")
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"Chatwoot API error {exc.code}: {detail}") from exc
            except URLError as exc:
                raise RuntimeError(f"Chatwoot API request failed: {exc.reason}") from exc

            return json.loads(raw) if raw else {}

        return await asyncio.to_thread(send)
