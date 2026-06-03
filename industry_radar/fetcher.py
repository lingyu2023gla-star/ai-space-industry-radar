from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .importer import ImportResult, import_records
from .models import normalize_industry
from .source_adapters import (
    USER_AGENT,
    atom_link,
    child_text,
    children,
    feed_entry_to_import_record,
    first_child,
    get_source_adapter,
    local_name,
    parse_atom_entries,
    parse_feed_date,
    parse_feed_xml,
    parse_rss_items,
    read_url,
    sanitize_xml_content,
    validate_source_config,
)


@dataclass
class FetchResult:
    fetched: int = 0
    imported: int = 0
    skipped_duplicates: int = 0
    failed: int = 0
    source_count: int = 0
    failed_sources: int = 0
    errors: list[str] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)


def load_sources(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("sources file must contain a list")

    sources: list[dict[str, str]] = []
    for index, source in enumerate(data, start=1):
        if not isinstance(source, dict):
            raise ValueError(f"source {index} must be an object")
        try:
            sources.append(validate_source_config(source))
        except ValueError as exc:
            raise ValueError(f"source {index}: {exc}") from exc
    return sources


def fetch_records(
    sources_path: Path,
    *,
    limit: int = 10,
    industry: str | None = None,
    fallback_date: str | None = None,
) -> FetchResult:
    sources = load_sources(sources_path)
    if industry:
        industry_value = normalize_industry(industry)
        sources = [source for source in sources if source["industry"] == industry_value]

    result = FetchResult()
    result.source_count = len(sources)
    for source in sources:
        try:
            adapter = get_source_adapter(source.get("type", "rss"))
            fetch_source = dict(source)
            if fallback_date:
                fetch_source["_fallback_date"] = fallback_date
            records = adapter.fetch(fetch_source, limit=limit)
        except ET.ParseError as exc:
            result.failed += 1
            result.failed_sources += 1
            result.errors.append(f"Source {source['name']}: XML parse error: {exc}")
            continue
        except Exception as exc:
            result.failed += 1
            result.failed_sources += 1
            result.errors.append(f"Source {source['name']}: {exc}")
            continue

        for index, record in enumerate(records, start=1):
            try:
                result.records.append(record)
                result.fetched += 1
            except (TypeError, ValueError) as exc:
                result.failed += 1
                result.errors.append(f"Source {source['name']} item {index}: {exc}")
    return result


def fetch_and_import(
    sources_path: Path,
    *,
    limit: int = 10,
    industry: str | None = None,
    dry_run: bool = False,
    storage_path: Path | None = None,
) -> FetchResult:
    result = fetch_records(sources_path, limit=limit, industry=industry)
    if dry_run:
        return result

    import_result: ImportResult = import_records(result.records, storage_path)
    result.imported = import_result.imported
    result.skipped_duplicates = import_result.skipped_duplicates
    result.failed += import_result.failed
    result.errors.extend(import_result.errors)
    return result
