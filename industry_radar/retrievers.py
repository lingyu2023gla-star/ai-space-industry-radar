from __future__ import annotations

import hashlib
import math
import sqlite3

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


def is_fts5_supported() -> bool:
    connection = None
    try:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content)")
    except sqlite3.OperationalError:
        return False
    finally:
        if connection is not None:
            connection.close()
    return True


def ensure_fts5_supported() -> None:
    if not is_fts5_supported():
        raise RuntimeError("SQLite FTS5 is not supported by this Python sqlite3 build")


def build_fts_query(query: str) -> str:
    if not clean_text(query):
        raise ValueError("query must not be empty")
    tokens = [
        token
        for token in tokenize(query)
        if token.replace("_", "").isalnum() or any("\u4e00" <= char <= "\u9fff" for char in token)
    ]
    if not tokens:
        raise ValueError("query must contain searchable tokens")
    return " OR ".join(dict.fromkeys(tokens))


class SQLiteFTSRetriever(BaseRetriever):
    def __init__(self, use_memory: bool = True):
        self.use_memory = use_memory

    def search(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
        **filters,
    ) -> list[dict]:
        if top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        fts_query = build_fts_query(query)
        query_tokens = set(tokenize(query))
        query_alnum_tokens = {token for token in query_tokens if token.isascii() and token.isalnum()}
        filtered = filter_documents(documents, **filters)
        if not filtered:
            return []
        ensure_fts5_supported()
        connection = sqlite3.connect(":memory:" if self.use_memory else "")
        try:
            self._create_index(connection, filtered)
            rows = connection.execute(
                """
                SELECT doc_id, bm25(docs_fts, 0.0, 4.0, 2.0, 3.0, 3.0, 1.0, 1.0, 1.0, 1.5) AS rank
                FROM docs_fts
                WHERE docs_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, max(top_k * 5, top_k)),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise ValueError(f"invalid FTS query: {exc}") from exc
        finally:
            connection.close()

        docs_by_id = {str(index): doc for index, doc in enumerate(filtered)}
        results = []
        for doc_id, bm25_score in rows:
            doc = docs_by_id.get(str(doc_id))
            if doc is None:
                continue
            doc_tokens = set(tokenize(str(doc.get("text", ""))))
            if query_alnum_tokens and not query_alnum_tokens <= doc_tokens:
                continue
            relevance_score = 1 / (1 + abs(float(bm25_score)))
            final_score = relevance_score + int_or_zero(doc.get("importance")) * 0.01
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

    def _create_index(self, connection: sqlite3.Connection, documents: list[dict]) -> None:
        connection.execute(
            """
            CREATE VIRTUAL TABLE docs_fts USING fts5(
                doc_id UNINDEXED,
                title,
                summary,
                signal,
                tags,
                company,
                category,
                source,
                text
            )
            """
        )
        rows = [
            (
                str(index),
                self._fts_index_text(doc.get("title", "")),
                self._fts_index_text(doc.get("summary", "")),
                self._fts_index_text(doc.get("signal", "")),
                self._fts_index_text(doc.get("tags", "")),
                self._fts_index_text(doc.get("company", "")),
                self._fts_index_text(doc.get("category", "")),
                self._fts_index_text(doc.get("source", "")),
                self._fts_index_text(doc.get("text", "")),
            )
            for index, doc in enumerate(documents)
        ]
        connection.executemany(
            """
            INSERT INTO docs_fts(
                doc_id, title, summary, signal, tags, company, category, source, text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _fts_index_text(self, value: object) -> str:
        text = clean_text(str(value))
        tokens = " ".join(tokenize(text))
        return f"{text} {tokens}".strip()
