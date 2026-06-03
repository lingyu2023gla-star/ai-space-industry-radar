from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime

from .models import IndustryItem, clean_prompt_value, normalize_tags


@dataclass
class DedupeResult:
    duplicate_groups: int
    removed_duplicates: int
    remaining_items: int
    items: list[IndustryItem]
    groups: list[list[IndustryItem]]


def build_dataset_stats(items: list[IndustryItem]) -> dict[str, object]:
    dates = [item.date for item in items if item.date]
    return {
        "total": len(items),
        "industry": Counter(item.industry for item in items if item.industry),
        "category": Counter(item.category for item in items if item.category),
        "tags": build_tag_counter(items),
        "company": Counter(item.company for item in items if item.company),
        "date_range": (min(dates), max(dates)) if dates else ("", ""),
        "importance": Counter(item.importance for item in items),
    }


def build_tag_counter(items: list[IndustryItem]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for item in items:
        for tag in item.tags.split(";"):
            cleaned = tag.strip()
            if cleaned:
                counter[cleaned] += 1
    return counter


def build_dedupe_fingerprint(item: IndustryItem) -> str:
    source_url = clean_prompt_value(item.source_url).casefold()
    if source_url:
        return source_url
    return build_event_fingerprint(item)


def build_event_fingerprint(item: IndustryItem) -> str:
    parts = [item.date, item.industry, item.company, item.title]
    normalized = [clean_prompt_value(part).casefold() for part in parts]
    normalized[-1] = re.sub(r"\s+", " ", normalized[-1]).strip()
    return "|".join(normalized)


def build_item_dedupe_fingerprints(item: IndustryItem) -> list[str]:
    fingerprints = [f"event:{build_event_fingerprint(item)}"]
    source_url = clean_prompt_value(item.source_url).casefold()
    if source_url:
        fingerprints.append(f"url:{source_url}")
    return fingerprints


def find_duplicate_groups(items: list[IndustryItem]) -> list[list[IndustryItem]]:
    if not items:
        return []

    parent = list(range(len(items)))
    fingerprint_owner: dict[str, int] = {}

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for index, item in enumerate(items):
        for fingerprint in build_item_dedupe_fingerprints(item):
            if fingerprint in fingerprint_owner:
                union(index, fingerprint_owner[fingerprint])
            else:
                fingerprint_owner[fingerprint] = index

    grouped: dict[int, list[IndustryItem]] = defaultdict(list)
    for index, item in enumerate(items):
        grouped[find(index)].append(item)
    return [group for group in grouped.values() if len(group) > 1]


def merge_duplicate_group(items: list[IndustryItem]) -> IndustryItem:
    if not items:
        raise ValueError("duplicate group is empty")
    primary = sorted(items, key=item_completeness_score, reverse=True)[0]
    summary = first_value(primary.summary, [item.summary for item in items])
    signal = first_value(primary.signal, [item.signal for item in items])
    source = first_value(primary.source, [item.source for item in items])
    tags = merge_tags([item.tags for item in items])
    importance = max(item.importance for item in items)
    return replace(
        primary,
        summary=summary,
        signal=signal,
        source=source,
        tags=tags,
        importance=importance,
        updated_at=datetime.now().replace(microsecond=0).isoformat(),
    )


def item_completeness_score(item: IndustryItem) -> tuple[int, int, int, int, int, str]:
    fields = [
        item.source_url,
        item.summary,
        item.signal,
        item.tags,
        item.source,
        item.created_at,
        item.updated_at,
    ]
    completeness = sum(1 for value in fields if clean_prompt_value(value))
    return (
        completeness,
        1 if clean_prompt_value(item.source_url) else 0,
        1 if clean_prompt_value(item.summary) else 0,
        1 if clean_prompt_value(item.signal) else 0,
        item.importance,
        item.updated_at,
    )


def first_value(primary_value: str, values: list[str]) -> str:
    if clean_prompt_value(primary_value):
        return primary_value
    for value in values:
        if clean_prompt_value(value):
            return value
    return ""


def merge_tags(values: list[str]) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for tag in normalize_tags(value).split(";"):
            if not tag:
                continue
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                merged.append(tag)
    return ";".join(merged)


def dedupe_items(items: list[IndustryItem]) -> DedupeResult:
    duplicate_groups = find_duplicate_groups(items)
    replacement_by_id: dict[str, IndustryItem] = {}
    remove_ids: set[str] = set()
    for group in duplicate_groups:
        merged = merge_duplicate_group(group)
        replacement_by_id[merged.id] = merged
        for item in group:
            if item.id != merged.id:
                remove_ids.add(item.id)

    deduped_items = [
        replacement_by_id.get(item.id, item)
        for item in items
        if item.id not in remove_ids
    ]
    return DedupeResult(
        duplicate_groups=len(duplicate_groups),
        removed_duplicates=len(remove_ids),
        remaining_items=len(deduped_items),
        items=deduped_items,
        groups=duplicate_groups,
    )
