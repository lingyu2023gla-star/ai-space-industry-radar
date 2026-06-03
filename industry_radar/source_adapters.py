from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from .models import clean_prompt_value, normalize_industry, normalize_tags
from .text_utils import truncate_text


USER_AGENT = "Mozilla/5.0 (compatible; ai-space-industry-radar/0.5; +https://example.com)"


class SourceAdapter:
    source_type = "base"

    def fetch(self, source: dict, limit: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError


class RSSSourceAdapter(SourceAdapter):
    source_type = "rss"

    def fetch(self, source: dict, limit: int = 10) -> list[dict[str, Any]]:
        entries = parse_feed_xml(read_url(source["url"]))[:limit]
        records = []
        for entry in entries:
            records.append(
                feed_entry_to_import_record(
                    entry,
                    source,
                    fallback_date=source.get("_fallback_date"),
                )
            )
        return records


def get_source_adapter(source_type: str | None) -> SourceAdapter:
    normalized = clean_prompt_value(source_type).casefold() or "rss"
    if normalized in {"rss", "atom"}:
        return RSSSourceAdapter()
    raise ValueError(f"Unsupported source type: {source_type}")


def validate_source_config(source: dict) -> dict[str, str]:
    source_type = clean_prompt_value(str(source.get("type", ""))).casefold() or "rss"
    normalized = {
        "type": source_type,
        "name": clean_prompt_value(str(source.get("name", ""))),
        "url": clean_prompt_value(str(source.get("url", ""))),
        "industry": normalize_industry(str(source.get("industry", ""))),
        "category": clean_prompt_value(str(source.get("category", ""))),
        "default_tags": normalize_tags(str(source.get("default_tags", ""))),
    }
    if not normalized["name"]:
        raise ValueError("source missing required field: name")
    if not normalized["industry"]:
        raise ValueError("source missing required field: industry")
    if source_type in {"rss", "atom"} and not normalized["url"]:
        raise ValueError("source missing required field: url")
    return normalized


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
