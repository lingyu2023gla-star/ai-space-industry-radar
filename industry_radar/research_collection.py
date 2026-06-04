from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


def generate_research_id(query: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "-", query.casefold()).strip("-")[:50].strip("-")
    return f"{timestamp}-{slug or 'research-session'}"


def ensure_research_dir(research_dir: str = "research") -> None:
    Path(research_dir).mkdir(parents=True, exist_ok=True)


def build_research_paths(research_id: str, research_dir: str = "research") -> dict:
    base = Path(research_dir)
    return {
        "markdown": str(base / f"{research_id}.md"),
        "metadata": str(base / f"{research_id}.json"),
    }


def create_research_metadata(
    research_id: str,
    query: str,
    output_path: str,
    retriever: str,
    top_k: int,
    filters: dict,
    evidence_count: int,
    llm_enabled: bool,
    ingested: bool = False,
) -> dict:
    timestamp = now_iso()
    return {
        "research_id": research_id,
        "query": query,
        "created_at": timestamp,
        "updated_at": timestamp,
        "output_path": output_path,
        "retriever": retriever,
        "top_k": top_k,
        "filters": filters,
        "evidence_count": evidence_count,
        "llm_enabled": llm_enabled,
        "ingested": ingested,
        "ingested_at": timestamp if ingested else None,
    }


def write_research_session(markdown: str, metadata: dict, research_dir: str = "research") -> dict:
    ensure_research_dir(research_dir)
    paths = build_research_paths(metadata["research_id"], research_dir)
    Path(paths["markdown"]).write_text(markdown, encoding="utf-8")
    with Path(paths["metadata"]).open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    return paths


def list_research_sessions(research_dir: str = "research", limit: int = 20) -> list[dict]:
    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    path = Path(research_dir)
    if not path.exists():
        return []
    sessions = []
    for entry in path.glob("*.json"):
        try:
            sessions.append(read_research_metadata(str(entry), research_dir=research_dir))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(sessions, key=lambda item: str(item.get("created_at", "")), reverse=True)[:limit]


def read_research_metadata(research_id_or_path: str, research_dir: str = "research") -> dict:
    path = resolve_research_path(research_id_or_path, research_dir, ".json")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_research_markdown(research_id_or_path: str, research_dir: str = "research") -> str:
    path = resolve_research_path(research_id_or_path, research_dir, ".md")
    return path.read_text(encoding="utf-8")


def mark_research_ingested(research_id: str, research_dir: str = "research") -> dict:
    metadata = read_research_metadata(research_id, research_dir=research_dir)
    timestamp = now_iso()
    metadata["ingested"] = True
    metadata["ingested_at"] = timestamp
    metadata["updated_at"] = timestamp
    ensure_research_dir(research_dir)
    paths = build_research_paths(metadata["research_id"], research_dir)
    with Path(paths["metadata"]).open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    return metadata


def delete_research_session(research_id: str, research_dir: str = "research") -> dict:
    paths = build_research_paths(research_id, research_dir)
    markdown_path = Path(paths["markdown"])
    metadata_path = Path(paths["metadata"])
    deleted_markdown = False
    deleted_metadata = False
    if markdown_path.exists():
        markdown_path.unlink()
        deleted_markdown = True
    if metadata_path.exists():
        metadata_path.unlink()
        deleted_metadata = True
    return {
        "deleted_markdown": deleted_markdown,
        "deleted_metadata": deleted_metadata,
    }


def resolve_research_path(research_id_or_path: str, research_dir: str, suffix: str) -> Path:
    direct_path = Path(research_id_or_path)
    if direct_path.exists():
        return direct_path
    path = Path(build_research_paths(research_id_or_path, research_dir)["metadata" if suffix == ".json" else "markdown"])
    if not path.exists():
        raise FileNotFoundError(f"research session not found: {research_id_or_path}")
    return path


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
