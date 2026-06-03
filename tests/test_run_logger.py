import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.run_logger import (
    add_step,
    create_run_log,
    finalize_run_log,
    generate_run_id,
    list_run_logs,
    read_run_log,
    write_run_log,
)


class RunLoggerTest(unittest.TestCase):
    def test_generate_run_id_contains_command(self) -> None:
        run_id = generate_run_id("pipeline test")

        self.assertRegex(run_id, r"\d{8}-\d{6}-pipeline-test")

    def test_create_run_log_contains_base_fields(self) -> None:
        run_log = create_run_log("pipeline", "dry-run", {"limit": 5})

        self.assertIn("run_id", run_log)
        self.assertEqual(run_log["command"], "pipeline")
        self.assertEqual(run_log["mode"], "dry-run")
        self.assertEqual(run_log["config"], {"limit": 5})
        self.assertEqual(run_log["steps"], [])

    def test_add_step_appends_step(self) -> None:
        run_log = create_run_log("pipeline", "dry-run", {})

        add_step(run_log, "fetch", "success", metrics={"fetched": 1})

        self.assertEqual(run_log["steps"][0]["name"], "fetch")
        self.assertEqual(run_log["steps"][0]["metrics"]["fetched"], 1)

    def test_add_step_rejects_invalid_status(self) -> None:
        run_log = create_run_log("pipeline", "dry-run", {})

        with self.assertRaises(ValueError):
            add_step(run_log, "fetch", "done")

    def test_finalize_run_log_success_without_errors(self) -> None:
        run_log = create_run_log("pipeline", "dry-run", {})
        add_step(run_log, "fetch", "success")

        finalized = finalize_run_log(run_log)

        self.assertEqual(finalized["summary"]["status"], "success")
        self.assertEqual(finalized["summary"]["total_errors"], 0)

    def test_finalize_run_log_partial_success(self) -> None:
        run_log = create_run_log("pipeline", "dry-run", {})
        add_step(run_log, "fetch", "partial_success", errors=["one failed"])

        finalized = finalize_run_log(run_log)

        self.assertEqual(finalized["summary"]["status"], "partial_success")
        self.assertEqual(finalized["summary"]["total_errors"], 1)

    def test_finalize_run_log_failed_step(self) -> None:
        run_log = create_run_log("pipeline", "dry-run", {})
        add_step(run_log, "fetch", "failed", errors=["failed"])

        finalized = finalize_run_log(run_log)

        self.assertEqual(finalized["summary"]["status"], "failed")

    def test_write_run_log_writes_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            run_log = finalize_run_log(create_run_log("pipeline", "dry-run", {}))

            path = write_run_log(run_log, runs_dir=tmp_dir)

            self.assertTrue(Path(path).exists())
            self.assertEqual(json.loads(Path(path).read_text())["run_id"], run_log["run_id"])

    def test_list_run_logs_returns_most_recent_first(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            old_log = finalize_run_log(create_run_log("pipeline", "dry-run", {}))
            old_path = Path(write_run_log(old_log, runs_dir=tmp_dir))
            time.sleep(0.01)
            new_log = finalize_run_log(create_run_log("pipeline", "apply", {}))
            new_path = Path(write_run_log(new_log, runs_dir=tmp_dir))
            old_path.touch()
            new_path.touch()

            logs = list_run_logs(tmp_dir, limit=2)

            self.assertEqual(logs[0]["run_id"], new_log["run_id"])

    def test_read_run_log_by_run_id(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            run_log = finalize_run_log(create_run_log("pipeline", "dry-run", {}))
            write_run_log(run_log, runs_dir=tmp_dir)

            loaded = read_run_log(run_log["run_id"], runs_dir=tmp_dir)

            self.assertEqual(loaded["run_id"], run_log["run_id"])

    def test_read_run_log_missing_raises_file_not_found(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            with self.assertRaises(FileNotFoundError):
                read_run_log("missing", runs_dir=tmp_dir)

    def test_gitignore_excludes_run_json_but_keeps_gitkeep(self) -> None:
        gitignore = Path(".gitignore").read_text(encoding="utf-8")

        self.assertIn("runs/*.json", gitignore)
        self.assertIn("!runs/.gitkeep", gitignore)


if __name__ == "__main__":
    unittest.main()
