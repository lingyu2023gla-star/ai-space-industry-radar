from __future__ import annotations

import csv
from pathlib import Path

from .models import (
    FIELDNAMES,
    IndustryItem,
    clean_prompt_value,
    normalize_industry,
    normalize_tags,
    validate_date,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "industry_items.csv"


def migrate_csv(path: Path) -> None:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        current_fieldnames = reader.fieldnames or []
        rows = list(reader)

    if current_fieldnames == FIELDNAMES:
        return

    migrated_rows = []
    for row in rows:
        migrated_rows.append(
            {field: clean_prompt_value(str(row.get(field, ""))) for field in FIELDNAMES}
        )

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(migrated_rows)


def ensure_csv(path: Path = DEFAULT_CSV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
        return
    migrate_csv(path)


def read_items(path: Path = DEFAULT_CSV_PATH) -> list[IndustryItem]:
    ensure_csv(path)
    items: list[IndustryItem] = []
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if not any(row.values()):
                continue
            items.append(IndustryItem.from_row(row))
    return items


def append_item(item: IndustryItem, path: Path = DEFAULT_CSV_PATH) -> None:
    ensure_csv(path)
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writerow(item.to_row())


def write_items(items: list[IndustryItem], path: Path = DEFAULT_CSV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for item in items:
            writer.writerow(item.to_row())


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
