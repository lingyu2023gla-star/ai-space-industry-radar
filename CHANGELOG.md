# Changelog

## v2.6.0

- 新增 research collection 管理能力
- research 支持 --save-session
- 新增 research-list
- 新增 research-show
- 新增 research-ingest
- 新增 research-delete

## v2.5.0

- 新增 research 命令
- 支持基于本地检索生成 Markdown 研究笔记
- 支持可选 DeepSeek 综合分析
- 支持将 research report 沉淀回 KB

## v2.4.0

- 新增 report-ingest 命令
- 支持将 Markdown report 沉淀为 IndustryItem
- pipeline 支持 --ingest-report
- ask 可以检索历史简报内容

## v2.3.0

- ask 默认支持 citation labels
- 本地回答显示 [1][2] 引用
- LLM ask prompt 支持编号证据
- 新增证据列表格式化能力

## v2.2.0

- 新增 SQLiteFTSRetriever
- ask 支持 --retriever fts
- 使用 Python sqlite3 FTS5 实现本地全文检索
- 保持 keyword 默认检索方式不变

## v2.1.0

- 新增 Retriever 抽象
- 新增 KeywordRetriever
- 新增 HashingEmbeddingProvider
- 新增 EmbeddingRetriever
- ask 命令支持 --retriever keyword|embedding
- 为未来真实 embedding provider / vector database 做准备

## v2.0.0

- 新增 Local Knowledge Base
- 新增 ask 命令
- 支持本地关键词检索问答
- 支持可选 DeepSeek 综合回答
- 支持 industry/tag/company/date 筛选

## v1.9.0

- 新增 LocalFileSourceAdapter
- 支持 type=local_file 数据源
- 支持 single / sections 两种模式
- 支持从本地 Markdown / TXT 文件生成 candidate items
- 新增 examples/local_notes 示例资料

## v1.8.0

- 新增 dashboard 命令
- 支持生成静态 HTML 看板
- 展示数据集统计、最近事件、最近 runs、source health
- outputs/*.html 默认忽略

## v1.7.0

- 新增 Source Failure Policy
- pipeline 支持 --skip-unhealthy-sources
- 支持按历史失败率跳过不健康 source
- 支持 failure_rate_threshold 和 min_source_runs
- run log 记录 source policy 执行结果

## v1.6.0

- 新增 source-health 命令
- 基于 runs/*.json 聚合数据源失败率
- 支持查看 source 最近错误和失败率
- 支持从 sources.json 补全 source 列表

## v1.5.0

- 增加 pipeline 运行日志
- 新增 --save-run-log
- 新增 runs 命令
- 新增 run-show 命令
- 支持记录 fetch / dedupe / enrich / report 指标和错误

## v1.4.0

- 新增 ArxivSourceAdapter
- 支持 type=arxiv 数据源
- 支持 arXiv API query / arxiv_category 配置
- arXiv API 结果转换为统一 IndustryItem candidate dict

## v1.3.0

- 引入 Source Adapter 数据源插件架构
- 新增 RSSSourceAdapter
- sources.json 支持 type 字段
- fetcher 改造为数据源编排层
- 兼容旧 sources 配置

## v1.2.0

- 引入 StorageBackend 抽象
- 增加 CsvStorage 实现
- 保留 storage.py 兼容层
- 为未来 SQLiteStorage 做准备

## v1.1.0

- 增加配置化 Pipeline
- 新增 configs 示例
- 支持 defaults < config < CLI 参数合并
- 保持 --apply 显式写入策略

## v1.0.0

- 完成项目文档化与作品集包装
- 增加 README 架构说明
- 增加 docs 文档
- 增加 examples 示例数据
- 增加 Makefile
- 增加版本号

## v0.9.0

- 增加 pipeline 工作流

## v0.8.0

- 增加 stats 和 dedupe

## v0.7.0

- 增加 DeepSeek enrich

## v0.6.0

- 增强报告质量

## v0.5.0

- 增加 RSS fetch

## v0.4.0

- 增加批量导入和去重

## v0.1.0

- 基础 CLI MVP
