from __future__ import annotations

from pathlib import Path

from .models import (
    IndustryItem,
    clean_prompt_value,
    normalize_industry,
    normalize_tags,
    validate_date,
)
from .storage_backend import DEFAULT_DATA_PATH, PROJECT_ROOT, CsvStorage


def migrate_csv(path: Path) -> None:
    CsvStorage(path).migrate_csv()


DEFAULT_CSV_PATH = DEFAULT_DATA_PATH


def ensure_csv(path: Path = DEFAULT_CSV_PATH) -> None:
    CsvStorage(path).ensure_csv()


def append_item(item: IndustryItem, path: Path = DEFAULT_CSV_PATH) -> None:
    CsvStorage(path).append_item(item)


def append_items(items: list[IndustryItem], path: Path = DEFAULT_CSV_PATH) -> None:
    CsvStorage(path).append_items(items)


def read_items(path: Path = DEFAULT_CSV_PATH) -> list[IndustryItem]:
    return CsvStorage(path).read_items()


def write_items(items: list[IndustryItem], path: Path = DEFAULT_CSV_PATH) -> None:
    CsvStorage(path).write_items(items)


def filter_items(
    items: list[IndustryItem],
    *,
    industry: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    company: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[IndustryItem]:
    filtered = items
    if industry:
        industry_value = normalize_industry(industry)
        filtered = [item for item in filtered if item.industry == industry_value]
    if category:
        category_value = clean_prompt_value(category).casefold()
        filtered = [
            item for item in filtered if item.category.casefold() == category_value
        ]
    if tag:
        tag_value = normalize_tags(tag).casefold()
        filtered = [
            item
            for item in filtered
            if tag_value
            in {tag_part.casefold() for tag_part in normalize_tags(item.tags).split(";")}
        ]
    if company:
        company_value = clean_prompt_value(company).casefold()
        filtered = [
            item for item in filtered if company_value in item.company.casefold()
        ]
    if since:
        since_value = validate_date(since)
        filtered = [item for item in filtered if item.date >= since_value]
    if until:
        until_value = validate_date(until)
        filtered = [item for item in filtered if item.date <= until_value]
    return filtered


def sort_by_date_desc(items: list[IndustryItem]) -> list[IndustryItem]:
    return sorted(items, key=lambda item: (item.date, item.id), reverse=True)
