import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.importer import build_item_fingerprint, import_items
from industry_radar.models import IndustryItem
from industry_radar.storage import read_items


def import_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "date": "2026-06-02",
        "industry": "AI",
        "category": "Agent",
        "company": "OpenAI",
        "title": "OpenAI 推进 Agent 产品化",
        "source": "OpenAI Blog",
        "source_url": "https://openai.com/blog/agent",
        "summary": "Summary",
        "signal": "Signal",
        "tags": "Agent;Product",
        "importance": 5,
    }
    record.update(overrides)
    return record


def write_json(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, records: list[dict[str, object]]) -> None:
    fieldnames = list(records[0].keys())
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


class ImporterTest(unittest.TestCase):
    def test_json_import_success(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            import_path = Path(tmp_dir) / "items.json"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_json(import_path, [import_record()])

            result = import_items(import_path, storage_path)

            self.assertEqual(result.imported, 1)
            self.assertEqual(read_items(storage_path)[0].company, "OpenAI")

    def test_csv_import_success(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            import_path = Path(tmp_dir) / "items.csv"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_csv(import_path, [import_record()])

            result = import_items(import_path, storage_path)

            self.assertEqual(result.imported, 1)
            self.assertEqual(read_items(storage_path)[0].title, "OpenAI 推进 Agent 产品化")

    def test_duplicate_source_url_is_skipped(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            import_path = Path(tmp_dir) / "items.json"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_json(
                import_path,
                [
                    import_record(source_url="https://example.com/news"),
                    import_record(title="Different title", source_url=" HTTPS://EXAMPLE.COM/NEWS "),
                ],
            )

            result = import_items(import_path, storage_path)

            self.assertEqual(result.imported, 1)
            self.assertEqual(result.skipped_duplicates, 1)
            self.assertEqual(len(read_items(storage_path)), 1)

    def test_duplicate_core_fields_without_source_url_are_skipped(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            import_path = Path(tmp_dir) / "items.json"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_json(
                import_path,
                [
                    import_record(source_url=""),
                    import_record(source_url="", summary="Different summary"),
                ],
            )

            result = import_items(import_path, storage_path)

            self.assertEqual(result.imported, 1)
            self.assertEqual(result.skipped_duplicates, 1)

    def test_invalid_importance_fails_one_record_and_continues(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            import_path = Path(tmp_dir) / "items.json"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_json(
                import_path,
                [
                    import_record(title="Bad", source_url="https://bad.example", importance=6),
                    import_record(title="Good", source_url="https://good.example"),
                ],
            )

            result = import_items(import_path, storage_path)

            self.assertEqual(result.imported, 1)
            self.assertEqual(result.failed, 1)
            self.assertIn("Record 1", result.errors[0])
            self.assertEqual(read_items(storage_path)[0].title, "Good")

    def test_tags_are_normalized_during_import(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            import_path = Path(tmp_dir) / "items.json"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_json(import_path, [import_record(tags=" Agent ; RAG；Product ")])

            result = import_items(import_path, storage_path)

            self.assertEqual(result.imported, 1)
            self.assertEqual(read_items(storage_path)[0].tags, "Agent;RAG;Product")

    def test_industry_alias_is_normalized_during_import(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            import_path = Path(tmp_dir) / "items.json"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_json(import_path, [import_record(industry="商业航天")])

            result = import_items(import_path, storage_path)

            self.assertEqual(result.imported, 1)
            self.assertEqual(read_items(storage_path)[0].industry, "Commercial Space")

    def test_build_item_fingerprint_uses_source_url_first(self) -> None:
        item = IndustryItem.from_import_record(import_record(source_url=" HTTPS://X.COM/A "))

        self.assertEqual(build_item_fingerprint(item), "url:https://x.com/a")


if __name__ == "__main__":
    unittest.main()
