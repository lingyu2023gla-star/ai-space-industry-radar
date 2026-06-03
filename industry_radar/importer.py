from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import IndustryItem, clean_prompt_value
from .storage import append_item, read_items


@dataclass
class ImportResult:
    imported: int = 0
    skipped_duplicates: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def build_item_fingerprint(item: IndustryItem) -> str:
    source_url = clean_prompt_value(item.source_url).casefold()
    if source_url:
        return f"url:{source_url}"
    parts = [
        item.date,
        item.industry,
        item.company,
        item.title,
    ]
    normalized_parts = [clean_prompt_value(part).casefold() for part in parts]
    return "core:" + "|".join(normalized_parts)


def load_import_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        return load_json_records(path)
    if suffix == ".csv":
        return load_csv_records(path)
    raise ValueError("import file must be .json or .csv")


def load_json_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("JSON import file must contain a list")
    records: list[dict[str, Any]] = []
    for index, record in enumerate(data, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"JSON record {index} must be an object")
        records.append(record)
    return records


def load_csv_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError("CSV import file must contain a header row")
        return [dict(row) for row in reader]


def import_items(import_path: Path, storage_path: Path | None = None) -> ImportResult:
    records = load_import_records(import_path)
    return import_records(records, storage_path)


def import_records(
    records: list[dict[str, Any]],
    storage_path: Path | None = None,
) -> ImportResult:
    existing_items = read_items(storage_path) if storage_path else read_items()
    fingerprints = {build_item_fingerprint(item) for item in existing_items}
    result = ImportResult()

    for index, record in enumerate(records, start=1):
        try:
            item = IndustryItem.from_import_record(record)
            fingerprint = build_item_fingerprint(item)
            if fingerprint in fingerprints:
                result.skipped_duplicates += 1
                continue
            append_item(item, storage_path) if storage_path else append_item(item)
            fingerprints.add(fingerprint)
            result.imported += 1
        except (TypeError, ValueError) as exc:
            result.failed += 1
            result.errors.append(f"Record {index}: {exc}")

    return result
