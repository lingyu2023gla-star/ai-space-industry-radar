from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .knowledge_base import build_citation_entries, format_citations_text


def build_research_context(query: str, results: list[dict]) -> dict:
    evidence = []
    for citation, result in zip(build_citation_entries(results), results):
        entry = dict(citation)
        entry["tags"] = str(result.get("tags", ""))
        evidence.append(entry)
    return {
        "query": query,
        "evidence_count": len(evidence),
        "evidence": evidence,
    }


def generate_local_research_notes(context: dict) -> str:
    query = str(context.get("query", ""))
    evidence = list(context.get("evidence", []))
    lines = [
        f"# Research Session: {query}",
        "",
        "## 研究问题",
        "",
        query,
        "",
        "## 初步结论",
        "",
    ]
    if not evidence:
        lines.extend(
            [
                "本地知识库中没有检索到足够相关的证据，当前无法形成可靠结论。",
                "",
                "## 关键证据",
                "",
                "暂无关键证据。",
                "",
                "## 观察与趋势",
                "",
                "- 证据不足，需要补充更多数据源后再判断。",
            ]
        )
    else:
        labels = "".join(item["label"] for item in evidence[: min(3, len(evidence))])
        lines.extend(
            [
                f"基于本地知识库，当前可检索到 {len(evidence)} 条相关证据。主要信息集中在这些证据所覆盖的公司动态、研究进展和行业信号中 {labels}。",
                "",
                "## 关键证据",
                "",
                format_citations_text(evidence, include_summary=True),
                "",
                "## 观察与趋势",
                "",
                f"- 结合证据 {labels}，可以看到该问题在本地资料中已有可追踪线索。",
                "- 当前结论仅基于本地知识库，不代表外部实时验证结果。",
            ]
        )
    lines.extend(
        [
            "",
            "## 后续问题",
            "",
            "- 还需要补充哪些数据源？",
            "- 哪些结论需要进一步验证？",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_research_llm_prompt(context: dict) -> list[dict]:
    query = str(context.get("query", ""))
    evidence_blocks = []
    for item in context.get("evidence", []):
        evidence_blocks.append(
            "\n".join(
                [
                    item.get("label", ""),
                    f"标题：{item.get('title', '')}",
                    f"日期：{item.get('date', '')}",
                    f"行业：{item.get('industry', '')}",
                    f"公司：{item.get('company', '')}",
                    f"来源：{item.get('source', '')}",
                    f"链接：{item.get('source_url', '')}",
                    f"摘要：{item.get('summary', '')}",
                    f"行业信号：{item.get('signal', '')}",
                    f"标签：{item.get('tags', '')}",
                ]
            )
        )
    return [
        {
            "role": "system",
            "content": "你是严谨的行业研究分析助手，只能基于给定证据进行分析，不要编造。输出中文 Markdown。",
        },
        {
            "role": "user",
            "content": (
                f"研究问题：{query}\n\n"
                "编号证据：\n"
                + "\n\n".join(evidence_blocks)
                + (
                    "\n\n请输出中文 Markdown，包含：研究结论、关键证据、趋势判断、不确定性、后续研究问题。"
                    "必须使用 [1]、[2] 形式引用证据编号。只能基于给定证据回答，不要编造。"
                    "如果证据不足，要说明不足。"
                )
            ),
        },
    ]


def render_research_report(
    query: str,
    local_notes: str,
    llm_notes: str | None = None,
    metadata: dict | None = None,
) -> str:
    lines = [local_notes.rstrip()]
    if llm_notes:
        lines.extend(["", "## LLM 综合分析", "", llm_notes.strip()])
    lines.extend(["", "## Metadata"])
    for key, value in (metadata or {}).items():
        lines.append(f"- {key}: {value}")
    if "generated_at" not in (metadata or {}):
        lines.append(f"- generated_at: {datetime.now().replace(microsecond=0).isoformat()}")
    if "query" not in (metadata or {}):
        lines.append(f"- query: {query}")
    return "\n".join(lines).rstrip() + "\n"


def write_research_report(markdown: str, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return str(path)
