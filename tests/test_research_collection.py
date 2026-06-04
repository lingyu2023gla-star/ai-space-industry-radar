import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.research_collection import (
    build_research_paths,
    create_research_metadata,
    delete_research_session,
    generate_research_id,
    list_research_sessions,
    mark_research_ingested,
    read_research_markdown,
    read_research_metadata,
    write_research_session,
)


class ResearchCollectionTest(unittest.TestCase):
    def test_generate_research_id_contains_timestamp_and_slug(self) -> None:
        research_id = generate_research_id("AI Agent Commercialization")

        self.assertRegex(research_id, r"^\d{8}-\d{6}-ai-agent-commercialization$")

    def test_generate_research_id_uses_fallback_slug(self) -> None:
        research_id = generate_research_id("商业化趋势")

        self.assertRegex(research_id, r"^\d{8}-\d{6}-research-session$")

    def test_build_research_paths_returns_markdown_and_json_paths(self) -> None:
        paths = build_research_paths("session-1", "research_tmp")

        self.assertEqual(paths["markdown"], "research_tmp/session-1.md")
        self.assertEqual(paths["metadata"], "research_tmp/session-1.json")

    def test_create_research_metadata_contains_required_fields(self) -> None:
        metadata = create_research_metadata(
            "session-1",
            "Agent trend",
            "research/session-1.md",
            "keyword",
            5,
            {"industry": "AI"},
            2,
            False,
        )

        self.assertEqual(metadata["research_id"], "session-1")
        self.assertEqual(metadata["query"], "Agent trend")
        self.assertEqual(metadata["retriever"], "keyword")
        self.assertEqual(metadata["top_k"], 5)
        self.assertEqual(metadata["filters"], {"industry": "AI"})
        self.assertEqual(metadata["evidence_count"], 2)
        self.assertFalse(metadata["llm_enabled"])
        self.assertFalse(metadata["ingested"])
        self.assertIsNone(metadata["ingested_at"])
        self.assertIn("created_at", metadata)
        self.assertIn("updated_at", metadata)

    def test_write_research_session_writes_markdown_and_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_research_metadata("session-1", "Agent", "", "keyword", 5, {}, 1, False)

            paths = write_research_session("# Research", metadata, research_dir=tmp_dir)

            self.assertTrue(Path(paths["markdown"]).exists())
            self.assertTrue(Path(paths["metadata"]).exists())
            self.assertEqual(Path(paths["markdown"]).read_text(encoding="utf-8"), "# Research")
            self.assertEqual(json.loads(Path(paths["metadata"]).read_text(encoding="utf-8"))["research_id"], "session-1")

    def test_list_research_sessions_sorts_by_created_at_desc(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            old_metadata = create_research_metadata("old", "old query", "", "keyword", 5, {}, 1, False)
            new_metadata = create_research_metadata("new", "new query", "", "fts", 8, {}, 2, False)
            old_metadata["created_at"] = "2026-06-01T10:00:00"
            new_metadata["created_at"] = "2026-06-02T10:00:00"
            write_research_session("# Old", old_metadata, research_dir=tmp_dir)
            write_research_session("# New", new_metadata, research_dir=tmp_dir)

            sessions = list_research_sessions(tmp_dir, limit=10)

            self.assertEqual([session["research_id"] for session in sessions], ["new", "old"])

    def test_list_research_sessions_skips_corrupt_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_research_metadata("good", "query", "", "keyword", 5, {}, 1, False)
            write_research_session("# Good", metadata, research_dir=tmp_dir)
            Path(tmp_dir, "bad.json").write_text("{bad json", encoding="utf-8")

            sessions = list_research_sessions(tmp_dir, limit=10)

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["research_id"], "good")

    def test_read_research_metadata_by_id(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_research_metadata("session-1", "Agent", "", "keyword", 5, {}, 1, False)
            write_research_session("# Research", metadata, research_dir=tmp_dir)

            loaded = read_research_metadata("session-1", research_dir=tmp_dir)

            self.assertEqual(loaded["research_id"], "session-1")

    def test_read_research_markdown_by_id(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_research_metadata("session-1", "Agent", "", "keyword", 5, {}, 1, False)
            write_research_session("# Research", metadata, research_dir=tmp_dir)

            markdown = read_research_markdown("session-1", research_dir=tmp_dir)

            self.assertEqual(markdown, "# Research")

    def test_mark_research_ingested_updates_metadata(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_research_metadata("session-1", "Agent", "", "keyword", 5, {}, 1, False)
            write_research_session("# Research", metadata, research_dir=tmp_dir)

            updated = mark_research_ingested("session-1", research_dir=tmp_dir)

            self.assertTrue(updated["ingested"])
            self.assertIsNotNone(updated["ingested_at"])
            self.assertTrue(read_research_metadata("session-1", research_dir=tmp_dir)["ingested"])

    def test_delete_research_session_deletes_markdown_and_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_research_metadata("session-1", "Agent", "", "keyword", 5, {}, 1, False)
            paths = write_research_session("# Research", metadata, research_dir=tmp_dir)

            result = delete_research_session("session-1", research_dir=tmp_dir)

            self.assertTrue(result["deleted_markdown"])
            self.assertTrue(result["deleted_metadata"])
            self.assertFalse(Path(paths["markdown"]).exists())
            self.assertFalse(Path(paths["metadata"]).exists())


if __name__ == "__main__":
    unittest.main()
