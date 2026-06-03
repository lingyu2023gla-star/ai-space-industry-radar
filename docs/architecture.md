# Architecture

AI Space Industry Radar 是一个标准库优先的 CLI 项目，围绕统一的 `IndustryItem`
数据模型构建行业信息采集、清洗、导入、增强、治理和报告生成流程。

## 整体架构

```mermaid
flowchart TD
    A[add / import / fetch] --> B[clean & normalize]
    B --> C[CSV Storage]
    C --> D[stats / dedupe]
    D --> E[DeepSeek enrich]
    E --> C
    C --> F[list / report]
    F --> G[Markdown Brief]
    H[pipeline] --> A
    H --> D
    H --> E
    H --> F
```

## 模块职责

| 模块 | 职责 |
|---|---|
| `cli.py` | 命令行入口，解析参数并调用各功能模块 |
| `models.py` | 数据模型、输入清洗、行业标准化、日期与重要性校验 |
| `storage_backend.py` | `StorageBackend` 抽象、`CsvStorage` 实现、存储后端工厂 |
| `storage.py` | 兼容层函数，委托给 `CsvStorage` 并保留旧调用方式 |
| `importer.py` | JSON / CSV 批量导入、导入记录标准化、导入去重 |
| `fetcher.py` | RSS / Atom 采集、XML 清洗解析、feed item 转换 |
| `enricher.py` | LLM prompt 构造、增强结果解析、字段合并 |
| `llm_client.py` | DeepSeek OpenAI-compatible API 调用 |
| `data_governance.py` | `stats` 统计、事件级 `dedupe`、重复组合并 |
| `report.py` | Markdown 行业简报生成、排序、分布统计 |
| `pipeline.py` | 工作流编排，串联 fetch / dedupe / enrich / report |

## 数据流

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Fetcher
    participant Importer
    participant Storage
    participant Enricher
    participant Report

    User->>CLI: pipeline --sources ... --apply
    CLI->>Fetcher: fetch RSS/Atom
    Fetcher->>Importer: candidate items
    Importer->>Storage: write normalized CSV
    CLI->>Storage: read items
    CLI->>Enricher: optional DeepSeek enrich
    Enricher->>Storage: write updated items
    CLI->>Report: generate markdown
```

## 配置驱动流程

```mermaid
flowchart TD
    A[config.json] --> B[config.py load / validate / merge]
    B --> C[pipeline.py]
    C --> D[fetch]
    C --> E[dedupe]
    C --> F[enrich]
    C --> G[report]
```

## 存储层抽象

```mermaid
flowchart TD
    A[CLI / Pipeline] --> B[StorageBackend]
    B --> C[CsvStorage]
    C --> D[data/industry_items.csv]
```

v1.2 开始，上层业务可以依赖 `StorageBackend` 的 `read_items`、`write_items`
和 `append_items` 能力，而不直接绑定 CSV 细节。当前默认后端仍然是 `CsvStorage`，
CSV 表头、兼容迁移和命令行为保持不变。

`storage.py` 继续保留 `read_items`、`write_items`、`append_item`、`append_items`
等旧函数，内部委托给 `CsvStorage`。这样可以避免一次性重构所有业务模块，同时为未来
扩展 `SQLiteStorage` 留出接口。

## 设计原则

- 标准库优先，降低运行和部署门槛。
- CSV 优先，便于审计、迁移和人工检查。
- dry-run / apply 分离，降低误写入和 API 成本风险。
- 外部网络和 LLM 调用集中封装，测试中通过 mock 隔离。
- 采集、导入、治理、增强和报告模块边界清晰，便于后续替换存储或接入 Web UI。

## 关键原则

- 标准库优先。
- dry-run 优先。
- 数据入口统一。
- LLM 与业务逻辑解耦。
- 可测试性优先。
