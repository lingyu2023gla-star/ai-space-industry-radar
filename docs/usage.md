# Usage

本文档汇总 AI Space Industry Radar 的主要 CLI 命令。

## add

交互式录入行业事件。

```bash
python -m industry_radar add
```

## import

从 JSON 或 CSV 批量导入。

```bash
python -m industry_radar import --file examples/import_items.json
```

## fetch

从 RSS / Atom 源采集元数据。

```bash
python -m industry_radar fetch --sources data/sources.example.json --dry-run --limit 5
```

`sources.json` 支持 `type` 字段；没有 `type` 时默认使用 `rss`。

```json
[
  {
    "type": "arxiv",
    "name": "arXiv AI Agent Research",
    "query": "cat:cs.AI AND all:agent",
    "industry": "AI",
    "category": "Research",
    "default_tags": "AI;Research;arXiv;Agent",
    "sort_by": "submittedDate",
    "sort_order": "descending"
  },
  {
    "type": "rss",
    "name": "arXiv cs.AI",
    "url": "https://rss.arxiv.org/rss/cs.AI",
    "industry": "AI",
    "category": "Research",
    "default_tags": "AI;Research;arXiv"
  }
]
```

本地 Markdown / TXT source 示例：

```json
{
  "type": "local_file",
  "name": "AI Agent Notes",
  "path": "examples/local_notes/ai_agent_notes.md",
  "industry": "AI",
  "category": "Research Notes",
  "default_tags": "AI;Agent;Notes",
  "mode": "single"
}
```

```json
{
  "type": "local_file",
  "name": "AI Space Research Notes",
  "path": "examples/local_notes/ai_space_research_notes.md",
  "industry": "AI",
  "category": "Research Notes",
  "default_tags": "AI;Space;Notes",
  "mode": "sections"
}
```

也可以用 `arxiv_category` 简化 arXiv 查询：

```json
{
  "type": "arxiv",
  "name": "arXiv cs.AI",
  "arxiv_category": "cs.AI",
  "industry": "AI",
  "category": "Research",
  "default_tags": "AI;Research;arXiv"
}
```

```bash
python -m industry_radar fetch --sources data/sources.json --dry-run --limit 5
```

## list

查询已有记录。

```bash
python -m industry_radar list --industry AI --tag Agent --limit 10
```

## stats

查看数据集统计。

```bash
python -m industry_radar stats
```

## dedupe

预览或执行事件级去重。

```bash
python -m industry_radar dedupe --dry-run
```

写回 CSV：

```bash
python -m industry_radar dedupe --apply
```

## enrich

使用 DeepSeek 对已有记录做结构化增强。

```bash
python -m industry_radar enrich --industry AI --limit 5 --dry-run
```

写回 CSV：

```bash
python -m industry_radar enrich --industry AI --limit 5 --apply
```

## report

生成 Markdown 行业简报。

```bash
python -m industry_radar report --top 5 --output outputs/top5_report.md
```

## report-ingest

将 Markdown report 沉淀为本地 KB items。

```bash
python -m industry_radar report-ingest --file outputs/top5_report.md --dry-run
python -m industry_radar report-ingest --file outputs/top5_report.md --apply
python -m industry_radar report-ingest --file outputs/top5_report.md --summary-only --dry-run
python -m industry_radar report-ingest --file outputs/top5_report.md --details-only --dry-run
```

## research

围绕一个研究问题生成 Markdown 研究笔记。

```bash
python -m industry_radar research "AI Agent 商业化趋势"
python -m industry_radar research "AI Agent 商业化趋势" --retriever fts --top 8 --apply --output outputs/agent_research.md
python -m industry_radar research "商业航天数据服务机会" --industry space --retriever keyword --apply --ingest
python -m industry_radar research "多智能体研究趋势" --tag arXiv --llm --apply
```

## pipeline

执行常用工作流。

```bash
python -m industry_radar pipeline --sources data/sources.json --limit 5 --top 10 --report outputs/weekly.md --apply
```

默认不传 `--apply` 时为 dry-run，不写 CSV，也不生成报告。

使用 JSON 配置文件：

```bash
python -m industry_radar pipeline --config configs/example_pipeline.json
python -m industry_radar pipeline --config configs/example_pipeline.json --apply
python -m industry_radar pipeline --config configs/example_ai_pipeline.json --limit 10 --industry space --apply
python -m industry_radar pipeline --config configs/example_pipeline.json --save-run-log
python -m industry_radar pipeline --config configs/example_pipeline.json --skip-unhealthy-sources
python -m industry_radar pipeline --config configs/example_pipeline.json --skip-unhealthy-sources --failure-rate-threshold 0.5 --min-source-runs 2
python -m industry_radar pipeline --config configs/example_pipeline.json --apply --ingest-report
```

## runs

查看最近 pipeline 运行日志。

```bash
python -m industry_radar runs
```

## run-show

查看某次运行日志详情。

```bash
python -m industry_radar run-show RUN_ID
```

## source-health

基于 run logs 分析数据源健康状态。

```bash
python -m industry_radar source-health
python -m industry_radar source-health --sources data/sources.json --limit 20
```

## dashboard

导出静态 HTML Dashboard。

```bash
python -m industry_radar dashboard
python -m industry_radar dashboard --output outputs/dashboard.html --top 10
python -m industry_radar dashboard --sources data/sources.json
```

## ask

基于本地知识库检索问答。

```bash
python -m industry_radar ask "最近 AI Agent 有哪些趋势？"
python -m industry_radar ask "商业航天有哪些机会？" --industry space --top 5
python -m industry_radar ask "多智能体有什么研究趋势？" --tag arXiv --top 3
python -m industry_radar ask "最近 AI Agent 有哪些趋势？" --llm
python -m industry_radar ask "AI Agent 有哪些趋势？" --retriever embedding
python -m industry_radar ask "AI Agent 有哪些趋势？" --retriever fts
python -m industry_radar ask "AI Agent 有哪些趋势？" --retriever fts --no-citations
python -m industry_radar ask "AI Agent 有哪些趋势？" --retriever fts --llm --citations
```
