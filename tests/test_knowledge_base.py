import unittest

from industry_radar.knowledge_base import (
    build_ask_prompt,
    build_citation_entries,
    build_documents_from_items,
    build_retrieval_answer,
    filter_documents,
    format_citation_label,
    format_citations_text,
    score_document,
    search_documents,
    tokenize,
)


def item(**overrides) -> dict:
    data = {
        "id": "1",
        "date": "2026-06-02",
        "industry": "AI",
        "category": "Agent",
        "company": "OpenAI",
        "title": "OpenAI 推进 Agent 产品化",
        "summary": "Agent is moving into enterprise workflow automation.",
        "signal": "Agent 商业化加速",
        "tags": "AI;Agent;Product",
        "source": "OpenAI Blog",
        "source_url": "https://example.com",
        "importance": 5,
    }
    data.update(overrides)
    return data


class KnowledgeBaseTest(unittest.TestCase):
    def test_build_documents_from_items_generates_document(self) -> None:
        docs = build_documents_from_items([item()])

        self.assertEqual(docs[0]["id"], "1")
        self.assertIn("text", docs[0])

    def test_document_text_contains_searchable_fields(self) -> None:
        doc = build_documents_from_items([item()])[0]

        self.assertIn("OpenAI 推进 Agent 产品化", doc["text"])
        self.assertIn("Agent is moving", doc["text"])
        self.assertIn("Agent 商业化加速", doc["text"])
        self.assertIn("AI;Agent;Product", doc["text"])

    def test_tokenize_handles_english(self) -> None:
        self.assertIn("agent", tokenize("AI Agent workflow"))

    def test_tokenize_handles_chinese(self) -> None:
        tokens = tokenize("多智能体研究趋势")

        self.assertIn("多智能体研究趋势", tokens)
        self.assertIn("研究", tokens)

    def test_tokenize_removes_english_stop_words(self) -> None:
        tokens = tokenize("the agent and workflow")

        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)
        self.assertIn("agent", tokens)

    def test_score_document_title_match_scores_higher_than_summary_match(self) -> None:
        title_doc = build_documents_from_items([item(title="Agent trend", summary="")])[0]
        summary_doc = build_documents_from_items([item(title="Other", summary="Agent trend")])[0]

        self.assertGreater(score_document("agent", title_doc), score_document("agent", summary_doc))

    def test_score_document_no_match_returns_zero(self) -> None:
        doc = build_documents_from_items([item()])[0]

        self.assertEqual(score_document("satellite", doc), 0)

    def test_search_documents_returns_top_k(self) -> None:
        docs = build_documents_from_items(
            [item(id="1", title="Agent one"), item(id="2", title="Agent two")]
        )

        results = search_documents("agent", docs, top_k=1)

        self.assertEqual(len(results), 1)

    def test_search_documents_sorts_by_score_descending(self) -> None:
        docs = build_documents_from_items(
            [
                item(id="low", title="Other", summary="Agent"),
                item(id="high", title="Agent", summary="Agent"),
            ]
        )

        results = search_documents("agent", docs)

        self.assertEqual(results[0]["id"], "high")

    def test_search_documents_supports_industry_filter(self) -> None:
        docs = build_documents_from_items(
            [item(id="ai", industry="AI"), item(id="space", industry="Commercial Space")]
        )

        results = search_documents("agent", docs, industry="ai")

        self.assertEqual([result["id"] for result in results], ["ai"])

    def test_search_documents_supports_tag_filter(self) -> None:
        docs = build_documents_from_items([item(id="1", tags="AI;Agent"), item(id="2", tags="Space")])

        results = search_documents("agent", docs, tag="agent")

        self.assertEqual([result["id"] for result in results], ["1"])

    def test_search_documents_supports_company_filter(self) -> None:
        docs = build_documents_from_items([item(id="1", company="OpenAI"), item(id="2", company="Anthropic")])

        results = search_documents("agent", docs, company="open")

        self.assertEqual([result["id"] for result in results], ["1"])

    def test_search_documents_supports_date_filters(self) -> None:
        docs = build_documents_from_items(
            [item(id="old", date="2026-06-01"), item(id="new", date="2026-06-03")]
        )

        results = search_documents("agent", docs, since="2026-06-02", until="2026-06-03")

        self.assertEqual([result["id"] for result in results], ["new"])

    def test_filter_documents_reuses_search_filters(self) -> None:
        docs = build_documents_from_items([item(id="1", tags="AI;Agent"), item(id="2", tags="Space")])

        results = filter_documents(docs, tag="agent")

        self.assertEqual([result["id"] for result in results], ["1"])

    def test_search_documents_empty_query_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            search_documents("", [])

    def test_build_retrieval_answer_without_results(self) -> None:
        self.assertIn("没有在本地知识库", build_retrieval_answer("question", []))

    def test_format_citation_label(self) -> None:
        self.assertEqual(format_citation_label(1), "[1]")

    def test_format_citation_label_invalid_index_raises(self) -> None:
        with self.assertRaises(ValueError):
            format_citation_label(0)

    def test_build_citation_entries_generates_numbered_evidence(self) -> None:
        result = build_documents_from_items([item()])[0]

        citation = build_citation_entries([result])[0]

        self.assertEqual(citation["index"], 1)
        self.assertEqual(citation["label"], "[1]")
        self.assertEqual(citation["title"], "OpenAI 推进 Agent 产品化")

    def test_build_citation_entries_does_not_modify_results(self) -> None:
        result = build_documents_from_items([item()])[0]
        original = dict(result)

        build_citation_entries([result])

        self.assertEqual(result, original)

    def test_format_citations_text_contains_title_and_source_url(self) -> None:
        result = build_documents_from_items([item()])[0]
        citations = build_citation_entries([result])

        text = format_citations_text(citations)

        self.assertIn("[1] OpenAI 推进 Agent 产品化", text)
        self.assertIn("链接：https://example.com", text)

    def test_format_citations_text_omits_empty_source_url(self) -> None:
        result = build_documents_from_items([item(source_url="")])[0]
        citations = build_citation_entries([result])

        text = format_citations_text(citations)

        self.assertNotIn("链接：", text)

    def test_build_retrieval_answer_with_results_contains_citation_label(self) -> None:
        result = build_documents_from_items([item()])[0]

        answer = build_retrieval_answer("agent", [result])

        self.assertIn("[1]", answer)
        self.assertIn("OpenAI 推进 Agent 产品化", answer)
        self.assertIn("相关证据", answer)

    def test_build_retrieval_answer_without_citations_uses_legacy_style(self) -> None:
        result = build_documents_from_items([item()])[0]

        answer = build_retrieval_answer("agent", [result], with_citations=False)

        self.assertNotIn("[1]", answer)
        self.assertIn("1. OpenAI 推进 Agent 产品化", answer)

    def test_build_ask_prompt_contains_query_and_evidence(self) -> None:
        result = build_documents_from_items([item()])[0]

        messages = build_ask_prompt("AI Agent 趋势", [result])

        self.assertIn("AI Agent 趋势", messages[1]["content"])
        self.assertIn("[1]", messages[1]["content"])
        self.assertIn("标题：OpenAI 推进 Agent 产品化", messages[1]["content"])

    def test_build_ask_prompt_requires_llm_to_use_citation_labels(self) -> None:
        result = build_documents_from_items([item()])[0]

        messages = build_ask_prompt("AI Agent 趋势", [result])

        self.assertIn("必须使用 [1]、[2] 形式引用证据", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
