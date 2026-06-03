import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.dashboard import (
    build_dashboard_data,
    render_dashboard_html,
    write_dashboard_html,
)


def item(**overrides) -> dict:
    data = {
        "date": "2026-06-02",
        "industry": "AI",
        "category": "Research",
        "company": "OpenAI",
        "title": "Agent update",
        "importance": 3,
        "tags": "AI;Agent",
    }
    data.update(overrides)
    return data


class DashboardTest(unittest.TestCase):
    def test_build_dashboard_data_counts_total_items(self) -> None:
        data = build_dashboard_data([item(), item(title="Second")])

        self.assertEqual(data["total_items"], 2)

    def test_build_dashboard_data_counts_industry_distribution(self) -> None:
        data = build_dashboard_data([item(industry="AI"), item(industry="Commercial Space")])

        self.assertEqual(data["industry_distribution"]["AI"], 1)
        self.assertEqual(data["industry_distribution"]["Commercial Space"], 1)

    def test_build_dashboard_data_counts_tag_distribution(self) -> None:
        data = build_dashboard_data([item(tags="AI;Agent"), item(tags="AI;Research")])

        self.assertEqual(data["tag_distribution"]["AI"], 2)
        self.assertEqual(data["tag_distribution"]["Agent"], 1)

    def test_build_dashboard_data_counts_importance_distribution(self) -> None:
        data = build_dashboard_data([item(importance=5), item(importance=3)])

        self.assertEqual(data["importance_distribution"]["5"], 1)
        self.assertEqual(data["importance_distribution"]["3"], 1)

    def test_build_dashboard_data_sorts_recent_items_by_date_and_importance(self) -> None:
        data = build_dashboard_data(
            [
                item(date="2026-06-01", importance=5, title="Old"),
                item(date="2026-06-02", importance=3, title="New Low"),
                item(date="2026-06-02", importance=5, title="New High"),
            ]
        )

        self.assertEqual(data["recent_items"][0]["title"], "New High")

    def test_build_dashboard_data_recent_items_respects_top_n(self) -> None:
        data = build_dashboard_data([item(title="One"), item(title="Two")], top_n=1)

        self.assertEqual(len(data["recent_items"]), 1)

    def test_render_dashboard_html_returns_complete_html(self) -> None:
        html = render_dashboard_html(build_dashboard_data([]))

        self.assertIn("<!doctype html>", html)
        self.assertIn("</html>", html)

    def test_render_dashboard_html_contains_overview(self) -> None:
        html = render_dashboard_html(build_dashboard_data([]))

        self.assertIn("Overview", html)

    def test_render_dashboard_html_contains_recent_items(self) -> None:
        html = render_dashboard_html(build_dashboard_data([item()]))

        self.assertIn("Recent Items", html)

    def test_render_dashboard_html_escapes_title_and_item_title(self) -> None:
        data = build_dashboard_data([item(title="<script>alert(1)</script>")])

        html = render_dashboard_html(data, title="<Dashboard>")

        self.assertIn("&lt;Dashboard&gt;", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_render_dashboard_html_empty_tables_show_no_data(self) -> None:
        html = render_dashboard_html(build_dashboard_data([]))

        self.assertIn("No data", html)

    def test_write_dashboard_html_writes_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dashboard.html"

            result = write_dashboard_html("<html></html>", str(output_path))

            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
