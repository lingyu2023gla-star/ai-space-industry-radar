import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.run_logger import add_step, create_run_log, finalize_run_log, write_run_log
from industry_radar.source_health import (
    add_config_sources_to_health,
    build_source_health_report,
    collect_source_health,
    load_run_logs_for_health,
    load_source_names_from_config,
)


def make_run_log(errors: list | None = None) -> dict:
    run_log = create_run_log("pipeline", "dry-run", {})
    add_step(
        run_log,
        "fetch",
        "partial_success" if errors else "success",
        metrics={"fetched": 1, "failed": len(errors or [])},
        errors=errors or [],
    )
    return finalize_run_log(run_log)


class SourceHealthTest(unittest.TestCase):
    def test_collect_source_health_counts_source_errors(self) -> None:
        health = collect_source_health(
            [make_run_log(["Source JPL News: XML parse error: broken"])]
        )

        self.assertEqual(health["JPL News"]["failures"], 1)

    def test_collect_source_health_calculates_failure_rate(self) -> None:
        health = collect_source_health(
            [
                make_run_log(["Source JPL News: XML parse error: broken"]),
                make_run_log(["Source JPL News: HTTP Error 403"]),
            ]
        )

        self.assertEqual(health["JPL News"]["failure_rate"], 1.0)

    def test_collect_source_health_records_last_error(self) -> None:
        health = collect_source_health(
            [make_run_log(["Source JPL News: XML parse error: broken"])]
        )

        self.assertEqual(health["JPL News"]["last_error"], "XML parse error: broken")

    def test_collect_source_health_no_errors_returns_empty(self) -> None:
        self.assertEqual(collect_source_health([make_run_log()]), {})

    def test_load_source_names_from_config_reads_sources_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sources.json"
            path.write_text(
                json.dumps([{"name": "arXiv cs.AI"}, {"name": "JPL News"}]),
                encoding="utf-8",
            )

            names = load_source_names_from_config(str(path))

        self.assertEqual(names, ["arXiv cs.AI", "JPL News"])

    def test_load_source_names_from_config_missing_file_returns_empty(self) -> None:
        self.assertEqual(load_source_names_from_config("missing.json"), [])

    def test_build_source_health_report_contains_source_name(self) -> None:
        health = collect_source_health(
            [make_run_log(["Source JPL News: XML parse error: broken"])]
        )

        report = build_source_health_report(health)

        self.assertIn("JPL News", report)

    def test_build_source_health_report_sorts_by_failure_rate_desc(self) -> None:
        health = {
            "Healthy": {
                "source": "Healthy",
                "runs_seen": 5,
                "failures": 0,
                "successes": 5,
                "failure_rate": 0.0,
                "last_error": "",
                "last_status": "success",
            },
            "Broken": {
                "source": "Broken",
                "runs_seen": 5,
                "failures": 5,
                "successes": 0,
                "failure_rate": 1.0,
                "last_error": "failed",
                "last_status": "failed",
            },
        }

        report = build_source_health_report(health)

        self.assertLess(report.index("Broken"), report.index("Healthy"))

    def test_add_config_sources_to_health_adds_success_sources(self) -> None:
        health = add_config_sources_to_health({}, ["arXiv cs.AI"], runs_seen=3)

        self.assertEqual(health["arXiv cs.AI"]["successes"], 3)
        self.assertEqual(health["arXiv cs.AI"]["last_status"], "success")

    def test_load_run_logs_for_health_skips_broken_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            write_run_log(make_run_log(), runs_dir=tmp_dir)
            (Path(tmp_dir) / "broken.json").write_text("{broken", encoding="utf-8")

            run_logs = load_run_logs_for_health(tmp_dir, limit=10)

        self.assertEqual(len(run_logs), 1)


if __name__ == "__main__":
    unittest.main()
