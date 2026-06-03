import unittest
import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from industry_radar.cli import main
from industry_radar.run_logger import add_step, create_run_log, finalize_run_log, write_run_log
from tests.test_storage import make_item


class ReportCliTest(unittest.TestCase):
    def test_report_filters_by_industry(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", industry="AI"),
            make_item(
                item_id="2",
                item_date="2026-06-02",
                industry="Commercial Space",
            ),
        ]
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "ai_report.md"
            with patch("industry_radar.cli.read_items", return_value=items):
                exit_code = main(
                    [
                        "report",
                        "--industry",
                        "AI",
                        "--output",
                        str(output_path),
                    ]
                )

            content = output_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertIn("- 行业：AI", content)
            self.assertNotIn("- 行业：Commercial Space", content)

    def test_report_writes_custom_output_path(self) -> None:
        items = [make_item(item_id="1", item_date="2026-06-02", industry="AI")]
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "custom_report.md"
            with patch("industry_radar.cli.read_items", return_value=items):
                exit_code = main(["report", "--output", str(output_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())

    def test_report_supports_top_argument(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", title="Top", importance=5),
            make_item(item_id="2", item_date="2026-06-02", title="Hidden", importance=1),
        ]
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "top_report.md"
            with patch("industry_radar.cli.read_items", return_value=items):
                exit_code = main(
                    ["report", "--top", "1", "--output", str(output_path)]
                )

            content = output_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertIn("Top", content)
            self.assertNotIn("Hidden", content)

    def test_enrich_dry_run_does_not_write_csv(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02", tags="")
        llm_content = (
            '{"summary": "增强摘要", "signal": "增强信号", '
            '"tags": "AI;Agent", "importance": 4}'
        )

        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.call_deepseek_chat", return_value=llm_content):
                with patch("industry_radar.cli.write_items") as write_items:
                    exit_code = main(["enrich", "--limit", "1", "--dry-run"])

        self.assertEqual(exit_code, 0)
        write_items.assert_not_called()

    def test_enrich_apply_writes_csv(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02", tags="")
        llm_content = (
            '{"summary": "增强摘要", "signal": "增强信号", '
            '"tags": "AI;Agent", "importance": 4}'
        )

        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.call_deepseek_chat", return_value=llm_content):
                with patch("industry_radar.cli.write_items") as write_items:
                    exit_code = main(["enrich", "--limit", "1", "--apply"])

        self.assertEqual(exit_code, 0)
        write_items.assert_called_once()
        written_items = write_items.call_args.args[0]
        self.assertEqual(written_items[0].tags, "AI;Agent")

    def test_enrich_dry_run_takes_precedence_over_apply(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02", tags="")
        llm_content = (
            '{"summary": "增强摘要", "signal": "增强信号", '
            '"tags": "AI;Agent", "importance": 4}'
        )

        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.call_deepseek_chat", return_value=llm_content):
                with patch("industry_radar.cli.write_items") as write_items:
                    exit_code = main(
                        ["enrich", "--limit", "1", "--dry-run", "--apply"]
                    )

        self.assertEqual(exit_code, 0)
        write_items.assert_not_called()

    def test_dedupe_dry_run_does_not_write_csv(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", source_url="https://x.com/a"),
            make_item(item_id="2", item_date="2026-06-02", source_url="https://x.com/a"),
        ]

        with patch("industry_radar.cli.read_items", return_value=items):
            with patch("industry_radar.cli.write_items") as write_items:
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main(["dedupe", "--dry-run"])

        self.assertEqual(exit_code, 0)
        write_items.assert_not_called()

    def test_dedupe_apply_writes_csv(self) -> None:
        items = [
            make_item(item_id="1", item_date="2026-06-02", source_url="https://x.com/a"),
            make_item(item_id="2", item_date="2026-06-02", source_url="https://x.com/a"),
        ]

        with patch("industry_radar.cli.read_items", return_value=items):
            with patch("industry_radar.cli.write_items") as write_items:
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main(["dedupe", "--apply"])

        self.assertEqual(exit_code, 0)
        write_items.assert_called_once()
        self.assertEqual(len(write_items.call_args.args[0]), 1)

    def test_pipeline_save_run_log_passes_argument(self) -> None:
        with patch("industry_radar.cli.run_pipeline") as run:
            run.return_value.mode = "dry-run"
            run.return_value.fetch_result = None
            run.return_value.dedupe_result = None
            run.return_value.enrich_result = None
            run.return_value.report_path = Path("outputs/pipeline_report.md")
            run.return_value.report_written = False
            run.return_value.run_log_path = "runs/example.json"
            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = main(["pipeline", "--save-run-log", "--runs-dir", "runs"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(run.call_args.kwargs["save_run_log"])
        self.assertEqual(run.call_args.kwargs["runs_dir"], "runs")
        self.assertIn("Run log saved: runs/example.json", output.getvalue())

    def test_runs_command_lists_run_logs(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            run_log = finalize_run_log(create_run_log("pipeline", "dry-run", {}))
            write_run_log(run_log, runs_dir=tmp_dir)

            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = main(["runs", "--runs-dir", tmp_dir])

        self.assertEqual(exit_code, 0)
        self.assertIn("Recent runs:", output.getvalue())
        self.assertIn(run_log["run_id"], output.getvalue())

    def test_run_show_command_displays_details(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            run_log = create_run_log("pipeline", "dry-run", {})
            run_log["run_id"] = "test-run"
            run_log = finalize_run_log(run_log)
            write_run_log(run_log, runs_dir=tmp_dir)

            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = main(["run-show", "test-run", "--runs-dir", tmp_dir])

        self.assertEqual(exit_code, 0)
        self.assertIn("run_id: test-run", output.getvalue())
        self.assertIn("summary status: success", output.getvalue())

    def test_source_health_command_reads_temp_runs_dir(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            run_log = create_run_log("pipeline", "dry-run", {})
            add_step(
                run_log,
                "fetch",
                "partial_success",
                errors=["Source JPL News: XML parse error: broken"],
            )
            write_run_log(finalize_run_log(run_log), runs_dir=tmp_dir)

            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = main(["source-health", "--runs-dir", tmp_dir])

        self.assertEqual(exit_code, 0)
        self.assertIn("JPL News", output.getvalue())
        self.assertIn("failure_rate: 100.0%", output.getvalue())

    def test_source_health_command_sources_shows_config_source(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            sources_path.write_text('[{"name": "arXiv cs.AI"}]', encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = main(
                    [
                        "source-health",
                        "--runs-dir",
                        tmp_dir,
                        "--sources",
                        str(sources_path),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("arXiv cs.AI", output.getvalue())


if __name__ == "__main__":
    unittest.main()
