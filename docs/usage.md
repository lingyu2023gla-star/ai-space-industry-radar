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

## pipeline

执行常用工作流。

```bash
python -m industry_radar pipeline --sources data/sources.json --limit 5 --top 10 --report outputs/weekly.md --apply
```

默认不传 `--apply` 时为 dry-run，不写 CSV，也不生成报告。
