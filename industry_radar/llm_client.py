from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def call_deepseek_chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int = 60,
    response_format_json: bool = True,
) -> str:
    api_key_value = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key_value:
        raise ValueError("DEEPSEEK_API_KEY is not set")

    model_value = model or os.environ.get("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL
    base_url_value = (
        base_url or os.environ.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL
    ).rstrip("/")
    payload: dict[str, Any] = {
        "model": model_value,
        "messages": messages,
        "max_tokens": 800,
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}

    request = urllib.request.Request(
        f"{base_url_value}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key_value}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"DeepSeek HTTP error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"DeepSeek request error: {exc.reason}") from exc

    try:
        data = json.loads(response_body)
        return str(data["choices"][0]["message"]["content"])
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise ValueError("DeepSeek response is not valid chat completion JSON") from exc
