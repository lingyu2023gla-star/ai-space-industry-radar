from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from .models import validate_date
from .research_index import build_research_documents, search_research_documents


def select_research_sessions(
    research_dir: str = "research",
    query: str | None = None,
    research_ids: list[str] | None = None,
    retriever: str | None = None,
    ingested: bool | None = None,
    since: str | None = None,
    until: str | None = None,
    top_k: int | None = None,
) -> list[dict]:
    if top_k is not None and top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    since_value = validate_date(since) if since else ""
    until_value = validate_date(until) if until else ""

    documents = build_research_documents(research_dir)
    if research_ids:
        wanted = {str(research_id) for research_id in research_ids}
        selected = [doc for doc in documents if str(doc.get("research_id", "")) in wanted]
    elif query:
        selected = search_research_documents(
            query,
            documents,
            top_k=top_k or len(documents) or 1,
            retriever=retriever,
            ingested=ingested,
            since=since_value,
            until=until_value,
        )
        return selected
    else:
        selected = list(documents)

    filtered = []
    for doc in selected:
        if retriever and str(doc.get("retriever", "")) != retriever:
            continue
        if ingested is not None and bool(doc.get("ingested", False)) != ingested:
            continue
        created_date = str(doc.get("created_at", ""))[:10]
        if since_value and created_date < since_value:
            continue
        if until_value and created_date > until_value:
            continue
        filtered.append(dict(doc))

    filtered = sorted(filtered, key=lambda item: str(item.get("created_at", "")), reverse=True)
    return filtered[:top_k] if top_k is not None else filtered


def build_export_manifest(
    sessions: list[dict],
    export_name: str,
    query: str | None = None,
    filters: dict | None = None,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "export_name": export_name,
        "created_at": now_iso(),
        "query": query or "",
        "filters": filters or {},
        "session_count": len(sessions),
        "sessions": [
            {
                "research_id": str(session.get("research_id", "")),
                "query": str(session.get("query", "")),
                "created_at": str(session.get("created_at", "")),
                "retriever": str(session.get("retriever", "")),
                "evidence_count": int_or_zero(session.get("evidence_count")),
                "llm_enabled": bool(session.get("llm_enabled", False)),
                "ingested": bool(session.get("ingested", False)),
                "markdown_path": archive_markdown_path(session),
                "metadata_path": archive_metadata_path(session),
            }
            for session in sessions
        ],
        "warnings": list(warnings or []),
    }


def render_export_readme(manifest: dict) -> str:
    lines = [
        f"# Research Pack: {manifest.get('export_name', '')}",
        "",
        f"Generated at: {manifest.get('created_at', '')}",
        "",
        "## Summary",
        "",
        f"- Query: {manifest.get('query', '')}",
        f"- Session count: {manifest.get('session_count', 0)}",
        f"- Filters: {json.dumps(manifest.get('filters', {}), ensure_ascii=False, sort_keys=True)}",
        "",
        "## Sessions",
        "",
    ]
    sessions = manifest.get("sessions", [])
    if sessions:
        for index, session in enumerate(sessions, start=1):
            lines.extend(
                [
                    f"{index}. {session.get('research_id', '')}",
                    f"   - query: {session.get('query', '')}",
                    f"   - created_at: {session.get('created_at', '')}",
                    f"   - retriever: {session.get('retriever', '')}",
                    f"   - evidence_count: {session.get('evidence_count', 0)}",
                    f"   - ingested: {str(session.get('ingested', False)).lower()}",
                ]
            )
    else:
        lines.append("No sessions included.")
    lines.extend(
        [
            "",
            "## How to use",
            "",
            "- `research/*.md` contains research notes.",
            "- `research/*.json` contains research session metadata.",
            "- `manifest.json` is the export index for this research pack.",
        ]
    )
    return "\n".join(lines)


def export_research_pack(
    sessions: list[dict],
    output_path: str,
    export_name: str = "research_pack",
    query: str | None = None,
    filters: dict | None = None,
    warnings: list[str] | None = None,
) -> str:
    all_warnings = list(warnings or [])
    for session in sessions:
        research_id = str(session.get("research_id", ""))
        if session.get("markdown_missing"):
            all_warnings.append(f"Markdown missing for research session: {research_id}")
        if not session.get("metadata_path"):
            all_warnings.append(f"Metadata missing for research session: {research_id}")

    manifest = build_export_manifest(
        sessions,
        export_name=export_name,
        query=query,
        filters=filters,
        warnings=all_warnings,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("README.md", render_export_readme(manifest))
        for session in sessions:
            research_id = str(session.get("research_id", ""))
            if not research_id:
                continue
            if not session.get("markdown_missing"):
                archive.writestr(archive_markdown_path(session), str(session.get("markdown", "")))
            archive.writestr(
                archive_metadata_path(session),
                json.dumps(session_metadata(session), ensure_ascii=False, indent=2),
            )
    return str(output)


def summarize_export_result(output_path: str, manifest: dict) -> str:
    return "\n".join(
        [
            f"Research pack exported: {output_path}",
            f"Sessions: {manifest.get('session_count', 0)}",
            f"Warnings: {len(manifest.get('warnings', []))}",
        ]
    )


def session_metadata(session: dict) -> dict:
    keys = (
        "research_id",
        "query",
        "created_at",
        "updated_at",
        "output_path",
        "retriever",
        "top_k",
        "filters",
        "evidence_count",
        "llm_enabled",
        "ingested",
        "ingested_at",
    )
    return {key: session.get(key) for key in keys if key in session}


def archive_markdown_path(session: dict) -> str:
    return f"research/{session.get('research_id', '')}.md"


def archive_metadata_path(session: dict) -> str:
    return f"research/{session.get('research_id', '')}.json"


def int_or_zero(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
