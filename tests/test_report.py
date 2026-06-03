import unittest

from industry_radar.report import generate_markdown, sort_report_items
from tests.test_storage import make_item


class ReportTest(unittest.TestCase):
    def test_report_sorting_orders_by_importance_desc(self) -> None:
        items = [
            make_item(item_id="low", item_date="2026-06-03", importance=1),
            make_item(item_id="high", item_date="2026-06-01", importance=5),
        ]

        result = sort_report_items(items)

        self.assertEqual([item.id for item in result], ["high", "low"])

    def test_report_top_limits_output(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-01", title="First", importance=5),
            make_item(item_id="2", item_date="2026-06-02", title="Second", importance=4),
        ]

        markdown = generate_markdown(items, top=1)

        self.assertIn("First", markdown)
        self.assertNotIn("Second", markdown)

    def test_report_stats_include_record_count(self) -> None:
        markdown = generate_markdown([make_item(item_id="1", item_date="2026-06-02")])

        self.assertIn("- 记录数量：1", markdown)

    def test_report_stats_include_industry_distribution(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", industry="AI"),
            make_item(item_id="2", item_date="2026-06-02", industry="Commercial Space"),
        ]

        markdown = generate_markdown(items)

        self.assertIn("- AI：1", markdown)
        self.assertIn("- Commercial Space：1", markdown)

    def test_report_stats_include_tag_distribution(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", tags="AI;Research"),
            make_item(item_id="2", item_date="2026-06-02", tags="AI;Product"),
        ]

        markdown = generate_markdown(items)

        self.assertIn("- AI：2", markdown)
        self.assertIn("- Research：1", markdown)


if __name__ == "__main__":
    unittest.main()
