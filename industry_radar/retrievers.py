from __future__ import annotations

import hashlib
import math

from .knowledge_base import filter_documents, int_or_zero, search_documents, tokenize
from .text_utils import clean_text


class BaseRetriever:
    def search(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
        **filters,
    ) -> list[dict]:
        raise NotImplementedError


class KeywordRetriever(BaseRetriever):
    def search(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
        **filters,
    ) -> list[dict]:
        return search_documents(query, documents, top_k=top_k, **filters)


class EmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class HashingEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 256):
        if not isinstance(dimensions, int) or isinstance(dimensions, bool) or dimensions <= 0:
            raise ValueError("dimensions must be a positive integer")
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = tokenize(text)
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            index = int(digest, 16) % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if len(vec_a) != len(vec_b):
        raise ValueError("vectors must have the same length")
    norm_a = math.sqrt(sum(value * value for value in vec_a))
    norm_b = math.sqrt(sum(value * value for value in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    dot = sum(left * right for left, right in zip(vec_a, vec_b))
    return dot / (norm_a * norm_b)


class EmbeddingRetriever(BaseRetriever):
    def __init__(self, embedding_provider: EmbeddingProvider | None = None):
        self.embedding_provider = embedding_provider or HashingEmbeddingProvider()

    def search(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
        **filters,
    ) -> list[dict]:
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if not clean_text(query):
            raise ValueError("query must not be empty")
        query_tokens = set(tokenize(query))
        query_alnum_tokens = {token for token in query_tokens if token.isascii() and token.isalnum()}
        filtered = filter_documents(documents, **filters)
        query_embedding = self.embedding_provider.embed_text(query)
        results = []
        for doc in filtered:
            doc_tokens = set(tokenize(str(doc.get("text", ""))))
            if query_alnum_tokens and not (query_alnum_tokens & doc_tokens):
                continue
            doc_embedding = self.embedding_provider.embed_text(str(doc.get("text", "")))
            cosine_score = cosine_similarity(query_embedding, doc_embedding)
            if cosine_score <= 0:
                continue
            final_score = cosine_score + int_or_zero(doc.get("importance")) * 0.01
            result = dict(doc)
            result["score"] = final_score
            results.append(result)
        return sorted(
            results,
            key=lambda doc: (
                doc["score"],
                int_or_zero(doc.get("importance")),
                str(doc.get("date", "")),
            ),
            reverse=True,
        )[:top_k]
