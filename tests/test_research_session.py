import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.knowledge_base import build_documents_from_items
from industry_radar.research_session import (
    build_research_context,
    build_research_llm_prompt,
    generate_local_research_notes,
    render_research_report,
    write_research_report,
)


def item(**overrides) -> dict:
    data = {
        "id": "1",
        "date": "2026-06-02",
        "industry": "AI",
        "category": "Agent",
        "company": "OpenAI",
        "title": "OpenAI 推进 Agent 产品化",
        "summary": "Agent enterprise workflow",
        "signal": "Agent 商业化加速",
        "tags": "AI;Agent",
        "source": "OpenAI Blog",
        "source_url": "https://example.com",
        "importance": 5,
    }
    data.update(overrides)
    return data


class ResearchSessionTest(unittest.TestCase):
    def test_build_research_context_generates_evidence(self) -> None:
        result = build_documents_from_items([item()])[0]

        context = build_research_context("Agent 趋势", [result])

        self.assertEqual(context["evidence_count"], 1)
        self.assertEqual(context["evidence"][0]["title"], "OpenAI 推进 Agent 产品化")

    def test_build_research_context_uses_citation_label(self) -> None:
        result = build_documents_from_items([item()])[0]

        context = build_research_context("Agent 趋势", [result])

        self.assertEqual(context["evidence"][0]["label"], "[1]")

    def test_generate_local_research_notes_with_evidence(self) -> None:
        result = build_documents_from_items([item()])[0]
        context = build_research_context("Agent 趋势", [result])

        notes = generate_local_research_notes(context)

        self.assertIn("## 研究问题", notes)
        self.assertIn("## 关键证据", notes)
        self.assertIn("[1] OpenAI 推进 Agent 产品化", notes)

    def test_generate_local_research_notes_without_evidence(self) -> None:
        notes = generate_local_research_notes(build_research_context("missing", []))

        self.assertIn("证据不足", notes)

    def test_build_research_llm_prompt_contains_query_and_numbered_evidence(self) -> None:
        result = build_documents_from_items([item()])[0]
        context = build_research_context("Agent 趋势", [result])

        messages = build_research_llm_prompt(context)

        self.assertIn("Agent 趋势", messages[1]["content"])
        self.assertIn("[1]", messages[1]["content"])

    def test_build_research_llm_prompt_requires_citation_labels(self) -> None:
        messages = build_research_llm_prompt(build_research_context("Agent 趋势", []))

        self.assertIn("必须使用 [1]、[2] 形式引用证据", messages[1]["content"])

    def test_render_research_report_contains_metadata(self) -> None:
        report = render_research_report("Agent 趋势", "# Research Session: Agent 趋势")

        self.assertIn("## Metadata", report)

    def test_render_research_report_includes_llm_notes(self) -> None:
        report = render_research_report("Agent 趋势", "# Local", llm_notes="LLM notes")

        self.assertIn("## LLM 综合分析", report)
        self.assertIn("LLM notes", report)

    def test_write_research_report_writes_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "research.md"

            written = write_research_report("# Research", str(output))

            self.assertEqual(written, str(output))
            self.assertEqual(output.read_text(encoding="utf-8"), "# Research")


if __name__ == "__main__":
    unittest.main()
