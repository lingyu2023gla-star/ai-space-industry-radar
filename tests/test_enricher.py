import json
import unittest

from industry_radar.enricher import (
    build_enrichment_prompt,
    merge_enrichment,
    parse_enrichment_result,
)
from tests.test_storage import make_item


class EnricherTest(unittest.TestCase):
    def test_build_enrichment_prompt_returns_messages(self) -> None:
        messages = build_enrichment_prompt(make_item(item_id="1", item_date="2026-06-02"))

        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")

    def test_prompt_contains_json_and_example_json(self) -> None:
        messages = build_enrichment_prompt(make_item(item_id="1", item_date="2026-06-02"))
        content = "\n".join(message["content"] for message in messages)

        self.assertIn("JSON", content)
        self.assertIn("示例 JSON", content)
        self.assertIn('"importance": 4', content)

    def test_parse_enrichment_result_parses_valid_json(self) -> None:
        result = parse_enrichment_result(
            json.dumps(
                {
                    "summary": "<p>中文摘要</p>",
                    "signal": "行业信号",
                    "tags": " Agent ; Product；AI ",
                    "importance": 4,
                },
                ensure_ascii=False,
            )
        )

        self.assertEqual(result["summary"], "中文摘要")
        self.assertEqual(result["signal"], "行业信号")
        self.assertEqual(result["tags"], "Agent;Product;AI")
        self.assertEqual(result["importance"], 4)

    def test_parse_enrichment_result_missing_field_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_enrichment_result('{"summary": "摘要"}')

    def test_parse_enrichment_result_invalid_importance_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_enrichment_result(
                '{"summary": "摘要", "signal": "信号", "tags": "AI", "importance": 6}'
            )

    def test_parse_enrichment_result_normalizes_tags(self) -> None:
        result = parse_enrichment_result(
            '{"summary": "摘要", "signal": "信号", "tags": " AI； Product ", "importance": 3}'
        )

        self.assertEqual(result["tags"], "AI;Product")

    def test_parse_enrichment_result_empty_content_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_enrichment_result("")

    def test_merge_enrichment_without_overwrite_keeps_existing_fields(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            summary="Existing summary",
            signal="Existing signal",
            tags="Existing",
            importance=2,
        )

        merged = merge_enrichment(
            item,
            {
                "summary": "New summary",
                "signal": "New signal",
                "tags": "New",
                "importance": 5,
            },
        )

        self.assertEqual(merged.summary, "Existing summary")
        self.assertEqual(merged.signal, "Existing signal")
        self.assertEqual(merged.tags, "Existing")
        self.assertEqual(merged.importance, 2)

    def test_merge_enrichment_with_overwrite_replaces_fields(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02", importance=2)

        merged = merge_enrichment(
            item,
            {
                "summary": "New summary",
                "signal": "New signal",
                "tags": "New",
                "importance": 5,
            },
            overwrite=True,
        )

        self.assertEqual(merged.summary, "New summary")
        self.assertEqual(merged.signal, "New signal")
        self.assertEqual(merged.tags, "New")
        self.assertEqual(merged.importance, 5)

    def test_merge_enrichment_preserves_identity_fields(self) -> None:
        item = make_item(
            item_id="id-1",
            item_date="2026-06-02",
            source_url="https://example.com/news",
            created_at="2026-06-02T10:00:00",
        )

        merged = merge_enrichment(
            item,
            {
                "summary": "New summary",
                "signal": "New signal",
                "tags": "New",
                "importance": 5,
            },
            overwrite=True,
        )

        self.assertEqual(merged.id, item.id)
        self.assertEqual(merged.date, item.date)
        self.assertEqual(merged.source_url, item.source_url)
        self.assertEqual(merged.created_at, item.created_at)
        self.assertNotEqual(merged.updated_at, item.updated_at)


if __name__ == "__main__":
    unittest.main()
