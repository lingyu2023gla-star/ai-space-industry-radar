from __future__ import annotations

import html
import re


TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    decoded = html.unescape(str(value))
    without_tags = TAG_RE.sub(" ", decoded)
    return WHITESPACE_RE.sub(" ", without_tags).strip()


def truncate_text(value: str | None, max_length: int = 300) -> str:
    if max_length <= 0:
        return ""
    cleaned = clean_text(value)
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[:max_length] + "..."
