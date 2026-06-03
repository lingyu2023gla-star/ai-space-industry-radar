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


def format_citation_label(index: int) -> str:
    if index <= 0:
        raise ValueError("citation index must be positive")
    return f"[{index}]"


def build_citation_entries(results: list[dict]) -> list[dict]:
    entries = []
    for index, result in enumerate(results, start=1):
        entries.append(
            {
                "index": index,
                "label": format_citation_label(index),
                "title": str(result.get("title", "")),
                "date": str(result.get("date", "")),
                "industry": str(result.get("industry", "")),
                "company": str(result.get("company", "")),
                "source": str(result.get("source", "")),
                "source_url": str(result.get("source_url", "")),
                "score": result.get("score", ""),
                "summary": str(result.get("summary", "")),
                "signal": str(result.get("signal", "")),
            }
        )
    return entries


def format_citations_text(citations: list[dict], include_summary: bool = False) -> str:
    if not citations:
        return ""
    lines = []
    for citation in citations:
        lines.append(f"{citation.get('label', '')} {citation.get('title', '')}".rstrip())
        if citation.get("date"):
            lines.append(f"    - 日期：{citation['date']}")
        if citation.get("company"):
            lines.append(f"    - 公司：{citation['company']}")
        if citation.get("source"):
            lines.append(f"    - 来源：{citation['source']}")
        if citation.get("source_url"):
            lines.append(f"    - 链接：{citation['source_url']}")
        if include_summary and citation.get("summary"):
            lines.append(f"    - 摘要：{citation['summary']}")
        if citation.get("signal"):
            lines.append(f"    - 行业信号：{citation['signal']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def build_retrieval_answer(
    query: str,
    results: list[dict],
    with_citations: bool = True,
    include_sources: bool = True,
) -> str:
    if not results:
        return "没有在本地知识库中找到足够相关的信息。"
    if with_citations:
        citations = build_citation_entries(results)
        labels = "".join(citation["label"] for citation in citations[: min(3, len(citations))])
        lines = [
            f"问题：{query}",
            "",
            f"根据本地知识库，相关信息主要集中在检索到的行业事件和趋势信号中 {labels}。",
        ]
        if include_sources:
            citations_text = format_citations_text(citations)
            if citations_text:
                lines.extend(["", "相关证据：", citations_text])
        return "\n".join(lines)

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
    for citation in build_citation_entries(results):
        evidence_lines.append(
            "\n".join(
                [
                    citation["label"],
                    f"标题：{citation.get('title', '')}",
                    f"日期：{citation.get('date', '')}",
                    f"行业：{citation.get('industry', '')}",
                    f"公司：{citation.get('company', '')}",
                    f"来源：{citation.get('source', '')}",
                    f"链接：{citation.get('source_url', '')}",
                    f"摘要：{citation.get('summary', '')}",
                    f"行业信号：{citation.get('signal', '')}",
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
                + (
                    "\n\n请用中文回答。只能基于给定证据回答，不要编造证据外信息。"
                    "回答中必须使用 [1]、[2] 形式引用证据。如果证据不足，要说明不足。"
                )
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
