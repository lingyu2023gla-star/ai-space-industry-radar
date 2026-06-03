import unittest
from dataclasses import replace

from industry_radar.data_governance import (
    build_dataset_stats,
    build_dedupe_fingerprint,
    build_event_fingerprint,
    dedupe_items,
    find_duplicate_groups,
    merge_duplicate_group,
)
from tests.test_storage import make_item


class DataGovernanceTest(unittest.TestCase):
    def test_build_dedupe_fingerprint_uses_source_url_first(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            source_url=" https://example.com/News ",
        )

        self.assertEqual(build_dedupe_fingerprint(item), "https://example.com/news")

    def test_build_dedupe_fingerprint_without_source_url_uses_core_fields(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            industry="AI",
            company="OpenAI",
            title="Agent Update",
        )

        self.assertEqual(
            build_dedupe_fingerprint(item),
            "2026-06-02|ai|openai|agent update",
        )

    def test_source_url_fingerprint_case_insensitive(self) -> None:
        first = make_item(item_id="1", item_date="2026-06-02", source_url="HTTPS://X.COM/A")
        second = make_item(item_id="2", item_date="2026-06-02", source_url="https://x.com/a")

        self.assertEqual(build_dedupe_fingerprint(first), build_dedupe_fingerprint(second))

    def test_core_fingerprint_case_insensitive(self) -> None:
        first = make_item(item_id="1", item_date="2026-06-02", company="OpenAI", title="Agent")
        second = make_item(item_id="2", item_date="2026-06-02", company="openai", title="agent")

        self.assertEqual(build_dedupe_fingerprint(first), build_dedupe_fingerprint(second))

    def test_event_fingerprint_case_insensitive(self) -> None:
        first = make_item(item_id="1", item_date="2026-06-02", industry="AI", company="OpenAI", title="Agent")
        second = make_item(item_id="2", item_date="2026-06-02", industry="ai", company="openai", title="agent")

        self.assertEqual(build_event_fingerprint(first), build_event_fingerprint(second))

    def test_event_fingerprint_compresses_title_whitespace(self) -> None:
        first = make_item(item_id="1", item_date="2026-06-02", title="OpenAI 推进 Agent 产品化")
        second = make_item(item_id="2", item_date="2026-06-02", title="OpenAI   推进 \n Agent  产品化")

        self.assertEqual(build_event_fingerprint(first), build_event_fingerprint(second))

    def test_find_duplicate_groups_identifies_duplicates(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", source_url="https://x.com/a"),
            make_item(item_id="2", item_date="2026-06-02", source_url="https://x.com/a"),
            make_item(item_id="3", item_date="2026-06-02", source_url="https://x.com/b"),
        ]

        groups = find_duplicate_groups(items)

        self.assertEqual(len(groups), 1)
        self.assertEqual({item.id for item in groups[0]}, {"1", "2"})

    def test_different_source_url_same_event_is_duplicate_group(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", company="OpenAI", title="OpenAI 推进 Agent 产品化", source_url="https://openai.com/a"),
            make_item(item_id="2", item_date="2026-06-02", company="OpenAI", title="OpenAI 推进 Agent 产品化", source_url="https://openai.com/b"),
        ]

        groups = find_duplicate_groups(items)

        self.assertEqual(len(groups), 1)
        self.assertEqual({item.id for item in groups[0]}, {"1", "2"})

    def test_missing_source_url_same_event_is_duplicate_group(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", company="OpenAI", title="OpenAI 推进 Agent 产品化", source_url="https://openai.com/a"),
            make_item(item_id="2", item_date="2026-06-02", company="OpenAI", title="OpenAI 推进 Agent 产品化", source_url=""),
        ]

        groups = find_duplicate_groups(items)

        self.assertEqual(len(groups), 1)
        self.assertEqual({item.id for item in groups[0]}, {"1", "2"})

    def test_cross_duplicates_are_merged_into_one_group(self) -> None:
        items = [
            make_item(item_id="a", item_date="2026-06-02", company="OpenAI", title="Event A", source_url="https://x.com/1"),
            make_item(item_id="b", item_date="2026-06-02", company="OpenAI", title="Event A", source_url="https://x.com/2"),
            make_item(item_id="c", item_date="2026-06-03", company="OpenAI", title="Event C", source_url="https://x.com/2"),
        ]

        groups = find_duplicate_groups(items)

        self.assertEqual(len(groups), 1)
        self.assertEqual({item.id for item in groups[0]}, {"a", "b", "c"})

    def test_dedupe_openai_sample_keeps_one_item(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", company="OpenAI", title="OpenAI 推进 Agent 产品化", source_url="https://openai.com/agent-demo", tags="Agent;AI", importance=4),
            make_item(item_id="2", item_date="2026-06-02", company="OpenAI", title="OpenAI 推进 Agent 产品化", source_url="https://openai.com", tags="AI;Product", importance=5),
            make_item(item_id="3", item_date="2026-06-02", company="OpenAI", title="OpenAI 推进 Agent 产品化", source_url="", tags="Product;Enterprise", importance=3),
        ]

        result = dedupe_items(items)

        self.assertEqual(result.remaining_items, 1)
        self.assertEqual(result.removed_duplicates, 2)
        self.assertEqual(set(result.items[0].tags.split(";")), {"Agent", "AI", "Product", "Enterprise"})
        self.assertEqual(result.items[0].importance, 5)

    def test_merge_duplicate_group_keeps_more_complete_record(self) -> None:
        sparse = replace(
            make_item(
                item_id="1",
                item_date="2026-06-02",
                source_url="https://x.com/a",
                importance=2,
            ),
            signal="",
            tags="",
        )
        complete = make_item(
            item_id="2",
            item_date="2026-06-02",
            source_url="https://x.com/a",
            summary="Summary",
            signal="Signal",
            tags="AI",
            importance=3,
        )

        merged = merge_duplicate_group([sparse, complete])

        self.assertEqual(merged.id, "2")
        self.assertEqual(merged.summary, "Summary")

    def test_merge_duplicate_group_merges_tags_and_dedupes(self) -> None:
        first = make_item(item_id="1", item_date="2026-06-02", tags="Agent;AI")
        second = make_item(item_id="2", item_date="2026-06-02", tags="AI;Product")

        merged = merge_duplicate_group([first, second])

        self.assertEqual(merged.tags, "Agent;AI;Product")

    def test_merge_duplicate_group_uses_highest_importance(self) -> None:
        first = make_item(item_id="1", item_date="2026-06-02", importance=2)
        second = make_item(item_id="2", item_date="2026-06-02", importance=5)

        merged = merge_duplicate_group([first, second])

        self.assertEqual(merged.importance, 5)

    def test_dedupe_items_dry_run_result_contains_deduped_items_without_writing(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", source_url="https://x.com/a"),
            make_item(item_id="2", item_date="2026-06-02", source_url="https://x.com/a"),
        ]

        result = dedupe_items(items)

        self.assertEqual(result.duplicate_groups, 1)
        self.assertEqual(result.removed_duplicates, 1)
        self.assertEqual(result.remaining_items, 1)

    def test_stats_industry_distribution(self) -> None:
        stats = build_dataset_stats(
            [
                make_item(item_id="1", item_date="2026-06-02", industry="AI"),
                make_item(item_id="2", item_date="2026-06-02", industry="AI"),
            ]
        )

        self.assertEqual(stats["industry"]["AI"], 2)

    def test_stats_tags_distribution(self) -> None:
        stats = build_dataset_stats(
            [
                make_item(item_id="1", item_date="2026-06-02", tags="AI;Agent"),
                make_item(item_id="2", item_date="2026-06-02", tags="AI;Product"),
            ]
        )

        self.assertEqual(stats["tags"]["AI"], 2)

    def test_stats_importance_distribution(self) -> None:
        stats = build_dataset_stats(
            [
                make_item(item_id="1", item_date="2026-06-02", importance=5),
                make_item(item_id="2", item_date="2026-06-02", importance=3),
                make_item(item_id="3", item_date="2026-06-02", importance=3),
            ]
        )

        self.assertEqual(stats["importance"][3], 2)


if __name__ == "__main__":
    unittest.main()
