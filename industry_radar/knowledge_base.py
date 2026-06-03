from __future__ import annotations

import re
from typing import Any

from .models import normalize_industry, validate_date
from .text_utils import clean_text


STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "with",
    "on",
    "by",
    "is",
    "are",
}

TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]+")


def build_documents_from_items(items: list[Any]) -> list[dict]:
    documents = []
    for item in items:
        doc = {
            "id": item_value(item, "id"),
            "date": item_value(item, "date"),
            "industry": item_value(item, "industry"),
            "category": item_value(item, "category"),
            "company": item_value(item, "company"),
            "title": item_value(item, "title"),
            "summary": item_value(item, "summary"),
            "signal": item_value(item, "signal"),
            "tags": item_value(item, "tags"),
            "source": item_value(item, "source"),
            "source_url": item_value(item, "source_url"),
            "importance": item_value(item, "importance"),
        }
        text_parts = [
            clean_text(str(doc[field]))
            for field in ("title", "summary", "signal", "company", "category", "tags", "source")
            if clean_text(str(doc[field]))
        ]
        doc["text"] = " ".join(text_parts)
        documents.append(doc)
    return documents


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.findall(clean_text(text).casefold()):
        if re.fullmatch(r"[a-z0-9]+", match):
            if match not in STOP_WORDS:
                tokens.append(match)
            continue
        tokens.append(match)
        if len(match) > 1:
            tokens.extend(match[index : index + 2] for index in range(len(match) - 1))
    return tokens


def score_document(query: str, doc: dict) -> float:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    field_weights = {
        "title": 4,
        "tags": 3,
        "signal": 3,
        "summary": 2,
        "company": 1,
        "category": 1,
        "source": 1,
    }
    score = 0.0
    matched = False
    for field, weight in field_weights.items():
        field_tokens = set(tokenize(str(doc.get(field, ""))))
        hits = query_tokens & field_tokens
        if hits:
            matched = True
            score += len(hits) * weight
    if not matched:
        return 0.0
    return score + int_or_zero(doc.get("importance")) * 0.2


def search_documents(
    query: str,
    documents: list[dict],
    top_k: int = 5,
    industry: str | None = None,
    tag: str | None = None,
    company: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    if top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    if not clean_text(query):
        raise ValueError("query must not be empty")
    filtered = filter_documents(
        documents,
        industry=industry,
        tag=tag,
        company=company,
        since=since,
        until=until,
    )

    scored = []
    for doc in filtered:
        score = score_document(query, doc)
        if score > 0:
            result = dict(doc)
            result["score"] = score
            scored.append(result)
    return sorted(
        scored,
        key=lambda doc: (doc["score"], int_or_zero(doc.get("importance")), str(doc.get("date", ""))),
        reverse=True,
    )[:top_k]


def filter_documents(
    documents: list[dict],
    industry: str | None = None,
    tag: str | None = None,
    company: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    filtered = documents
    if industry:
        industry_value = normalize_industry(industry)
        filtered = [doc for doc in filtered if doc.get("industry") == industry_value]
    if tag:
        tag_value = clean_text(tag).casefold()
        filtered = [
            doc
            for doc in filtered
            if tag_value in {part.strip().casefold() for part in str(doc.get("tags", "")).split(";")}
        ]
    if company:
        company_value = clean_text(company).casefold()
        filtered = [
            doc for doc in filtered if company_value in str(doc.get("company", "")).casefold()
        ]
    if since:
        since_value = validate_date(since)
        filtered = [doc for doc in filtered if str(doc.get("date", "")) >= since_value]
    if until:
        until_value = validate_date(until)
        filtered = [doc for doc in filtered if str(doc.get("date", "")) <= until_value]
    return [dict(doc) for doc in filtered]


def build_retrieval_answer(query: str, results: list[dict]) -> str:
    if not results:
        return "没有在本地知识库中找到足够相关的信息。"
    lines = [
        f"问题：{query}",
        "",
        "本地知识库中最相关的信息显示，以下行业事件与问题相关。结论仅基于本地已记录数据。",
        "",
        "相关证据：",
    ]
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result.get('title', '')}")
        if result.get("date"):
            lines.append(f"   - 日期：{result['date']}")
        if result.get("company"):
            lines.append(f"   - 公司：{result['company']}")
        if result.get("signal"):
            lines.append(f"   - 行业信号：{result['signal']}")
        if result.get("source_url"):
            lines.append(f"   - 来源链接：{result['source_url']}")
    return "\n".join(lines)


def build_ask_prompt(query: str, results: list[dict]) -> list[dict]:
    evidence_lines = []
    for index, result in enumerate(results, start=1):
        evidence_lines.append(
            "\n".join(
                [
                    f"[{index}] {result.get('title', '')}",
                    f"日期：{result.get('date', '')}",
                    f"公司：{result.get('company', '')}",
                    f"摘要：{result.get('summary', '')}",
                    f"行业信号：{result.get('signal', '')}",
                    f"标签：{result.get('tags', '')}",
                    f"来源链接：{result.get('source_url', '')}",
                ]
            )
        )
    return [
        {
            "role": "system",
            "content": "你是严谨的行业研究助手，只能基于给定证据回答，不要编造。",
        },
        {
            "role": "user",
            "content": (
                f"用户问题：{query}\n\n"
                "检索到的证据：\n"
                + "\n\n".join(evidence_lines)
                + "\n\n请用中文回答，明确引用证据编号，例如 [1]、[2]。如果证据不足，要说明不足。"
            ),
        },
    ]


def item_value(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field, "")
    return getattr(item, field, "")


def int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
