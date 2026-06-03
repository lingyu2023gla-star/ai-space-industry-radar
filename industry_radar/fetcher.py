from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .importer import ImportResult, import_records
from .models import clean_prompt_value, normalize_industry, normalize_tags
from .text_utils import truncate_text


USER_AGENT = "Mozilla/5.0 (compatible; ai-space-industry-radar/0.5; +https://example.com)"


@dataclass
class FetchResult:
    fetched: int = 0
    imported: int = 0
    skipped_duplicates: int = 0
    failed: int = 0
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
        normalized = {
            "name": clean_prompt_value(str(source.get("name", ""))),
            "url": clean_prompt_value(str(source.get("url", ""))),
            "industry": normalize_industry(str(source.get("industry", ""))),
            "category": clean_prompt_value(str(source.get("category", ""))),
            "default_tags": normalize_tags(str(source.get("default_tags", ""))),
        }
        missing = [key for key in ("name", "url", "industry", "category") if not normalized[key]]
        if missing:
            raise ValueError(f"source {index} missing required fields: {', '.join(missing)}")
        sources.append(normalized)
    return sources


def read_url(url: str, timeout: int = 15) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def sanitize_xml_content(content: bytes) -> str:
    decoded = content.decode("utf-8", errors="replace")
    first_xml_char = decoded.find("<")
    if first_xml_char > 0:
        decoded = decoded[first_xml_char:]
    return "".join(
        ch
        for ch in decoded
        if ch in ("\t", "\n", "\r") or ord(ch) >= 0x20
    )


def parse_feed_xml(xml_bytes: bytes | str) -> list[dict[str, str]]:
    content = (
        sanitize_xml_content(xml_bytes)
        if isinstance(xml_bytes, bytes)
        else sanitize_xml_content(xml_bytes.encode("utf-8"))
    )
    root = ET.fromstring(content)
    root_name = local_name(root.tag)
    if root_name == "rss":
        channel = first_child(root, "channel")
        return parse_rss_items(channel if channel is not None else root)
    if root_name == "feed":
        return parse_atom_entries(root)
    return []


def parse_rss_items(parent: ET.Element) -> list[dict[str, str]]:
    entries = []
    for item in children(parent, "item"):
        entries.append(
            {
                "title": child_text(item, "title"),
                "link": child_text(item, "link"),
                "summary": child_text(item, "description"),
                "published": child_text(item, "pubDate"),
            }
        )
    return entries


def parse_atom_entries(parent: ET.Element) -> list[dict[str, str]]:
    entries = []
    for entry in children(parent, "entry"):
        entries.append(
            {
                "title": child_text(entry, "title"),
                "link": atom_link(entry),
                "summary": child_text(entry, "summary") or child_text(entry, "content"),
                "published": child_text(entry, "updated") or child_text(entry, "published"),
            }
        )
    return entries


def feed_entry_to_import_record(
    entry: dict[str, str],
    source: dict[str, str],
    fallback_date: str | None = None,
) -> dict[str, Any]:
    return {
        "date": parse_feed_date(entry.get("published", ""), fallback_date),
        "industry": source["industry"],
        "category": source["category"],
        "company": source["name"],
        "title": clean_prompt_value(entry.get("title", "")),
        "source": source["name"],
        "source_url": clean_prompt_value(entry.get("link", "")),
        "summary": truncate_text(entry.get("summary", ""), 500)
        or truncate_text(entry.get("title", ""), 500),
        "signal": "",
        "tags": source.get("default_tags", ""),
        "importance": 3,
    }


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
    for source in sources:
        try:
            entries = parse_feed_xml(read_url(source["url"]))[:limit]
        except ET.ParseError as exc:
            result.failed += 1
            result.errors.append(f"Source {source['name']}: XML parse error: {exc}")
            continue
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"Source {source['name']}: {exc}")
            continue

        for index, entry in enumerate(entries, start=1):
            try:
                record = feed_entry_to_import_record(entry, source, fallback_date)
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


def parse_feed_date(value: str | None, fallback_date: str | None = None) -> str:
    fallback = fallback_date or date.today().isoformat()
    cleaned = clean_prompt_value(value)
    if not cleaned:
        return fallback

    try:
        return parsedate_to_datetime(cleaned).date().isoformat()
    except (TypeError, ValueError):
        pass

    atom_value = cleaned.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(atom_value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.date().isoformat()
    except ValueError:
        return fallback


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(parent) if local_name(child.tag) == name]


def first_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in list(parent):
        if local_name(child.tag) == name:
            return child
    return None


def child_text(parent: ET.Element, name: str) -> str:
    child = first_child(parent, name)
    if child is None or child.text is None:
        return ""
    return clean_prompt_value(child.text)


def atom_link(entry: ET.Element) -> str:
    for link in children(entry, "link"):
        href = link.attrib.get("href")
        if href:
            return clean_prompt_value(href)
    return child_text(entry, "link")
