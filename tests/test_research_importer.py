import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.research_importer import (
    build_import_plan,
    import_research_pack,
    inspect_research_pack,
    render_import_plan,
    summarize_import_result,
    validate_research_pack_manifest,
)


class ResearchImporterTest(unittest.TestCase):
    def test_inspect_research_pack_reads_valid_zip(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = create_pack(tmp_dir)

            info = inspect_research_pack(str(zip_path))

            self.assertEqual(info["manifest"]["session_count"], 1)
            self.assertIn("research/session-1.md", info["research_markdown_files"])
            self.assertIn("research/session-1.json", info["research_metadata_files"])

    def test_inspect_research_pack_missing_file_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            inspect_research_pack("missing.zip")

    def test_inspect_research_pack_non_zip_raises_value_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "bad.zip"
            path.write_text("not zip", encoding="utf-8")

            with self.assertRaises(ValueError):
                inspect_research_pack(str(path))

    def test_inspect_research_pack_missing_manifest_raises_value_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("README.md", "readme")

            with self.assertRaises(ValueError):
                inspect_research_pack(str(path))

    def test_validate_research_pack_manifest_accepts_valid_manifest(self) -> None:
        manifest = valid_manifest()

        self.assertEqual(validate_research_pack_manifest(manifest), manifest)

    def test_validate_research_pack_manifest_missing_sessions_raises_value_error(self) -> None:
        manifest = valid_manifest()
        manifest.pop("sessions")

        with self.assertRaises(ValueError):
            validate_research_pack_manifest(manifest)

    def test_build_import_plan_marks_new_session(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            info = inspect_research_pack(str(create_pack(tmp_dir)))

            plan = build_import_plan(info, research_dir=str(Path(tmp_dir) / "research"))

            self.assertEqual(plan["new"], 1)
            self.assertEqual(plan["sessions"][0]["status"], "new")

    def test_build_import_plan_marks_existing_session(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            info = inspect_research_pack(str(create_pack(tmp_dir)))
            research_dir = Path(tmp_dir) / "research"
            research_dir.mkdir()
            Path(research_dir, "session-1.md").write_text("existing", encoding="utf-8")
            Path(research_dir, "session-1.json").write_text("{}", encoding="utf-8")

            plan = build_import_plan(info, research_dir=str(research_dir))

            self.assertEqual(plan["exists"], 1)
            self.assertEqual(plan["sessions"][0]["status"], "exists")

    def test_build_import_plan_overwrite_marks_overwrite(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            info = inspect_research_pack(str(create_pack(tmp_dir)))
            research_dir = Path(tmp_dir) / "research"
            research_dir.mkdir()
            Path(research_dir, "session-1.md").write_text("existing", encoding="utf-8")

            plan = build_import_plan(info, research_dir=str(research_dir), overwrite=True)

            self.assertEqual(plan["overwrite"], 1)
            self.assertEqual(plan["sessions"][0]["status"], "overwrite")

    def test_build_import_plan_missing_files_marks_missing_files(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            info = inspect_research_pack(str(create_pack(tmp_dir, include_markdown=False)))

            plan = build_import_plan(info, research_dir=str(Path(tmp_dir) / "research"))

            self.assertEqual(plan["missing_files"], 1)
            self.assertEqual(plan["sessions"][0]["status"], "missing_files")

    def test_render_import_plan_contains_total_sessions(self) -> None:
        text = render_import_plan({"total": 1, "new": 1, "exists": 0, "overwrite": 0, "missing_files": 0, "sessions": []})

        self.assertIn("Total sessions", text)
        self.assertIn("No sessions found.", text)

    def test_import_research_pack_dry_run_does_not_write_files(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = create_pack(tmp_dir)
            research_dir = Path(tmp_dir) / "imported"

            result = import_research_pack(str(zip_path), research_dir=str(research_dir), apply=False)

            self.assertFalse(research_dir.exists())
            self.assertFalse(result["applied"])

    def test_import_research_pack_apply_writes_markdown_and_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = create_pack(tmp_dir)
            research_dir = Path(tmp_dir) / "imported"

            result = import_research_pack(str(zip_path), research_dir=str(research_dir), apply=True)

            self.assertEqual(result["imported"], 1)
            self.assertTrue(Path(research_dir, "session-1.md").exists())
            self.assertTrue(Path(research_dir, "session-1.json").exists())

    def test_import_research_pack_existing_without_overwrite_skips(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = create_pack(tmp_dir)
            research_dir = Path(tmp_dir) / "imported"
            research_dir.mkdir()
            Path(research_dir, "session-1.md").write_text("existing", encoding="utf-8")

            result = import_research_pack(str(zip_path), research_dir=str(research_dir), apply=True)

            self.assertEqual(result["imported"], 0)
            self.assertEqual(result["skipped_existing"], 1)
            self.assertEqual(Path(research_dir, "session-1.md").read_text(encoding="utf-8"), "existing")

    def test_import_research_pack_overwrite_replaces_existing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            zip_path = create_pack(tmp_dir)
            research_dir = Path(tmp_dir) / "imported"
            research_dir.mkdir()
            Path(research_dir, "session-1.md").write_text("existing", encoding="utf-8")

            result = import_research_pack(str(zip_path), research_dir=str(research_dir), overwrite=True, apply=True)

            self.assertEqual(result["overwritten"], 1)
            self.assertIn("Research Session", Path(research_dir, "session-1.md").read_text(encoding="utf-8"))

    def test_summarize_import_result_contains_imported(self) -> None:
        text = summarize_import_result(
            {
                "applied": True,
                "imported": 2,
                "skipped_existing": 1,
                "skipped_missing": 0,
                "overwritten": 0,
            }
        )

        self.assertIn("Imported: 2", text)


def create_pack(tmp_dir: str, include_markdown: bool = True, include_metadata: bool = True) -> Path:
    zip_path = Path(tmp_dir) / "pack.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(valid_manifest(), ensure_ascii=False))
        archive.writestr("README.md", "# Research Pack")
        if include_markdown:
            archive.writestr("research/session-1.md", "# Research Session: AI Agent")
        if include_metadata:
            archive.writestr(
                "research/session-1.json",
                json.dumps(
                    {
                        "research_id": "session-1",
                        "query": "AI Agent",
                        "created_at": "2026-06-02T10:00:00",
                        "retriever": "keyword",
                    },
                    ensure_ascii=False,
                ),
            )
    return zip_path


def valid_manifest() -> dict:
    return {
        "export_name": "pack",
        "created_at": "2026-06-02T10:00:00",
        "session_count": 1,
        "sessions": [
            {
                "research_id": "session-1",
                "query": "AI Agent",
                "metadata_path": "research/session-1.json",
                "markdown_path": "research/session-1.md",
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
