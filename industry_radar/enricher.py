from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from typing import Any

from .models import IndustryItem, normalize_importance, normalize_tags
from .text_utils import clean_text


REQUIRED_ENRICHMENT_FIELDS = {"summary", "signal", "tags", "importance"}


def build_enrichment_prompt(item: IndustryItem) -> list[dict[str, str]]:
    example = {
        "summary": "一句到两句话的中文摘要",
        "signal": "这条信息反映的行业信号",
        "tags": "Agent;Product;Enterprise AI",
        "importance": 4,
    }
    user_content = "\n".join(
        [
            "请基于以下行业信息输出结构化 JSON。",
            "",
            f"title: {item.title}",
            f"industry: {item.industry}",
            f"category: {item.category}",
            f"company: {item.company}",
            f"source: {item.source}",
            f"source_url: {item.source_url}",
            f"summary: {item.summary}",
            f"signal: {item.signal}",
            f"tags: {item.tags}",
            f"importance: {item.importance}",
            "",
            "输出 JSON 字段要求：",
            "- summary：中文，一到两句话，不超过 300 字",
            "- signal：中文，说明行业信号或趋势，不超过 100 字",
            "- tags：英文分号分隔，3 到 6 个标签",
            "- importance：1 到 5 的整数",
            "",
            f"示例 JSON：{json.dumps(example, ensure_ascii=False)}",
        ]
    )
    return [
        {
            "role": "system",
            "content": (
                "你是一个严谨的行业研究分析助手，负责把 AI 和商业航天新闻整理成"
                "结构化行业情报。只输出 JSON，不要输出 Markdown。输出必须是合法 JSON。"
            ),
        },
        {"role": "user", "content": user_content},
    ]


def parse_enrichment_result(content: str) -> dict[str, Any]:
    if not content or not content.strip():
        raise ValueError("enrichment content is empty")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("enrichment content is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("enrichment content must be a JSON object")

    missing = REQUIRED_ENRICHMENT_FIELDS - set(data)
    if missing:
        raise ValueError(f"enrichment result missing fields: {', '.join(sorted(missing))}")

    return {
        "summary": clean_text(str(data["summary"])),
        "signal": clean_text(str(data["signal"])),
        "tags": normalize_tags(str(data["tags"])),
        "importance": normalize_importance(str(data["importance"])),
    }


def merge_enrichment(
    item: IndustryItem,
    enrichment: dict[str, Any],
    overwrite: bool = False,
) -> IndustryItem:
    values = {
        "summary": item.summary,
        "signal": item.signal,
        "tags": item.tags,
        "importance": item.importance,
    }
    for field in ("summary", "signal", "tags"):
        if overwrite or not values[field]:
            values[field] = str(enrichment[field])
    if overwrite:
        values["importance"] = int(enrichment["importance"])

    return replace(
        item,
        summary=str(values["summary"]),
        signal=str(values["signal"]),
        tags=str(values["tags"]),
        importance=int(values["importance"]),
        updated_at=datetime.now().replace(microsecond=0).isoformat(),
    )


def needs_enrichment(item: IndustryItem, overwrite: bool = False) -> bool:
    if overwrite:
        return True
    return not (item.summary and item.signal and item.tags)
