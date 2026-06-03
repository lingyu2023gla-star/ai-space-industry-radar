import unittest
import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from industry_radar.cli import main
from industry_radar.retrievers import is_fts5_supported
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

    def test_pipeline_source_policy_cli_arguments_pass_through(self) -> None:
        with patch("industry_radar.cli.run_pipeline") as run:
            run.return_value.mode = "dry-run"
            run.return_value.fetch_result = None
            run.return_value.dedupe_result = None
            run.return_value.enrich_result = None
            run.return_value.report_path = Path("outputs/pipeline_report.md")
            run.return_value.report_written = False
            run.return_value.run_log_path = None
            run.return_value.skipped_sources = []
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "pipeline",
                        "--skip-unhealthy-sources",
                        "--failure-rate-threshold",
                        "0.5",
                        "--min-source-runs",
                        "2",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertTrue(run.call_args.kwargs["skip_unhealthy_sources"])
        self.assertEqual(run.call_args.kwargs["failure_rate_threshold"], 0.5)
        self.assertEqual(run.call_args.kwargs["min_source_runs"], 2)

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

    def test_dashboard_command_generates_html_to_temp_path(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02", title="Dashboard Item")
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dashboard.html"
            with patch("industry_radar.cli.read_items", return_value=[item]):
                with patch("industry_radar.cli.list_run_logs", return_value=[]):
                    with patch("industry_radar.cli.load_run_logs_for_health", return_value=[]):
                        with contextlib.redirect_stdout(io.StringIO()) as output:
                            exit_code = main(
                                [
                                    "dashboard",
                                    "--output",
                                    str(output_path),
                                    "--top",
                                    "5",
                                ]
                            )

            html = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("Dashboard generated:", output.getvalue())
        self.assertIn("Dashboard Item", html)

    def test_ask_command_default_does_not_call_llm(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            title="OpenAI 推进 Agent 产品化",
            summary="Agent enterprise workflow",
            signal="Agent 商业化加速",
            tags="AI;Agent",
        )
        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.call_deepseek_chat") as llm:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    exit_code = main(["ask", "Agent 趋势"])

        self.assertEqual(exit_code, 0)
        llm.assert_not_called()
        self.assertIn("OpenAI 推进 Agent 产品化", output.getvalue())
        self.assertIn("[1]", output.getvalue())
        self.assertIn("相关证据", output.getvalue())

    def test_ask_command_embedding_retriever_runs_without_llm(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            title="OpenAI 推进 Agent 产品化",
            summary="Agent enterprise workflow",
            signal="Agent 商业化加速",
            tags="AI;Agent",
        )
        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.call_deepseek_chat") as llm:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    exit_code = main(["ask", "Agent 趋势", "--retriever", "embedding"])

        self.assertEqual(exit_code, 0)
        llm.assert_not_called()
        self.assertIn("OpenAI 推进 Agent 产品化", output.getvalue())

    def test_ask_command_no_citations_runs(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            title="OpenAI 推进 Agent 产品化",
            summary="Agent enterprise workflow",
            signal="Agent 商业化加速",
            tags="AI;Agent",
        )
        with patch("industry_radar.cli.read_items", return_value=[item]):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = main(["ask", "Agent 趋势", "--no-citations"])

        self.assertEqual(exit_code, 0)
        self.assertNotIn("[1]", output.getvalue())
        self.assertIn("1. OpenAI 推进 Agent 产品化", output.getvalue())

    @unittest.skipUnless(is_fts5_supported(), "SQLite FTS5 is not available")
    def test_ask_command_fts_retriever_runs_without_llm(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            title="OpenAI Agent productization",
            summary="Agent enterprise workflow",
            signal="Agent commercialization",
            tags="AI;Agent",
        )
        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.call_deepseek_chat") as llm:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    exit_code = main(["ask", "Agent workflow", "--retriever", "fts"])

        self.assertEqual(exit_code, 0)
        llm.assert_not_called()
        self.assertIn("OpenAI Agent productization", output.getvalue())

    def test_ask_command_fts_retriever_reports_unsupported_fts5(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            title="OpenAI Agent productization",
            summary="Agent enterprise workflow",
            tags="AI;Agent",
        )
        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.retrievers.is_fts5_supported", return_value=False):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    exit_code = main(["ask", "Agent", "--retriever", "fts"])

        self.assertEqual(exit_code, 1)
        self.assertIn("SQLite FTS5 is not supported", output.getvalue())

    def test_ask_command_llm_uses_mocked_llm(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            title="OpenAI 推进 Agent 产品化",
            summary="Agent enterprise workflow",
            signal="Agent 商业化加速",
            tags="AI;Agent",
        )
        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.call_deepseek_chat", return_value="LLM answer") as llm:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    exit_code = main(["ask", "Agent 趋势", "--llm"])

        self.assertEqual(exit_code, 0)
        llm.assert_called_once()
        self.assertIn("LLM answer", output.getvalue())
        self.assertIn("证据列表", output.getvalue())

    def test_ask_command_llm_receives_numbered_evidence(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            title="OpenAI 推进 Agent 产品化",
            summary="Agent enterprise workflow",
            signal="Agent 商业化加速",
            tags="AI;Agent",
        )
        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.call_deepseek_chat", return_value="LLM answer") as llm:
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main(["ask", "Agent 趋势", "--llm", "--citations"])

        self.assertEqual(exit_code, 0)
        messages = llm.call_args.args[0]
        self.assertIn("[1]", messages[1]["content"])
        self.assertIn("标题：OpenAI 推进 Agent 产品化", messages[1]["content"])

    def test_ask_command_without_results_does_not_call_llm(self) -> None:
        with patch("industry_radar.cli.read_items", return_value=[]):
            with patch("industry_radar.cli.call_deepseek_chat") as llm:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    exit_code = main(["ask", "missing", "--llm"])

        self.assertEqual(exit_code, 0)
        llm.assert_not_called()
        self.assertIn("没有在本地知识库", output.getvalue())

    def test_ask_command_does_not_write_csv(self) -> None:
        item = make_item(
            item_id="1",
            item_date="2026-06-02",
            title="OpenAI 推进 Agent 产品化",
            summary="Agent enterprise workflow",
            signal="Agent 商业化加速",
            tags="AI;Agent",
        )
        with patch("industry_radar.cli.read_items", return_value=[item]):
            with patch("industry_radar.cli.write_items") as write_items:
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main(["ask", "Agent 趋势"])

        self.assertEqual(exit_code, 0)
        write_items.assert_not_called()


if __name__ == "__main__":
    unittest.main()
