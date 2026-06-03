from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from pathlib import Path

from .models import FIELDNAMES, IndustryItem, clean_prompt_value


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "industry_items.csv"


class StorageBackend(ABC):
    @abstractmethod
    def read_items(self) -> list[IndustryItem]:
        ...

    @abstractmethod
    def write_items(self, items: list[IndustryItem]) -> None:
        ...

    @abstractmethod
    def append_items(self, items: list[IndustryItem]) -> None:
        ...

    def append_item(self, item: IndustryItem) -> None:
        self.append_items([item])


class CsvStorage(StorageBackend):
    def __init__(self, path: str | Path = DEFAULT_DATA_PATH):
        self.path = Path(path)

    def read_items(self) -> list[IndustryItem]:
        self.ensure_csv()
        items: list[IndustryItem] = []
        with self.path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if not any(row.values()):
                    continue
                items.append(IndustryItem.from_row(row))
        return items

    def write_items(self, items: list[IndustryItem]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
            for item in items:
                writer.writerow(self._item_to_row(item))

    def append_items(self, items: list[IndustryItem]) -> None:
        self.ensure_csv()
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            for item in items:
                writer.writerow(self._item_to_row(item))

    def ensure_csv(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists() or self.path.stat().st_size == 0:
            with self.path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
                writer.writeheader()
            return
        self.migrate_csv()

    def migrate_csv(self) -> None:
        with self.path.open("r", newline="", encoding="utf-8") as file:
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

        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(migrated_rows)

    @staticmethod
    def _item_to_row(item: IndustryItem) -> dict[str, str]:
        if isinstance(item, IndustryItem):
            return item.to_row()
        if isinstance(item, dict):
            return IndustryItem.from_row(item).to_row()
        raise TypeError("item must be an IndustryItem or dict")


def get_storage_backend(
    kind: str = "csv",
    path: str | Path | None = None,
) -> StorageBackend:
    if kind == "csv":
        return CsvStorage(path or DEFAULT_DATA_PATH)
    raise ValueError(f"Unsupported storage backend: {kind}")
