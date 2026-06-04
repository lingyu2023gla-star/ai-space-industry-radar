import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.research_collection import create_research_metadata, write_research_session
from industry_radar.research_index import (
    build_research_collection_stats,
    build_research_documents,
    build_research_search_report,
    render_research_stats,
    score_research_document,
    search_research_documents,
)


class ResearchIndexTest(unittest.TestCase):
    def test_build_research_documents_reads_metadata_and_markdown(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_research_metadata("session-1", "AI Agent", "", "keyword", 5, {}, 2, False)
            write_research_session("# Research Session: AI Agent\n\nAgent workflow", metadata, research_dir=tmp_dir)

            documents = build_research_documents(tmp_dir)

            self.assertEqual(len(documents), 1)
            self.assertEqual(documents[0]["research_id"], "session-1")
            self.assertIn("Agent workflow", documents[0]["markdown"])
            self.assertIn("AI Agent", documents[0]["text"])

    def test_build_research_documents_handles_missing_markdown(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            metadata = create_research_metadata("session-1", "AI Agent", "", "keyword", 5, {}, 2, False)
            Path(tmp_dir, "session-1.json").write_text(json.dumps(metadata), encoding="utf-8")

            documents = build_research_documents(tmp_dir)

            self.assertEqual(len(documents), 1)
            self.assertEqual(documents[0]["markdown"], "")

    def test_build_research_documents_skips_corrupt_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, "bad.json").write_text("{bad", encoding="utf-8")

            documents = build_research_documents(tmp_dir)

            self.assertEqual(documents, [])

    def test_score_research_document_matches_query(self) -> None:
        doc = document(query="AI Agent trend", markdown="# Research Session: AI Agent")

        score = score_research_document("AI Agent", doc)

        self.assertGreater(score, 0)

    def test_score_research_document_without_match_returns_zero(self) -> None:
        doc = document(query="Satellite service", markdown="# Research Session: Space")

        score = score_research_document("Agent", doc)

        self.assertEqual(score, 0)

    def test_search_research_documents_returns_top_k(self) -> None:
        docs = [
            document(research_id="1", query="AI Agent", created_at="2026-06-01T10:00:00"),
            document(research_id="2", query="AI Agent workflow", created_at="2026-06-02T10:00:00"),
        ]

        results = search_research_documents("AI Agent", docs, top_k=1)

        self.assertEqual(len(results), 1)

    def test_search_research_documents_filters_by_retriever(self) -> None:
        docs = [
            document(research_id="1", query="AI Agent", retriever="keyword"),
            document(research_id="2", query="AI Agent", retriever="fts"),
        ]

        results = search_research_documents("Agent", docs, retriever="fts")

        self.assertEqual([result["research_id"] for result in results], ["2"])

    def test_search_research_documents_filters_ingested_true(self) -> None:
        docs = [
            document(research_id="1", query="AI Agent", ingested=True),
            document(research_id="2", query="AI Agent", ingested=False),
        ]

        results = search_research_documents("Agent", docs, ingested=True)

        self.assertEqual([result["research_id"] for result in results], ["1"])

    def test_search_research_documents_filters_ingested_false(self) -> None:
        docs = [
            document(research_id="1", query="AI Agent", ingested=True),
            document(research_id="2", query="AI Agent", ingested=False),
        ]

        results = search_research_documents("Agent", docs, ingested=False)

        self.assertEqual([result["research_id"] for result in results], ["2"])

    def test_search_research_documents_filters_since_until(self) -> None:
        docs = [
            document(research_id="old", query="AI Agent", created_at="2026-05-31T10:00:00"),
            document(research_id="new", query="AI Agent", created_at="2026-06-02T10:00:00"),
        ]

        results = search_research_documents("Agent", docs, since="2026-06-01", until="2026-06-03")

        self.assertEqual([result["research_id"] for result in results], ["new"])

    def test_search_research_documents_empty_query_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            search_research_documents("", [], top_k=10)

    def test_build_research_search_report_without_results(self) -> None:
        report = build_research_search_report([], "Agent")

        self.assertIn("No matching research sessions found.", report)

    def test_build_research_search_report_with_results_contains_research_id(self) -> None:
        report = build_research_search_report([document(research_id="session-1", query="Agent", score=3.2)], "Agent")

        self.assertIn("Research Search Results for: Agent", report)
        self.assertIn("session-1", report)

    def test_build_research_collection_stats_counts_total_sessions(self) -> None:
        stats = build_research_collection_stats([document(), document(research_id="2")])

        self.assertEqual(stats["total_sessions"], 2)

    def test_build_research_collection_stats_counts_ingested(self) -> None:
        stats = build_research_collection_stats([document(ingested=True), document(research_id="2", ingested=False)])

        self.assertEqual(stats["ingested_count"], 1)
        self.assertEqual(stats["not_ingested_count"], 1)

    def test_build_research_collection_stats_counts_retriever_distribution(self) -> None:
        stats = build_research_collection_stats([document(retriever="keyword"), document(research_id="2", retriever="fts")])

        self.assertEqual(stats["retriever_distribution"], {"keyword": 1, "fts": 1})

    def test_render_research_stats_contains_total_sessions(self) -> None:
        text = render_research_stats(build_research_collection_stats([document()]))

        self.assertIn("Total sessions", text)
        self.assertIn("Retriever distribution", text)


def document(**overrides) -> dict:
    data = {
        "research_id": "session-1",
        "query": "AI Agent trend",
        "created_at": "2026-06-02T10:00:00",
        "updated_at": "2026-06-02T10:00:00",
        "retriever": "keyword",
        "top_k": 5,
        "filters": {"industry": "AI"},
        "evidence_count": 3,
        "llm_enabled": False,
        "ingested": False,
        "output_path": "research/session-1.md",
        "markdown": "# Research Session: AI Agent\n\nAgent commercialization workflow",
        "text": "AI Agent trend Agent commercialization workflow",
    }
    data.update(overrides)
    return data


if __name__ == "__main__":
    unittest.main()
