import unittest
from copy import deepcopy

from industry_radar.knowledge_base import build_documents_from_items
from industry_radar.retrievers import (
    EmbeddingRetriever,
    HashingEmbeddingProvider,
    KeywordRetriever,
    cosine_similarity,
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


if __name__ == "__main__":
    unittest.main()
