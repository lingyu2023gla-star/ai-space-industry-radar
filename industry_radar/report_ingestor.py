from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .models import normalize_importance, normalize_industry, normalize_tags
from .text_utils import clean_text, truncate_text


HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
REPORT_ITEM_RE = re.compile(r"^####\s+\d+\.\s+(.+?)\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^-\s*([^：:]+)[：:]\s*(.*?)\s*$")


def read_markdown_file(path: str) -> str:
    markdown_path = Path(path)
    if not markdown_path.exists():
        raise FileNotFoundError(f"report file not found: {path}")
    try:
        return markdown_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"failed to read report file: {path}: {exc}") from exc


def extract_report_title(markdown: str, fallback: str = "Industry Radar Report") -> str:
    match = HEADING_RE.search(markdown)
    if not match:
        return clean_text(fallback)
    return clean_text(match.group(1)) or clean_text(fallback)


def extract_report_overview(markdown: str) -> str:
    sections = list(SECTION_RE.finditer(markdown))
    for index, match in enumerate(sections):
        if clean_text(match.group(1)) != "概览":
            continue
        start = match.end()
        end = sections[index + 1].start() if index + 1 < len(sections) else len(markdown)
        return clean_text(markdown[start:end])
    return ""


def extract_report_items(markdown: str) -> list[dict]:
    matches = list(REPORT_ITEM_RE.finditer(markdown))
    items = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        fields = parse_item_fields(markdown[start:end])
        title = clean_text(match.group(1))
        if title:
            fields["title"] = title
        items.append(fields)
    return items


def parse_item_fields(block: str) -> dict:
    fields = empty_report_item()
    label_map = {
        "日期": "date",
        "行业": "industry",
        "类别": "category",
        "公司": "company",
        "重要性": "importance",
        "标签": "tags",
        "来源": "source",
        "来源链接": "source_url",
        "摘要": "summary",
        "行业信号": "signal",
    }
    for line in block.splitlines():
        match = FIELD_RE.match(line.strip())
        if not match:
            continue
        key = label_map.get(clean_text(match.group(1)))
        if not key:
            continue
        value = clean_text(match.group(2))
        if key == "importance":
            value = parse_importance(value)
        elif key == "tags":
            value = normalize_tags(value)
        elif key == "industry":
            value = normalize_industry_or_original(value)
        fields[key] = value
    return fields


def empty_report_item() -> dict:
    return {
        "title": "",
        "date": "",
        "industry": "",
        "category": "",
        "company": "",
        "importance": "",
        "tags": "",
        "source": "",
        "source_url": "",
        "summary": "",
        "signal": "",
    }


def parse_importance(value: str) -> str:
    match = re.search(r"\d+", value)
    if not match:
        return ""
    try:
        return str(normalize_importance(match.group(0)))
    except ValueError:
        return ""


def normalize_industry_or_original(value: str) -> str:
    if not value:
        return ""
    try:
        return normalize_industry(value)
    except ValueError:
        return value


def build_report_summary_item(
    markdown: str,
    file_path: str,
    default_industry: str = "AI",
) -> dict:
    title = extract_report_title(markdown)
    overview = extract_report_overview(markdown)
    item_titles = [item.get("title", "") for item in extract_report_items(markdown) if item.get("title")]
    summary_parts = [overview]
    if item_titles:
        summary_parts.append("重点条目：" + "；".join(item_titles))
    summary = truncate_text(" ".join(part for part in summary_parts if part), max_length=1000)
    return {
        "date": date.today().isoformat(),
        "industry": normalize_industry(default_industry),
        "category": "Report",
        "company": "AI Space Industry Radar",
        "title": title,
        "source": "Generated Report",
        "source_url": file_url(file_path),
        "summary": summary or title,
        "signal": "Generated weekly industry brief",
        "tags": "Report;Brief;Industry Radar",
        "importance": 3,
    }


def convert_report_items_to_industry_items(report_items: list[dict], file_path: str) -> list[dict]:
    converted = []
    for index, item in enumerate(report_items, start=1):
        tags = append_report_tag(item.get("tags", ""))
        converted.append(
            {
                "date": item.get("date") or date.today().isoformat(),
                "industry": item.get("industry") or "AI",
                "category": item.get("category") or "Report Detail",
                "company": item.get("company") or "AI Space Industry Radar",
                "title": item.get("title", ""),
                "source": item.get("source") or "Generated Report",
                "source_url": item.get("source_url") or f"{file_url(file_path)}#item-{index}",
                "summary": item.get("summary") or item.get("title", ""),
                "signal": item.get("signal") or "Generated weekly industry brief item",
                "tags": tags,
                "importance": item.get("importance") or 3,
            }
        )
    return converted


def append_report_tag(tags: str) -> str:
    existing = [tag for tag in normalize_tags(tags).split(";") if tag]
    if "report" not in {tag.casefold() for tag in existing}:
        existing.append("Report")
    return normalize_tags(";".join(existing))


def ingest_report_file(
    path: str,
    include_summary_item: bool = True,
    include_detail_items: bool = True,
    default_industry: str = "AI",
) -> list[dict]:
    if not include_summary_item and not include_detail_items:
        return []
    markdown = read_markdown_file(path)
    candidates = []
    if include_summary_item:
        candidates.append(build_report_summary_item(markdown, path, default_industry=default_industry))
    if include_detail_items:
        candidates.extend(convert_report_items_to_industry_items(extract_report_items(markdown), path))
    return candidates


def file_url(path: str) -> str:
    return "file://" + str(Path(path).resolve())
