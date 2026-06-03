import unittest
from copy import deepcopy
from unittest.mock import patch

from industry_radar.knowledge_base import build_documents_from_items
from industry_radar.retrievers import (
    EmbeddingRetriever,
    HashingEmbeddingProvider,
    KeywordRetriever,
    SQLiteFTSRetriever,
    build_fts_query,
    cosine_similarity,
    ensure_fts5_supported,
    is_fts5_supported,
)


def item(**overrides) -> dict:
    data = {
        "id": "1",
        "date": "2026-06-02",
        "industry": "AI",
        "category": "Agent",
        "company": "OpenAI",
        "title": "OpenAI Agent productization",
        "summary": "Agent workflow automation",
        "signal": "Agent commercialization",
        "tags": "AI;Agent;Product",
        "source": "OpenAI Blog",
        "source_url": "https://example.com",
        "importance": 5,
    }
    data.update(overrides)
    return data


class RetrieversTest(unittest.TestCase):
    def test_is_fts5_supported_returns_bool(self) -> None:
        self.assertIsInstance(is_fts5_supported(), bool)

    def test_ensure_fts5_supported_raises_when_unavailable(self) -> None:
        with patch("industry_radar.retrievers.is_fts5_supported", return_value=False):
            with self.assertRaises(RuntimeError):
                ensure_fts5_supported()

    def test_build_fts_query_handles_english_query(self) -> None:
        self.assertEqual(build_fts_query("SpaceX Starlink"), "spacex OR starlink")

    def test_build_fts_query_handles_chinese_query(self) -> None:
        query = build_fts_query("AI Agent 趋势")

        self.assertIn("ai", query)
        self.assertIn("agent", query)
        self.assertIn("趋势", query)

    def test_build_fts_query_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_fts_query("")

    def test_build_fts_query_removes_dangerous_special_characters(self) -> None:
        query = build_fts_query('title:"Agent" (AI):SpaceX')

        for char in ('"', ":", "(", ")"):
            self.assertNotIn(char, query)

    def test_hashing_embedding_provider_is_stable(self) -> None:
        provider = HashingEmbeddingProvider(dimensions=16)

        self.assertEqual(provider.embed_text("AI Agent"), provider.embed_text("AI Agent"))

    def test_hashing_embedding_provider_dimension_is_correct(self) -> None:
        self.assertEqual(len(HashingEmbeddingProvider(dimensions=32).embed_text("AI")), 32)

    def test_hashing_embedding_provider_empty_text_returns_zero_vector(self) -> None:
        self.assertEqual(HashingEmbeddingProvider(dimensions=4).embed_text(""), [0.0] * 4)

    def test_hashing_embedding_provider_invalid_dimensions_raises(self) -> None:
        with self.assertRaises(ValueError):
            HashingEmbeddingProvider(dimensions=0)

    def test_cosine_similarity_identical_vectors_is_close_to_one(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)

    def test_cosine_similarity_zero_vector_returns_zero(self) -> None:
        self.assertEqual(cosine_similarity([0.0, 0.0], [1.0, 0.0]), 0.0)

    def test_cosine_similarity_different_lengths_raises(self) -> None:
        with self.assertRaises(ValueError):
            cosine_similarity([1.0], [1.0, 0.0])

    def test_keyword_retriever_returns_keyword_results(self) -> None:
        docs = build_documents_from_items([item()])

        results = KeywordRetriever().search("agent", docs)

        self.assertEqual(results[0]["id"], "1")

    def test_embedding_retriever_returns_related_documents(self) -> None:
        docs = build_documents_from_items([item()])

        results = EmbeddingRetriever(HashingEmbeddingProvider(dimensions=32)).search("agent workflow", docs)

        self.assertEqual(results[0]["id"], "1")

    def test_embedding_retriever_respects_top_k(self) -> None:
        docs = build_documents_from_items([item(id="1"), item(id="2")])

        results = EmbeddingRetriever().search("agent", docs, top_k=1)

        self.assertEqual(len(results), 1)

    def test_embedding_retriever_supports_industry_filter(self) -> None:
        docs = build_documents_from_items(
            [item(id="ai", industry="AI"), item(id="space", industry="Commercial Space")]
        )

        results = EmbeddingRetriever().search("agent", docs, industry="AI")

        self.assertEqual([result["id"] for result in results], ["ai"])

    def test_embedding_retriever_supports_tag_filter(self) -> None:
        docs = build_documents_from_items([item(id="1", tags="AI;Agent"), item(id="2", tags="Space")])

        results = EmbeddingRetriever().search("agent", docs, tag="Agent")

        self.assertEqual([result["id"] for result in results], ["1"])

    def test_embedding_retriever_unique_alnum_query_does_not_return_hash_collisions(self) -> None:
        docs = build_documents_from_items([item()])

        results = EmbeddingRetriever().search("xyzabc123", docs)

        self.assertEqual(results, [])

    def test_embedding_retriever_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            EmbeddingRetriever().search("", [])

    def test_embedding_retriever_invalid_top_k_raises(self) -> None:
        with self.assertRaises(ValueError):
            EmbeddingRetriever().search("agent", [], top_k=0)

    def test_embedding_retriever_does_not_modify_documents(self) -> None:
        docs = build_documents_from_items([item()])
        original = deepcopy(docs)

        EmbeddingRetriever().search("agent", docs)

        self.assertEqual(docs, original)

    @unittest.skipUnless(is_fts5_supported(), "SQLite FTS5 is not available")
    def test_sqlite_fts_retriever_returns_related_documents(self) -> None:
        docs = build_documents_from_items([item()])

        results = SQLiteFTSRetriever().search("agent workflow", docs)

        self.assertEqual(results[0]["id"], "1")

    @unittest.skipUnless(is_fts5_supported(), "SQLite FTS5 is not available")
    def test_sqlite_fts_retriever_respects_top_k(self) -> None:
        docs = build_documents_from_items([item(id="1"), item(id="2")])

        results = SQLiteFTSRetriever().search("agent", docs, top_k=1)

        self.assertEqual(len(results), 1)

    @unittest.skipUnless(is_fts5_supported(), "SQLite FTS5 is not available")
    def test_sqlite_fts_retriever_supports_industry_filter(self) -> None:
        docs = build_documents_from_items(
            [item(id="ai", industry="AI"), item(id="space", industry="Commercial Space")]
        )

        results = SQLiteFTSRetriever().search("agent", docs, industry="AI")

        self.assertEqual([result["id"] for result in results], ["ai"])

    @unittest.skipUnless(is_fts5_supported(), "SQLite FTS5 is not available")
    def test_sqlite_fts_retriever_supports_tag_filter(self) -> None:
        docs = build_documents_from_items([item(id="1", tags="AI;Agent"), item(id="2", tags="Space")])

        results = SQLiteFTSRetriever().search("agent", docs, tag="Agent")

        self.assertEqual([result["id"] for result in results], ["1"])

    @unittest.skipUnless(is_fts5_supported(), "SQLite FTS5 is not available")
    def test_sqlite_fts_retriever_supports_chinese_query(self) -> None:
        docs = build_documents_from_items(
            [
                item(
                    id="space",
                    industry="Commercial Space",
                    title="Starlink 星座继续扩张",
                    summary="卫星互联网基础设施扩张",
                    tags="Space;Satellite",
                )
            ]
        )

        results = SQLiteFTSRetriever().search("卫星数据服务机会", docs, industry="space")

        self.assertEqual(results[0]["id"], "space")

    @unittest.skipUnless(is_fts5_supported(), "SQLite FTS5 is not available")
    def test_sqlite_fts_retriever_unique_alnum_query_does_not_return_noise(self) -> None:
        docs = build_documents_from_items([item(summary="This document mentions industry data")])

        results = SQLiteFTSRetriever().search("非常冷门问题xyzabc123 data", docs)

        self.assertEqual(results, [])

    def test_sqlite_fts_retriever_empty_query_raises(self) -> None:
        with self.assertRaises(ValueError):
            SQLiteFTSRetriever().search("", [])

    def test_sqlite_fts_retriever_invalid_top_k_raises(self) -> None:
        with self.assertRaises(ValueError):
            SQLiteFTSRetriever().search("agent", [], top_k=0)

    @unittest.skipUnless(is_fts5_supported(), "SQLite FTS5 is not available")
    def test_sqlite_fts_retriever_does_not_modify_documents(self) -> None:
        docs = build_documents_from_items([item()])
        original = deepcopy(docs)

        SQLiteFTSRetriever().search("agent", docs)

        self.assertEqual(docs, original)


if __name__ == "__main__":
    unittest.main()
