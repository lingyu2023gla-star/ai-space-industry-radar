# Changelog

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
