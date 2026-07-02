from __future__ import annotations

import re
from typing import Any

from .support_templates import FAQ_COMMAND_PREFIX, FAQ_LOCALES, FAQ_MENU_TRIGGERS


def normalize_faq_language(language: str) -> str:
    normalized = language.strip().lower()
    if normalized in ("zh", "zh-cn", "zh-tw", "zh-hans", "zh-hant"):
        return "vi"
    if normalized.startswith("en"):
        return "en"
    if normalized.startswith("vi"):
        return "vi"
    return ""


def is_supported_faq_language(language: str) -> bool:
    return normalize_faq_language(language) in FAQ_LOCALES


def get_faq_intro(language: str) -> str:
    locale = _get_locale(language)
    return str(locale["intro"])


def get_faq_button_prompt(language: str) -> str:
    locale = _get_locale(language)
    return str(locale["button_prompt"])


def get_faq_menu_text(language: str) -> str:
    locale = _get_locale(language)
    lines = [str(locale["button_prompt"])]
    for index, item in enumerate(locale["items"], start=1):
        title = str(item["title"]).replace("\n", " / ")
        lines.append(f"{index}. {title}")
    return "\n".join(lines)


def get_faq_answer(command: str, language: str = "") -> str:
    normalized_command = find_faq_command(command)
    if not normalized_command:
        return ""

    locale = _get_locale(language)
    for item in locale["items"]:
        if item["value"] == normalized_command:
            return str(item["answer"])
    return ""


def find_faq_command(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith(FAQ_COMMAND_PREFIX):
        return normalized

    numbered_command = _find_numbered_faq_command(normalized)
    if numbered_command:
        return numbered_command

    for locale in FAQ_LOCALES.values():
        for item in locale["items"]:
            if normalized == item["title"] or normalized == item["value"]:
                return str(item["value"])
    return ""


def is_faq_menu_trigger(content: str) -> bool:
    return content.strip().lower() in FAQ_MENU_TRIGGERS


def build_faq_menu_attributes(language: str) -> dict[str, list[dict[str, Any]]]:
    locale = _get_locale(language)
    return {
        "items": [
            {"title": str(item["title"]), "value": str(item["value"])}
            for item in locale["items"]
        ]
    }


def _get_locale(language: str) -> dict[str, Any]:
    normalized_language = normalize_faq_language(language)
    return FAQ_LOCALES.get(normalized_language) or FAQ_LOCALES["vi"]


def _find_numbered_faq_command(value: str) -> str:
    match = re.fullmatch(r"#?(\d+)[.)、．]?", value)
    if not match:
        return ""

    index = int(match.group(1)) - 1
    first_locale = next(iter(FAQ_LOCALES.values()))
    items = first_locale["items"]
    if 0 <= index < len(items):
        return str(items[index]["value"])
    return ""
