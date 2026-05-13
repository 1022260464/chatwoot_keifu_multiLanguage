from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib import request
from urllib.error import HTTPError, URLError

from .config import Settings


logger = logging.getLogger(__name__)


class PrivateNoteTranslator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = settings.translation_provider.lower()
        self._target = settings.translation_target_lang
        self._proxy = settings.pygtrans_proxy

    async def translate_to_target(self, text: str) -> str:
        return await asyncio.to_thread(self._translate_sync, text, self._target)

    async def translate(self, text: str, target: str) -> str:
        return await asyncio.to_thread(self._translate_sync, text, target)

    async def detect_language(self, text: str) -> str:
        guessed = guess_language(text)
        if guessed:
            return guessed
        return await asyncio.to_thread(self._detect_language_sync, text)

    def _translate_sync(self, text: str, target: str) -> str:
        if self._provider == "deepseek":
            return self._deepseek_translate_sync(text, target)

        try:
            from pygtrans import Null, Translate
        except ImportError:
            logger.exception("pygtrans is not installed; translation private note was skipped")
            return ""

        proxies = self._proxy_config()
        client = Translate(proxies=proxies) if proxies else Translate()
        result = client.translate(text, target=target)
        if isinstance(result, Null):
            logger.warning("pygtrans returned Null; translation private note was skipped")
            return ""

        return str(getattr(result, "translatedText", "") or "").strip()

    def _detect_language_sync(self, text: str) -> str:
        if self._provider == "deepseek":
            return self._deepseek_detect_language_sync(text)

        try:
            from pygtrans import Null, Translate
        except ImportError:
            logger.exception("pygtrans is not installed; language detection was skipped")
            return ""

        proxies = self._proxy_config()
        client = Translate(proxies=proxies) if proxies else Translate()
        result = client.detect(text)
        if isinstance(result, Null):
            logger.warning("pygtrans returned Null; language detection was skipped")
            return ""

        return str(getattr(result, "language", "") or "").strip()

    def _deepseek_translate_sync(self, text: str, target: str) -> str:
        prompt = (
            f"Translate the following text to {target}. "
            "Only output the translation, with no explanations.\n\n"
            f"{text}"
        )
        return self._deepseek_chat_sync(prompt)

    def _deepseek_detect_language_sync(self, text: str) -> str:
        prompt = (
            "Detect the language of the following text. "
            "Only output one ISO 639-1 language code such as en, ja, ko, fr, es, ar, ru, zh.\n\n"
            f"{text}"
        )
        return self._deepseek_chat_sync(prompt).split()[0].strip().lower()

    def _deepseek_chat_sync(self, prompt: str) -> str:
        if not self._settings.deepseek_api_key:
            logger.warning("DEEPSEEK_API_KEY is empty; translation was skipped")
            return ""

        payload = {
            "model": self._settings.deepseek_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self._settings.deepseek_base_url.rstrip('/')}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=self._settings.translation_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"DeepSeek translation API error {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"DeepSeek translation API request failed: {exc.reason}") from exc

        return str(data["choices"][0]["message"]["content"] or "").strip()

    def _proxy_config(self) -> dict[str, str] | None:
        if not self._proxy:
            return None
        return {
            "http": self._proxy,
            "https": self._proxy,
        }


def should_translate_private_note(text: str, settings: Settings) -> bool:
    return get_translation_skip_reason(text, settings) == ""


def get_translation_skip_reason(text: str, settings: Settings) -> str:
    normalized = text.strip()
    if not settings.translation_private_note_enabled:
        return "TRANSLATION_PRIVATE_NOTE_ENABLED is false"

    if len(normalized) < settings.translation_min_text_length:
        return "Text is shorter than TRANSLATION_MIN_TEXT_LENGTH"

    if settings.translation_skip_chinese and _contains_chinese(normalized):
        return "Text contains Chinese and TRANSLATION_SKIP_CHINESE is true"

    if not normalized:
        return "Empty content"

    return ""


def _contains_chinese(text: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", text) is not None


def contains_chinese(text: str) -> bool:
    return _contains_chinese(text)


def guess_language(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""

    if _contains_chinese(normalized):
        return "zh-CN"

    # Vietnamese and many other languages use Latin letters. Only guess English
    # locally when the text is plain ASCII; accented Latin text should go through
    # the configured detector instead of being collapsed to English.
    if not normalized.isascii():
        return ""

    latin_letters = re.findall(r"[A-Za-z]", normalized)
    if len(latin_letters) >= 2:
        return "en"

    return ""
