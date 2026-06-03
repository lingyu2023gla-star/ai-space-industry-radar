import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.report_ingestor import (
    build_report_summary_item,
    convert_report_items_to_industry_items,
    extract_report_items,
    extract_report_overview,
    extract_report_title,
    ingest_report_file,
)
from industry_radar.importer import import_records


SAMPLE_REPORT = """# AI & Commercial Space Weekly Brief

生成时间：2026-06-02 18:30:00

## 概览

- 记录数量：2
- 日期范围：2026-06-01 至 2026-06-02

## 行业分布

- AI：1
- Commercial Space：1

## 重点条目

#### 1. OpenAI 推进 Agent 产品化

- 日期：2026-06-02
- 行业：AI
- 类别：Agent
- 公司：OpenAI
- 重要性：5/5
- 标签：Agent;Product
- 来源：OpenAI Blog
- 来源链接：https://openai.com/agent-demo
- 摘要：Agent 正在进入企业工作流。
- 行业信号：Agent 商业化加速

#### 2. Starlink 星座继续扩张

- 日期：2026-06-01
- 行业：Commercial Space
- 类别：Satellite
- 公司：SpaceX
- 重要性：4/5
- 标签： Space；Satellite
- 来源：SpaceX
- 摘要：卫星互联网基础设施扩张。
- 行业信号：卫星互联网基础设施扩张
"""


class ReportIngestorTest(unittest.TestCase):
    def test_extract_report_title_reads_first_h1(self) -> None:
        self.assertEqual(extract_report_title(SAMPLE_REPORT), "AI & Commercial Space Weekly Brief")

    def test_extract_report_title_uses_fallback_without_h1(self) -> None:
        self.assertEqual(extract_report_title("## No H1", fallback="Fallback"), "Fallback")

    def test_extract_report_overview_reads_overview_section(self) -> None:
        overview = extract_report_overview(SAMPLE_REPORT)

        self.assertIn("记录数量", overview)
        self.assertIn("日期范围", overview)

    def test_extract_report_items_parses_one_item(self) -> None:
        items = extract_report_items(SAMPLE_REPORT)

        self.assertEqual(items[0]["title"], "OpenAI 推进 Agent 产品化")
        self.assertEqual(items[0]["company"], "OpenAI")

    def test_extract_report_items_parses_multiple_items(self) -> None:
        self.assertEqual(len(extract_report_items(SAMPLE_REPORT)), 2)

    def test_extract_report_items_parses_importance(self) -> None:
        self.assertEqual(extract_report_items(SAMPLE_REPORT)[0]["importance"], "5")

    def test_extract_report_items_normalizes_tags(self) -> None:
        self.assertEqual(extract_report_items(SAMPLE_REPORT)[1]["tags"], "Space;Satellite")

    def test_build_report_summary_item_generates_report_category(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "weekly.md"
            path.write_text(SAMPLE_REPORT, encoding="utf-8")

            item = build_report_summary_item(SAMPLE_REPORT, str(path))

        self.assertEqual(item["category"], "Report")
        self.assertEqual(item["source"], "Generated Report")

    def test_build_report_summary_item_source_url_uses_file_url(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "weekly.md"
            path.write_text(SAMPLE_REPORT, encoding="utf-8")

            item = build_report_summary_item(SAMPLE_REPORT, str(path))

        self.assertTrue(item["source_url"].startswith("file://"))

    def test_convert_report_items_to_industry_items_appends_report_tag(self) -> None:
        converted = convert_report_items_to_industry_items(extract_report_items(SAMPLE_REPORT), "weekly.md")

        self.assertIn("Report", converted[0]["tags"])

    def test_ingest_report_file_default_generates_summary_and_details(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "weekly.md"
            path.write_text(SAMPLE_REPORT, encoding="utf-8")

            candidates = ingest_report_file(str(path))

        self.assertEqual(len(candidates), 3)

    def test_ingest_report_file_summary_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "weekly.md"
            path.write_text(SAMPLE_REPORT, encoding="utf-8")

            candidates = ingest_report_file(str(path), include_detail_items=False)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["category"], "Report")

    def test_ingest_report_file_details_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "weekly.md"
            path.write_text(SAMPLE_REPORT, encoding="utf-8")

            candidates = ingest_report_file(str(path), include_summary_item=False)

        self.assertEqual(len(candidates), 2)
        self.assertNotEqual(candidates[0]["category"], "Report")

    def test_report_candidates_repeat_import_skips_duplicates(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "weekly.md"
            storage_path = Path(tmp_dir) / "items.csv"
            report_path.write_text(SAMPLE_REPORT, encoding="utf-8")
            candidates = ingest_report_file(str(report_path))

            first = import_records(candidates, storage_path=storage_path)
            second = import_records(candidates, storage_path=storage_path)

        self.assertGreater(first.imported, 0)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.skipped_duplicates, len(candidates))


if __name__ == "__main__":
    unittest.main()
