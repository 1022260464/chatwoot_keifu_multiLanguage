from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .faq_config import normalize_faq_language
from .support_templates import (
    LOW_VALUE_MESSAGES,
    LOW_VALUE_REPLIES,
    PRIVACY_PATTERNS,
    PRIVACY_PRIVATE_NOTE_PREFIX,
    SENSITIVE_KEYWORDS,
    SENSITIVE_PUBLIC_REPLIES,
)


GuardAction = Literal["continue", "reply", "handoff"]


@dataclass(frozen=True)
class GuardResult:
    action: GuardAction
    reason: str = ""
    reply: str = ""
    private_note: str = ""
    sanitized_content: str = ""


def inspect_message(content: str, language: str = "") -> GuardResult:
    normalized_language = normalize_faq_language(language) or "vi"
    normalized_content = content.strip()

    if _is_low_value_message(normalized_content, normalized_language):
        return GuardResult(
            action="reply",
            reason="low_value_message",
            reply=_localized(LOW_VALUE_REPLIES, normalized_language),
            sanitized_content=normalized_content,
        )

    sensitive_keyword = _find_sensitive_keyword(normalized_content, normalized_language)
    if sensitive_keyword:
        return GuardResult(
            action="handoff",
            reason=f"sensitive_keyword:{sensitive_keyword}",
            reply=_localized(SENSITIVE_PUBLIC_REPLIES, normalized_language),
            private_note=(
                "Message matched a sensitive or high-risk keyword. Human review is recommended.\n"
                f"Matched keyword: {sensitive_keyword}\n"
                f"Original user message: {normalized_content}"
            ),
            sanitized_content=mask_private_info(normalized_content),
        )

    sanitized_content, matched_labels = mask_private_info_with_labels(normalized_content)
    if matched_labels:
        return GuardResult(
            action="continue",
            reason=f"privacy_masked:{','.join(matched_labels)}",
            private_note=(
                f"{PRIVACY_PRIVATE_NOTE_PREFIX}.\n"
                f"Field types: {', '.join(matched_labels)}"
            ),
            sanitized_content=sanitized_content,
        )

    return GuardResult(action="continue", sanitized_content=normalized_content)


def mask_private_info(text: str) -> str:
    masked, _ = mask_private_info_with_labels(text)
    return masked


def mask_private_info_with_labels(text: str) -> tuple[str, list[str]]:
    masked = text
    matched_labels: list[str] = []
    for item in PRIVACY_PATTERNS:
        pattern = str(item["pattern"])
        if re.search(pattern, masked):
            matched_labels.append(str(item["name"]))
            masked = re.sub(pattern, str(item["mask"]), masked)
    return masked, matched_labels


def _is_low_value_message(content: str, language: str) -> bool:
    lowered = content.lower()
    if not lowered:
        return True

    if len(lowered) <= 1:
        return True

    low_value_messages = set(LOW_VALUE_MESSAGES.get(language, set()))
    low_value_messages.update(LOW_VALUE_MESSAGES.get("en", set()))
    low_value_messages.update(LOW_VALUE_MESSAGES.get("zh", set()))
    if lowered in low_value_messages:
        return True

    if len(lowered) <= 8 and len(set(lowered)) <= 2:
        return True

    if re.fullmatch(r"[\W_]+", lowered):
        return True

    return False


def _find_sensitive_keyword(content: str, language: str) -> str:
    lowered = content.lower()
    keyword_sets = [SENSITIVE_KEYWORDS.get(language, set()), SENSITIVE_KEYWORDS.get("en", set())]
    keyword_sets.append(SENSITIVE_KEYWORDS.get("zh", set()))

    for keywords in keyword_sets:
        for keyword in keywords:
            if keyword.lower() in lowered:
                return keyword
    return ""


def _localized(values: dict[str, str], language: str) -> str:
    return values.get(language) or values["vi"]
