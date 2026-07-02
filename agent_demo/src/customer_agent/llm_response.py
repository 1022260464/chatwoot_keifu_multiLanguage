from __future__ import annotations

import re


_HIDDEN_BLOCK_RE = re.compile(
    r"<(?:think|analysis|reasoning)\b[^>]*>.*?</(?:think|analysis|reasoning)>",
    re.DOTALL | re.IGNORECASE,
)
_UNCLOSED_HIDDEN_BLOCK_RE = re.compile(
    r"<(?:think|analysis|reasoning)\b[^>]*>.*\Z",
    re.DOTALL | re.IGNORECASE,
)
_REASONING_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:思考过程|推理过程|分析过程|Reasoning|Thought process|Analysis)\s*[:：]\s*[\s\S]*?"
    r"(?=\n\s*(?:最终回答|回答|Reply|Answer|Final answer)\s*[:：]|\Z)",
    re.IGNORECASE,
)
_ANSWER_PREFIX_RE = re.compile(
    r"^\s*(?:最终回答|回答|Reply|Answer|Final answer)\s*[:：]\s*",
    re.IGNORECASE,
)


def sanitize_public_reply(text: str) -> str:
    """Remove reasoning text that must never be shown in public replies."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    cleaned = _HIDDEN_BLOCK_RE.sub("", cleaned)
    cleaned = _UNCLOSED_HIDDEN_BLOCK_RE.sub("", cleaned)
    cleaned = _REASONING_SECTION_RE.sub("", cleaned)
    cleaned = _ANSWER_PREFIX_RE.sub("", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
