from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .knowledge_base import tokenize
from .models import validate_date
from .text_utils import clean_text


def build_research_documents(research_dir: str = "research") -> list[dict]:
    base = Path(research_dir)
    if not base.exists():
        return []

    documents = []
    for metadata_path in sorted(base.glob("*.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(metadata, dict):
            continue

        research_id = str(metadata.get("research_id") or metadata_path.stem)
        markdown_path = base / f"{research_id}.md"
        try:
            markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
        except OSError:
            markdown = ""

        doc = {
            "research_id": research_id,
            "query": str(metadata.get("query", "")),
            "created_at": str(metadata.get("created_at", "")),
            "updated_at": str(metadata.get("updated_at", "")),
            "retriever": str(metadata.get("retriever", "")),
            "top_k": metadata.get("top_k", 0),
            "filters": metadata.get("filters") if isinstance(metadata.get("filters"), dict) else {},
            "evidence_count": int_or_zero(metadata.get("evidence_count")),
            "llm_enabled": bool(metadata.get("llm_enabled", False)),
            "ingested": bool(metadata.get("ingested", False)),
            "output_path": str(metadata.get("output_path") or markdown_path),
            "markdown_path": str(markdown_path),
            "metadata_path": str(metadata_path),
            "markdown_missing": not markdown_path.exists(),
            "markdown": markdown,
        }
        doc["text"] = build_document_text(doc, metadata)
        documents.append(doc)
    return documents


def score_research_document(query: str, doc: dict) -> float:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        raise ValueError("query must not be empty")

    field_weights = {
        "query": 5,
        "heading": 4,
        "markdown": 2,
        "filters": 1,
        "retriever": 1,
    }
    heading = extract_markdown_heading(str(doc.get("markdown", "")))
    field_values = {
        "query": str(doc.get("query", "")),
        "heading": heading,
        "markdown": str(doc.get("markdown", "")),
        "filters": json.dumps(doc.get("filters", {}), ensure_ascii=False, sort_keys=True),
        "retriever": str(doc.get("retriever", "")),
    }

    score = 0.0
    matched = False
    for field, weight in field_weights.items():
        field_tokens = set(tokenize(field_values[field]))
        hits = query_tokens & field_tokens
        if hits:
            matched = True
            score += len(hits) * weight

    if not matched:
        return 0.0
    score += int_or_zero(doc.get("evidence_count")) * 0.05
    if doc.get("ingested"):
        score += 0.1
    return score


def search_research_documents(
    query: str,
    documents: list[dict],
    top_k: int = 10,
    retriever: str | None = None,
    ingested: bool | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    if top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    if not clean_text(query):
        raise ValueError("query must not be empty")
    since_value = validate_date(since) if since else ""
    until_value = validate_date(until) if until else ""

    scored = []
    for doc in documents:
        if retriever and str(doc.get("retriever", "")) != retriever:
            continue
        if ingested is not None and bool(doc.get("ingested", False)) != ingested:
            continue
        created_date = str(doc.get("created_at", ""))[:10]
        if since_value and created_date < since_value:
            continue
        if until_value and created_date > until_value:
            continue

        score = score_research_document(query, doc)
        if score <= 0:
            continue
        result = dict(doc)
        result["score"] = score
        scored.append(result)

    return sorted(
        scored,
        key=lambda item: (float(item.get("score", 0)), str(item.get("created_at", ""))),
        reverse=True,
    )[:top_k]


def build_research_search_report(results: list[dict], query: str) -> str:
    if not results:
        return "No matching research sessions found."

    lines = [f"Research Search Results for: {query}", ""]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"{index}. {result.get('research_id', '')}",
                f"   - query: {result.get('query', '')}",
                f"   - created_at: {result.get('created_at', '')}",
                f"   - retriever: {result.get('retriever', '')}",
                f"   - evidence_count: {result.get('evidence_count', 0)}",
                f"   - ingested: {str(result.get('ingested', False)).lower()}",
                f"   - score: {float(result.get('score', 0)):.2f}",
            ]
        )
        if result.get("output_path"):
            lines.append(f"   - output_path: {result.get('output_path', '')}")
    return "\n".join(lines)


def build_research_collection_stats(documents: list[dict]) -> dict:
    total = len(documents)
    ingested_count = sum(1 for doc in documents if doc.get("ingested"))
    evidence_counts = [int_or_zero(doc.get("evidence_count")) for doc in documents]
    created_dates = sorted(
        date_part(doc.get("created_at")) for doc in documents if date_part(doc.get("created_at"))
    )
    industries = Counter(
        str(doc.get("filters", {}).get("industry"))
        for doc in documents
        if isinstance(doc.get("filters"), dict) and doc.get("filters", {}).get("industry")
    )
    filters = Counter()
    for doc in documents:
        if not isinstance(doc.get("filters"), dict):
            continue
        for key, value in doc["filters"].items():
            if value:
                filters[f"{key}:{value}"] += 1

    return {
        "total_sessions": total,
        "ingested_count": ingested_count,
        "not_ingested_count": total - ingested_count,
        "retriever_distribution": dict(Counter(str(doc.get("retriever", "")) or "unknown" for doc in documents)),
        "llm_enabled_count": sum(1 for doc in documents if doc.get("llm_enabled")),
        "date_range": (created_dates[0], created_dates[-1]) if created_dates else ("", ""),
        "average_evidence_count": (sum(evidence_counts) / total) if total else 0.0,
        "top_filters": dict(filters.most_common(10)),
        "top_industries": dict(industries.most_common(10)),
    }


def render_research_stats(stats: dict) -> str:
    start_date, end_date = stats.get("date_range", ("", ""))
    date_range = f"{start_date} to {end_date}" if start_date and end_date else ""
    lines = [
        "Research Collection Stats",
        "",
        f"Total sessions: {stats.get('total_sessions', 0)}",
        f"Ingested: {stats.get('ingested_count', 0)}",
        f"Not ingested: {stats.get('not_ingested_count', 0)}",
        f"LLM enabled: {stats.get('llm_enabled_count', 0)}",
        f"Date range: {date_range}",
        f"Average evidence count: {float(stats.get('average_evidence_count', 0)):.1f}",
        "",
        "Retriever distribution:",
    ]
    distribution = stats.get("retriever_distribution", {})
    if distribution:
        lines.extend(f"- {name}: {count}" for name, count in sorted(distribution.items()))
    else:
        lines.append("- No data")
    return "\n".join(lines)


def build_document_text(doc: dict, metadata: dict) -> str:
    filters_text = json.dumps(doc.get("filters", {}), ensure_ascii=False, sort_keys=True)
    metadata_text = " ".join(
        clean_text(str(metadata.get(field, "")))
        for field in ("research_id", "query", "created_at", "updated_at", "retriever", "output_path")
        if metadata.get(field)
    )
    parts = [
        doc.get("query", ""),
        doc.get("retriever", ""),
        filters_text,
        str(doc.get("evidence_count", "")),
        doc.get("markdown", ""),
        metadata_text,
    ]
    return clean_text(" ".join(str(part) for part in parts if part is not None))


def extract_markdown_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            return clean_text(match.group(1))
    return ""


def date_part(value) -> str:
    text = str(value or "")
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else ""


def int_or_zero(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
