import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.models import FIELDNAMES
from industry_radar.pipeline import run_pipeline
from industry_radar.storage import append_item, read_items, write_items
from industry_radar.storage_backend import CsvStorage, get_storage_backend
from tests.test_storage import make_item


class StorageBackendTest(unittest.TestCase):
    def test_csv_storage_reads_empty_csv(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            storage = CsvStorage(Path(tmp_dir) / "items.csv")

            self.assertEqual(storage.read_items(), [])

    def test_csv_storage_writes_and_reads_items(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            storage = CsvStorage(Path(tmp_dir) / "items.csv")
            item = make_item(item_id="1", item_date="2026-06-02")

            storage.write_items([item])

            self.assertEqual(storage.read_items(), [item])

    def test_csv_storage_append_items_adds_multiple_items(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            storage = CsvStorage(Path(tmp_dir) / "items.csv")
            items = [
                make_item(item_id="1", item_date="2026-06-02"),
                make_item(item_id="2", item_date="2026-06-03"),
            ]

            storage.append_items(items)

            self.assertEqual(storage.read_items(), items)

    def test_csv_storage_append_item_adds_single_item(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            storage = CsvStorage(Path(tmp_dir) / "items.csv")
            item = make_item(item_id="1", item_date="2026-06-02")

            storage.append_item(item)

            self.assertEqual(storage.read_items(), [item])

    def test_csv_storage_uses_complete_field_order(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "items.csv"
            storage = CsvStorage(path)

            storage.write_items([make_item(item_id="1", item_date="2026-06-02")])

            with path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                self.assertEqual(reader.fieldnames, FIELDNAMES)

    def test_csv_storage_reads_legacy_csv(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "items.csv"
            path.write_text(
                "\n".join(
                    [
                        "id,date,industry,category,company,title,source,summary,signal,importance",
                        "1,2026-06-02,AI,Agent,OpenAI,Title,OpenAI Blog,Summary,Signal,5",
                    ]
                ),
                encoding="utf-8",
            )
            item = CsvStorage(path).read_items()[0]

            self.assertEqual(item.source_url, "")
            self.assertEqual(item.tags, "")
            self.assertEqual(item.created_at, "")
            self.assertEqual(item.updated_at, "")

    def test_storage_compat_functions_still_work(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "items.csv"
            item = make_item(item_id="1", item_date="2026-06-02")
            replacement = make_item(item_id="2", item_date="2026-06-03")

            append_item(item, path)
            self.assertEqual(read_items(path), [item])

            write_items([replacement], path)
            self.assertEqual(read_items(path), [replacement])

    def test_get_storage_backend_csv_returns_csv_storage(self) -> None:
        storage = get_storage_backend("csv")

        self.assertIsInstance(storage, CsvStorage)

    def test_get_storage_backend_unknown_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_storage_backend("unknown")

    def test_pipeline_accepts_csv_storage_backend(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            storage = CsvStorage(Path(tmp_dir) / "items.csv")
            item = make_item(item_id="1", item_date="2026-06-02")
            storage.write_items([item])

            result = run_pipeline(
                report_path=Path(tmp_dir) / "report.md",
                apply=False,
                storage=storage,
            )

            self.assertEqual(result.mode, "dry-run")
            self.assertEqual(storage.read_items(), [item])
