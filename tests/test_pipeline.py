import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from industry_radar.data_governance import DedupeResult
from industry_radar.fetcher import FetchResult
from industry_radar.pipeline import PipelineEnrichResult, run_pipeline
from industry_radar.cli import main
from tests.test_storage import make_item


class PipelineTest(unittest.TestCase):
    def test_pipeline_dry_run_does_not_write_csv_or_report(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        with patch("industry_radar.pipeline.read_items", return_value=[item]):
            with patch("industry_radar.pipeline.write_items") as write_items:
                with patch("industry_radar.pipeline.write_report") as write_report:
                    result = run_pipeline(
                        report_path=Path("outputs/pipeline_report.md"),
                        apply=False,
                    )

        self.assertEqual(result.mode, "dry-run")
        write_items.assert_not_called()
        write_report.assert_not_called()

    def test_pipeline_apply_calls_fetch_dedupe_and_report(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        dedupe_result = DedupeResult(
            duplicate_groups=0,
            removed_duplicates=0,
            remaining_items=1,
            items=[item],
            groups=[],
        )
        with patch("industry_radar.pipeline.fetch_and_import", return_value=FetchResult(fetched=1, imported=1)) as fetch:
            with patch("industry_radar.pipeline.read_items", return_value=[item]):
                with patch("industry_radar.pipeline.dedupe_items", return_value=dedupe_result) as dedupe:
                    with patch("industry_radar.pipeline.write_items") as write_items:
                        with patch("industry_radar.pipeline.write_report") as write_report:
                            result = run_pipeline(
                                sources_path=Path("data/sources.json"),
                                report_path=Path("outputs/weekly.md"),
                                apply=True,
                            )

        self.assertEqual(result.mode, "apply")
        fetch.assert_called_once()
        dedupe.assert_called_once()
        write_items.assert_called_once_with([item])
        write_report.assert_called_once()

    def test_pipeline_without_sources_skips_fetch(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        with patch("industry_radar.pipeline.fetch_and_import") as fetch:
            with patch("industry_radar.pipeline.read_items", return_value=[item]):
                run_pipeline(report_path=Path("outputs/pipeline_report.md"))

        fetch.assert_not_called()

    def test_pipeline_without_enrich_does_not_call_enrich_step(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        with patch("industry_radar.pipeline.read_items", return_value=[item]):
            with patch("industry_radar.pipeline.run_enrich_step") as enrich:
                run_pipeline(report_path=Path("outputs/pipeline_report.md"), enrich=False)

        enrich.assert_not_called()

    def test_pipeline_with_enrich_calls_enrich_step(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        with patch("industry_radar.pipeline.read_items", return_value=[item]):
            with patch(
                "industry_radar.pipeline.run_enrich_step",
                return_value=PipelineEnrichResult(selected=1),
            ) as enrich:
                run_pipeline(
                    report_path=Path("outputs/pipeline_report.md"),
                    enrich=True,
                )

        enrich.assert_called_once()

    def test_pipeline_dry_run_passes_apply_false_to_enrich(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        with patch("industry_radar.pipeline.read_items", return_value=[item]):
            with patch(
                "industry_radar.pipeline.run_enrich_step",
                return_value=PipelineEnrichResult(selected=1),
            ) as enrich:
                run_pipeline(
                    report_path=Path("outputs/pipeline_report.md"),
                    enrich=True,
                    apply=False,
                )

        self.assertFalse(enrich.call_args.kwargs["apply"])

    def test_pipeline_report_path_is_used(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        report_path = Path("outputs/custom.md")
        with patch("industry_radar.pipeline.read_items", return_value=[item]):
            with patch("industry_radar.pipeline.write_items"):
                with patch("industry_radar.pipeline.write_report") as write_report:
                    run_pipeline(report_path=report_path, apply=True)

        self.assertEqual(write_report.call_args.args[1], report_path)

    def test_pipeline_industry_passes_to_fetch_and_enrich(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        with patch("industry_radar.pipeline.fetch_and_import", return_value=FetchResult()) as fetch:
            with patch("industry_radar.pipeline.read_items", return_value=[item]):
                with patch(
                    "industry_radar.pipeline.run_enrich_step",
                    return_value=PipelineEnrichResult(selected=1),
                ) as enrich:
                    run_pipeline(
                        sources_path=Path("data/sources.json"),
                        report_path=Path("outputs/pipeline_report.md"),
                        industry="AI",
                        enrich=True,
                    )

        self.assertEqual(fetch.call_args.kwargs["industry"], "AI")
        self.assertEqual(enrich.call_args.kwargs["industry"], "AI")

    def test_pipeline_limit_and_top_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            run_pipeline(report_path=Path("outputs/pipeline_report.md"), limit=0)
        with self.assertRaises(ValueError):
            run_pipeline(report_path=Path("outputs/pipeline_report.md"), top=0)

    def test_pipeline_default_does_not_write_run_log(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        with patch("industry_radar.pipeline.read_items", return_value=[item]):
            with patch("industry_radar.pipeline.write_run_log") as write_run_log:
                result = run_pipeline(report_path=Path("outputs/pipeline_report.md"))

        write_run_log.assert_not_called()
        self.assertIsNone(result.run_log_path)

    def test_pipeline_save_run_log_writes_run_log(self) -> None:
        item = make_item(item_id="1", item_date="2026-06-02")
        with TemporaryDirectory() as tmp_dir:
            with patch("industry_radar.pipeline.read_items", return_value=[item]):
                result = run_pipeline(
                    report_path=Path("outputs/pipeline_report.md"),
                    save_run_log=True,
                    runs_dir=tmp_dir,
                )

            self.assertIsNotNone(result.run_log_path)
            self.assertTrue(Path(result.run_log_path).exists())

    def test_pipeline_config_executes_dry_run(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "pipeline.json"
            config_path.write_text(
                json.dumps({"limit": 3, "industry": "AI", "report": "outputs/ai.md"}),
                encoding="utf-8",
            )
            with patch("industry_radar.cli.run_pipeline") as run:
                run.return_value.mode = "dry-run"
                run.return_value.fetch_result = None
                run.return_value.dedupe_result = None
                run.return_value.enrich_result = None
                run.return_value.report_path = Path("outputs/ai.md")
                run.return_value.report_written = False
                exit_code = main(["pipeline", "--config", str(config_path)])

        self.assertEqual(exit_code, 0)
        self.assertFalse(run.call_args.kwargs["apply"])
        self.assertEqual(run.call_args.kwargs["limit"], 3)
        self.assertEqual(run.call_args.kwargs["industry"], "AI")

    def test_pipeline_cli_overrides_config(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "pipeline.json"
            config_path.write_text(
                json.dumps(
                    {
                        "limit": 3,
                        "industry": "AI",
                        "top": 5,
                        "report": "outputs/ai_weekly.md",
                    }
                ),
                encoding="utf-8",
            )
            with patch("industry_radar.cli.run_pipeline") as run:
                run.return_value.mode = "dry-run"
                run.return_value.fetch_result = None
                run.return_value.dedupe_result = None
                run.return_value.enrich_result = None
                run.return_value.report_path = Path("outputs/ai_weekly.md")
                run.return_value.report_written = False
                exit_code = main(
                    [
                        "pipeline",
                        "--config",
                        str(config_path),
                        "--limit",
                        "10",
                        "--industry",
                        "space",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(run.call_args.kwargs["limit"], 10)
        self.assertEqual(run.call_args.kwargs["industry"], "Commercial Space")
        self.assertEqual(run.call_args.kwargs["top"], 5)
        self.assertEqual(run.call_args.kwargs["report_path"], Path("outputs/ai_weekly.md"))

    def test_pipeline_config_apply_key_returns_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "pipeline.json"
            config_path.write_text(json.dumps({"apply": True}), encoding="utf-8")

            exit_code = main(["pipeline", "--config", str(config_path)])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
