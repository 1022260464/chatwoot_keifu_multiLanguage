from __future__ import annotations

import asyncio
import json
from typing import Annotated
from typing import Protocol
from urllib import parse, request
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from .config import Settings


class DashboardMessageSender(Protocol):
    async def send_public_reply(self, conversation_id: str, content: str) -> None:
        ...

    async def send_private_note(self, conversation_id: str, content: str) -> None:
        ...


class DashboardTranslator(Protocol):
    async def translate(self, text: str, target: str) -> str:
        ...


class MassMessageRequest(BaseModel):
    conversation_ids: list[str] = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=4000)
    private: bool = False
    delay_seconds: float = Field(default=0.5, ge=0, le=10)
    translate_before_send: bool = False
    target_language: str = ""


class MassMessageItemResult(BaseModel):
    conversation_id: str
    ok: bool
    error: str = ""


class MassMessageResponse(BaseModel):
    total: int
    success: int
    failed: int
    translated: bool = False
    target_language: str = ""
    sent_content_preview: str = ""
    results: list[MassMessageItemResult]


class DashboardConversation(BaseModel):
    id: str
    display_name: str = ""
    email: str = ""
    status: str = ""
    inbox_id: str = ""
    last_activity_at: str = ""
    assignee_name: str = ""


class DashboardConversationResponse(BaseModel):
    total: int
    conversations: list[DashboardConversation]


def build_dashboard_router(
    settings: Settings,
    sender: DashboardMessageSender,
    translator: DashboardTranslator,
) -> APIRouter:
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    def verify_dashboard_token(token: str) -> None:
        if not settings.dashboard_api_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DASHBOARD_API_TOKEN is not configured",
            )

        if token != settings.dashboard_api_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid dashboard token",
            )

    @router.get("/conversations", response_model=DashboardConversationResponse)
    async def list_conversations(
        x_dashboard_token: Annotated[str, Header(alias="X-Dashboard-Token")] = "",
        status_filter: Annotated[str, Query(alias="status")] = "open",
        query: Annotated[str, Query(alias="q")] = "",
        page: int = 1,
    ) -> DashboardConversationResponse:
        verify_dashboard_token(x_dashboard_token)

        if not (
            settings.chatwoot_base_url
            and settings.chatwoot_account_id
            and settings.chatwoot_api_access_token
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chatwoot settings are incomplete",
            )

        conversations = await asyncio.to_thread(
            _fetch_chatwoot_conversations,
            settings,
            status_filter,
            query,
            page,
        )
        return DashboardConversationResponse(
            total=len(conversations),
            conversations=conversations,
        )

    @router.post("/mass-messages", response_model=MassMessageResponse)
    async def send_mass_messages(
        payload: MassMessageRequest,
        x_dashboard_token: Annotated[str, Header(alias="X-Dashboard-Token")] = "",
    ) -> MassMessageResponse:
        verify_dashboard_token(x_dashboard_token)

        normalized_ids = [str(item).strip() for item in payload.conversation_ids]
        conversation_ids = [item for item in normalized_ids if item]
        if not conversation_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="conversation_ids cannot be empty",
            )

        content = payload.content
        translated = False
        target_language = ""
        if payload.translate_before_send:
            target_language = payload.target_language.strip()
            if not target_language:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="target_language is required when translate_before_send is true",
                )

            translated_content = await translator.translate(payload.content, target=target_language)
            if not translated_content:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Translation returned empty content",
                )
            content = translated_content
            translated = True

        results: list[MassMessageItemResult] = []
        for index, conversation_id in enumerate(conversation_ids):
            try:
                if payload.private:
                    await sender.send_private_note(conversation_id, content)
                else:
                    await sender.send_public_reply(conversation_id, content)
                results.append(MassMessageItemResult(conversation_id=conversation_id, ok=True))
            except Exception as exc:
                results.append(
                    MassMessageItemResult(
                        conversation_id=conversation_id,
                        ok=False,
                        error=str(exc),
                    )
                )

            if payload.delay_seconds and index < len(conversation_ids) - 1:
                await asyncio.sleep(payload.delay_seconds)

        success = sum(1 for item in results if item.ok)
        return MassMessageResponse(
            total=len(results),
            success=success,
            failed=len(results) - success,
            translated=translated,
            target_language=target_language,
            sent_content_preview=content[:160],
            results=results,
        )

    return router


def _fetch_chatwoot_conversations(
    settings: Settings,
    status_filter: str,
    query: str,
    page: int,
) -> list[DashboardConversation]:
    params: dict[str, str] = {"page": str(max(page, 1))}
    if status_filter:
        params["status"] = status_filter
    if query:
        params["q"] = query

    query_string = parse.urlencode(params)
    url = (
        f"{settings.chatwoot_base_url.rstrip('/')}"
        f"/api/v1/accounts/{settings.chatwoot_account_id}/conversations?{query_string}"
    )
    req = request.Request(
        url,
        method="GET",
        headers={
            "api_access_token": settings.chatwoot_api_access_token,
            "Content-Type": "application/json",
        },
    )

    try:
        with request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chatwoot API error {exc.code}: {detail}",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chatwoot API request failed: {exc.reason}",
        ) from exc

    raw_items = _extract_conversation_items(data)
    return [_normalize_conversation(item) for item in raw_items if isinstance(item, dict)]


def _extract_conversation_items(data: object) -> list[object]:
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    payload = data.get("payload")
    if isinstance(payload, list):
        return payload

    nested_data = data.get("data")
    if isinstance(nested_data, dict):
        nested_payload = nested_data.get("payload")
        if isinstance(nested_payload, list):
            return nested_payload

    conversations = data.get("conversations")
    if isinstance(conversations, list):
        return conversations

    return []


def _normalize_conversation(item: dict[str, object]) -> DashboardConversation:
    meta = _as_dict(item.get("meta"))
    sender = _as_dict(meta.get("sender") or item.get("sender"))
    contact = _as_dict(item.get("contact") or sender)
    assignee = _as_dict(meta.get("assignee") or item.get("assignee"))

    conversation_id = item.get("id") or item.get("conversation_id")
    display_name = (
        _string_value(sender.get("name"))
        or _string_value(contact.get("name"))
        or _string_value(item.get("display_id"))
        or _string_value(conversation_id)
    )

    return DashboardConversation(
        id=_string_value(conversation_id),
        display_name=display_name,
        email=_string_value(sender.get("email") or contact.get("email")),
        status=_string_value(item.get("status")),
        inbox_id=_string_value(item.get("inbox_id")),
        last_activity_at=_string_value(item.get("last_activity_at")),
        assignee_name=_string_value(assignee.get("name")),
    )


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _string_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)
