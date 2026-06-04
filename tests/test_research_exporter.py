import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.research_collection import create_research_metadata, write_research_session
from industry_radar.research_exporter import (
    build_export_manifest,
    export_research_pack,
    render_export_readme,
    select_research_sessions,
    summarize_export_result,
)
from industry_radar.research_index import build_research_documents


class ResearchExporterTest(unittest.TestCase):
    def test_select_research_sessions_by_query(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            create_session(tmp_dir, "session-1", "AI Agent trend")
            create_session(tmp_dir, "session-2", "Satellite data")

            sessions = select_research_sessions(tmp_dir, query="AI Agent")

            self.assertEqual([session["research_id"] for session in sessions], ["session-1"])

    def test_select_research_sessions_by_research_ids(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            create_session(tmp_dir, "session-1", "AI Agent trend")
            create_session(tmp_dir, "session-2", "Satellite data")

            sessions = select_research_sessions(tmp_dir, research_ids=["session-2"])

            self.assertEqual([session["research_id"] for session in sessions], ["session-2"])

    def test_select_research_sessions_filters_retriever(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            create_session(tmp_dir, "session-1", "AI Agent", retriever="keyword")
            create_session(tmp_dir, "session-2", "AI Agent", retriever="fts")

            sessions = select_research_sessions(tmp_dir, retriever="fts")

            self.assertEqual([session["research_id"] for session in sessions], ["session-2"])

    def test_select_research_sessions_filters_ingested_true(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            create_session(tmp_dir, "session-1", "AI Agent", ingested=True)
            create_session(tmp_dir, "session-2", "AI Agent", ingested=False)

            sessions = select_research_sessions(tmp_dir, ingested=True)

            self.assertEqual([session["research_id"] for session in sessions], ["session-1"])

    def test_select_research_sessions_filters_ingested_false(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            create_session(tmp_dir, "session-1", "AI Agent", ingested=True)
            create_session(tmp_dir, "session-2", "AI Agent", ingested=False)

            sessions = select_research_sessions(tmp_dir, ingested=False)

            self.assertEqual([session["research_id"] for session in sessions], ["session-2"])

    def test_select_research_sessions_filters_since_until(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            create_session(tmp_dir, "old", "AI Agent", created_at="2026-05-31T10:00:00")
            create_session(tmp_dir, "new", "AI Agent", created_at="2026-06-02T10:00:00")

            sessions = select_research_sessions(tmp_dir, since="2026-06-01", until="2026-06-03")

            self.assertEqual([session["research_id"] for session in sessions], ["new"])

    def test_select_research_sessions_top_k(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            create_session(tmp_dir, "session-1", "AI Agent", created_at="2026-06-01T10:00:00")
            create_session(tmp_dir, "session-2", "AI Agent", created_at="2026-06-02T10:00:00")

            sessions = select_research_sessions(tmp_dir, top_k=1)

            self.assertEqual(len(sessions), 1)

    def test_build_export_manifest_contains_session_count(self) -> None:
        manifest = build_export_manifest([session_doc()], "pack")

        self.assertEqual(manifest["session_count"], 1)

    def test_build_export_manifest_contains_sessions(self) -> None:
        manifest = build_export_manifest([session_doc(research_id="session-1")], "pack")

        self.assertEqual(manifest["sessions"][0]["research_id"], "session-1")

    def test_render_export_readme_contains_research_pack(self) -> None:
        readme = render_export_readme(build_export_manifest([session_doc()], "pack"))

        self.assertIn("Research Pack", readme)
        self.assertIn("How to use", readme)

    def test_export_research_pack_generates_zip(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "pack.zip"

            written = export_research_pack([session_doc()], str(output))

            self.assertEqual(written, str(output))
            self.assertTrue(output.exists())

    def test_export_zip_contains_manifest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "pack.zip"
            export_research_pack([session_doc()], str(output))

            with zipfile.ZipFile(output) as archive:
                self.assertIn("manifest.json", archive.namelist())

    def test_export_zip_contains_readme(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "pack.zip"
            export_research_pack([session_doc()], str(output))

            with zipfile.ZipFile(output) as archive:
                self.assertIn("README.md", archive.namelist())

    def test_export_zip_contains_research_markdown_and_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "pack.zip"
            export_research_pack([session_doc(research_id="session-1")], str(output))

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

            self.assertIn("research/session-1.md", names)
            self.assertIn("research/session-1.json", names)

    def test_export_markdown_missing_writes_warning(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_session(tmp_dir, "session-1", "AI Agent")
            Path(tmp_dir, "session-1.md").unlink()
            output = Path(tmp_dir) / "pack.zip"

            export_research_pack(build_research_documents(tmp_dir), str(output))

            with zipfile.ZipFile(output) as archive:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                names = archive.namelist()

            self.assertIn("Markdown missing for research session: session-1", manifest["warnings"])
            self.assertNotIn("research/session-1.md", names)
            self.assertIn("research/session-1.json", names)
            self.assertEqual(metadata["research_id"], "session-1")

    def test_summarize_export_result_contains_output_path(self) -> None:
        summary = summarize_export_result("exports/pack.zip", build_export_manifest([session_doc()], "pack"))

        self.assertIn("exports/pack.zip", summary)
        self.assertIn("Sessions: 1", summary)


def create_session(
    research_dir: str,
    research_id: str,
    query: str,
    retriever: str = "keyword",
    ingested: bool = False,
    created_at: str = "2026-06-02T10:00:00",
) -> dict:
    metadata = create_research_metadata(research_id, query, "", retriever, 5, {}, 1, False, ingested=ingested)
    metadata["created_at"] = created_at
    metadata["updated_at"] = created_at
    write_research_session(f"# Research Session: {query}\n\n{query} notes", metadata, research_dir=research_dir)
    return metadata


def session_doc(**overrides) -> dict:
    data = {
        "research_id": "session-1",
        "query": "AI Agent trend",
        "created_at": "2026-06-02T10:00:00",
        "updated_at": "2026-06-02T10:00:00",
        "output_path": "research/session-1.md",
        "retriever": "keyword",
        "top_k": 5,
        "filters": {},
        "evidence_count": 1,
        "llm_enabled": False,
        "ingested": False,
        "ingested_at": None,
        "markdown": "# Research Session: AI Agent",
        "markdown_missing": False,
        "metadata_path": "research/session-1.json",
    }
    data.update(overrides)
    return data


if __name__ == "__main__":
    unittest.main()
