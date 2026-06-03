import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.models import FIELDNAMES, IndustryItem
from industry_radar.storage import append_item, filter_items, read_items, sort_by_date_desc


def make_item(
    *,
    item_id: str,
    item_date: str,
    industry: str = "AI",
    category: str = "funding",
    company: str = "ExampleCo",
    title: str | None = None,
    source_url: str = "",
    summary: str = "Short summary",
    signal: str = "Market signal",
    tags: str = "",
    importance: int = 3,
    created_at: str = "",
) -> IndustryItem:
    return IndustryItem(
        id=item_id,
        date=item_date,
        industry=industry,
        category=category,
        company=company,
        title=title or f"Item {item_id}",
        source="https://example.com",
        source_url=source_url,
        summary=summary,
        signal=signal,
        tags=tags,
        importance=importance,
        created_at=created_at,
        updated_at="",
    )


class StorageTest(unittest.TestCase):
    def test_append_and_read_items(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "industry_items.csv"
            item = make_item(item_id="1", item_date="2026-06-02")

            append_item(item, csv_path)

            self.assertEqual(read_items(csv_path), [item])

    def test_read_items_normalizes_legacy_prompt_label(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "industry_items.csv"
            item = make_item(
                item_id="1",
                item_date="2026-06-02",
                industry="Industry [AI/Commercial Space]: AI",
            )

            append_item(item, csv_path)

            self.assertEqual(read_items(csv_path)[0].industry, "AI")

    def test_read_old_csv_missing_new_fields(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "industry_items.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "id,date,industry,category,company,title,source,summary,signal,importance",
                        "1,2026-06-02,AI,Agent,OpenAI,Title,OpenAI Blog,Summary,Signal,5",
                    ]
                ),
                encoding="utf-8",
            )

            item = read_items(csv_path)[0]

            self.assertEqual(item.source_url, "")
            self.assertEqual(item.tags, "")
            self.assertEqual(item.created_at, "")
            self.assertEqual(item.updated_at, "")

    def test_append_item_migrates_csv_header(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "industry_items.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "id,date,industry,category,company,title,source,summary,signal,importance",
                        "1,2026-06-02,AI,Agent,OpenAI,Title,OpenAI Blog,Summary,Signal,5",
                    ]
                ),
                encoding="utf-8",
            )
            item = make_item(item_id="2", item_date="2026-06-03", tags="Agent;Product")

            append_item(item, csv_path)

            with csv_path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                rows = list(reader)
            self.assertEqual(reader.fieldnames, FIELDNAMES)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["id"], "1")
            self.assertEqual(rows[0]["source_url"], "")
            self.assertEqual(rows[1]["tags"], "Agent;Product")

    def test_create_item_sets_timestamps(self) -> None:
        item = IndustryItem.create(
            industry="AI",
            category="Agent",
            company="OpenAI",
            title="Title",
            source="OpenAI Blog",
            source_url="https://example.com",
            summary="Summary",
            signal="Signal",
            tags="Agent;Product",
            importance=5,
        )

        self.assertTrue(item.created_at)
        self.assertEqual(item.created_at, item.updated_at)

    def test_filter_items_by_industry_and_category(self) -> None:
        items = [
            make_item(
                item_id="1",
                item_date="2026-06-02",
                industry="AI",
                category="model",
            ),
            make_item(
                item_id="2",
                item_date="2026-06-01",
                industry="Space",
                category="launch",
            ),
        ]

        result = filter_items(items, industry="ai", category="MODEL")

        self.assertEqual([item.id for item in result], ["1"])

    def test_filter_items_by_industry_alias(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", industry="AI"),
            make_item(
                item_id="2",
                item_date="2026-06-01",
                industry="Commercial Space",
            ),
        ]

        result = filter_items(items, industry="商业航天")

        self.assertEqual([item.id for item in result], ["2"])

    def test_filter_items_by_tag_case_insensitive(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", tags="Agent;Product"),
            make_item(item_id="2", item_date="2026-06-02", tags="Satellite"),
        ]

        result = filter_items(items, tag="agent")

        self.assertEqual([item.id for item in result], ["1"])

    def test_filter_items_by_company_contains_case_insensitive(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", company="OpenAI"),
            make_item(item_id="2", item_date="2026-06-02", company="SpaceX"),
        ]

        result = filter_items(items, company="open")

        self.assertEqual([item.id for item in result], ["1"])

    def test_filter_items_by_since(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-01"),
            make_item(item_id="2", item_date="2026-06-03"),
        ]

        result = filter_items(items, since="2026-06-02")

        self.assertEqual([item.id for item in result], ["2"])

    def test_filter_items_by_until(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-01"),
            make_item(item_id="2", item_date="2026-06-03"),
        ]

        result = filter_items(items, until="2026-06-02")

        self.assertEqual([item.id for item in result], ["1"])

    def test_filter_items_by_since_and_until(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-01"),
            make_item(item_id="2", item_date="2026-06-02"),
            make_item(item_id="3", item_date="2026-06-03"),
        ]

        result = filter_items(items, since="2026-06-02", until="2026-06-02")

        self.assertEqual([item.id for item in result], ["2"])

    def test_sort_by_date_desc(self) -> None:
        items = [
            make_item(item_id="old", item_date="2026-05-31"),
            make_item(item_id="new", item_date="2026-06-02"),
        ]

        result = sort_by_date_desc(items)

        self.assertEqual([item.id for item in result], ["new", "old"])


if __name__ == "__main__":
    unittest.main()
