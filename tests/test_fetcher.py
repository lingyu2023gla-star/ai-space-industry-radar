import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from industry_radar.fetcher import (
    USER_AGENT,
    feed_entry_to_import_record,
    fetch_and_import,
    fetch_records,
    parse_feed_date,
    parse_feed_xml,
    read_url,
    sanitize_xml_content,
)
from industry_radar.storage import read_items


RSS_XML = """\
<rss>
  <channel>
    <item>
      <title>OpenAI Agent update</title>
      <link>https://example.com/openai-agent</link>
      <description>Agent product update</description>
      <pubDate>Tue, 02 Jun 2026 17:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


ATOM_XML = """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Space launch update</title>
    <link href="https://example.com/space-launch" />
    <summary>Launch market update</summary>
    <updated>2026-06-03T08:00:00Z</updated>
  </entry>
</feed>
"""


ARXIV_XML = """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>https://arxiv.org/abs/2606.00001</id>
    <updated>2026-06-03T08:00:00Z</updated>
    <published>2026-06-02T17:30:00Z</published>
    <title>Agent Research</title>
    <summary>Agent research summary</summary>
    <category term="cs.AI" />
  </entry>
</feed>
"""


def source_config(**overrides: str) -> dict[str, str]:
    source = {
        "name": "OpenAI Blog",
        "url": "https://example.com/rss.xml",
        "industry": "AI",
        "category": "AI Company",
        "default_tags": "AI;Model;Company",
    }
    source.update(overrides)
    return source


def arxiv_source_config(**overrides: str) -> dict[str, str]:
    source = {
        "type": "arxiv",
        "name": "arXiv AI Agent Research",
        "query": "cat:cs.AI AND all:agent",
        "industry": "AI",
        "category": "Research",
        "default_tags": "AI;Research;arXiv;Agent",
    }
    source.update(overrides)
    return source


def local_file_source_config(**overrides: str) -> dict[str, str]:
    source = {
        "type": "local_file",
        "name": "AI Agent Notes",
        "path": "notes.md",
        "industry": "AI",
        "category": "Research Notes",
        "default_tags": "AI;Agent;Notes",
        "mode": "single",
    }
    source.update(overrides)
    return source


def write_sources(path: Path, sources: list[dict[str, str]]) -> None:
    path.write_text(json.dumps(sources), encoding="utf-8")


class FetcherTest(unittest.TestCase):
    def test_read_url_sends_user_agent_header(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, _exc_type, _exc, _traceback) -> None:
                return None

            def read(self) -> bytes:
                return b"<rss />"

        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("industry_radar.source_adapters.urllib.request.urlopen", fake_urlopen):
            content = read_url("https://example.com/feed.xml", timeout=3)

        self.assertEqual(content, b"<rss />")
        self.assertEqual(captured["timeout"], 3)
        self.assertEqual(captured["request"].headers["User-agent"], USER_AGENT)

    def test_sanitize_xml_content_removes_prefix_before_first_tag(self) -> None:
        content = sanitize_xml_content(b"junk bytes before xml\n<rss />")

        self.assertEqual(content, "<rss />")

    def test_sanitize_xml_content_removes_invalid_control_chars(self) -> None:
        content = sanitize_xml_content(b"<rss>\x00<title>Bad\x08Char</title></rss>")

        self.assertEqual(content, "<rss><title>BadChar</title></rss>")

    def test_sanitize_xml_content_keeps_allowed_whitespace_controls(self) -> None:
        content = sanitize_xml_content(b"<rss>\t\n\r<title>OK</title></rss>")

        self.assertIn("\t\n\r", content)

    def test_malformed_xml_error_includes_xml_parse_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            write_sources(sources_path, [source_config()])

            with patch("industry_radar.source_adapters.read_url", return_value=b"<rss><broken></rss>"):
                result = fetch_records(sources_path)

            self.assertEqual(result.failed, 1)
            self.assertIn("XML parse error", result.errors[0])

    def test_parse_basic_rss_xml(self) -> None:
        entries = parse_feed_xml(RSS_XML)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "OpenAI Agent update")
        self.assertEqual(entries[0]["link"], "https://example.com/openai-agent")

    def test_parse_basic_atom_xml(self) -> None:
        entries = parse_feed_xml(ATOM_XML)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Space launch update")
        self.assertEqual(entries[0]["link"], "https://example.com/space-launch")

    def test_rss_item_converts_to_import_dict(self) -> None:
        entry = parse_feed_xml(RSS_XML)[0]

        record = feed_entry_to_import_record(entry, source_config())

        self.assertEqual(record["title"], "OpenAI Agent update")
        self.assertEqual(record["source_url"], "https://example.com/openai-agent")
        self.assertEqual(record["industry"], "AI")
        self.assertEqual(record["importance"], 3)

    def test_feed_summary_is_cleaned(self) -> None:
        entry = {
            "title": "Title",
            "link": "https://example.com",
            "summary": "<p>AI &amp; Space<br>Update</p>",
            "published": "Tue, 02 Jun 2026 17:30:00 GMT",
        }

        record = feed_entry_to_import_record(entry, source_config())

        self.assertEqual(record["summary"], "AI & Space Update")

    def test_atom_entry_converts_to_import_dict(self) -> None:
        entry = parse_feed_xml(ATOM_XML)[0]

        record = feed_entry_to_import_record(entry, source_config(name="Space News", industry="Commercial Space"))

        self.assertEqual(record["title"], "Space launch update")
        self.assertEqual(record["source"], "Space News")
        self.assertEqual(record["industry"], "Commercial Space")

    def test_pub_date_converts_to_yyyy_mm_dd(self) -> None:
        self.assertEqual(
            parse_feed_date("Tue, 02 Jun 2026 17:30:00 GMT"),
            "2026-06-02",
        )

    def test_invalid_date_uses_fallback_date(self) -> None:
        self.assertEqual(parse_feed_date("not a date", "2026-06-04"), "2026-06-04")

    def test_dry_run_does_not_write_csv(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_sources(sources_path, [source_config()])

            with patch("industry_radar.source_adapters.read_url", return_value=RSS_XML.encode("utf-8")):
                result = fetch_and_import(
                    sources_path,
                    dry_run=True,
                    storage_path=storage_path,
                )

            self.assertEqual(result.fetched, 1)
            self.assertFalse(storage_path.exists())

    def test_fetch_reuses_dedupe_for_duplicate_source_url(self) -> None:
        duplicate_rss = """\
<rss>
  <channel>
    <item>
      <title>First</title>
      <link>https://example.com/duplicate</link>
      <description>First summary</description>
      <pubDate>Tue, 02 Jun 2026 17:30:00 GMT</pubDate>
    </item>
    <item>
      <title>Second</title>
      <link>https://example.com/duplicate</link>
      <description>Second summary</description>
      <pubDate>Tue, 02 Jun 2026 17:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            storage_path = Path(tmp_dir) / "industry_items.csv"
            write_sources(sources_path, [source_config()])

            with patch("industry_radar.source_adapters.read_url", return_value=duplicate_rss.encode("utf-8")):
                result = fetch_and_import(sources_path, storage_path=storage_path)

            self.assertEqual(result.fetched, 2)
            self.assertEqual(result.imported, 1)
            self.assertEqual(result.skipped_duplicates, 1)
            self.assertEqual(len(read_items(storage_path)), 1)

    def test_fetcher_handles_sources_with_type(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            write_sources(sources_path, [source_config(type="rss")])

            with patch("industry_radar.source_adapters.read_url", return_value=RSS_XML.encode("utf-8")):
                result = fetch_records(sources_path)

            self.assertEqual(result.fetched, 1)
            self.assertEqual(result.records[0]["title"], "OpenAI Agent update")

    def test_fetcher_supports_legacy_sources_without_type(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            write_sources(sources_path, [source_config()])

            with patch("industry_radar.source_adapters.read_url", return_value=RSS_XML.encode("utf-8")):
                result = fetch_records(sources_path)

            self.assertEqual(result.fetched, 1)
            self.assertEqual(result.failed, 0)

    def test_unknown_source_type_does_not_stop_other_sources(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            write_sources(
                sources_path,
                [
                    source_config(type="unknown", name="Unknown Source"),
                    source_config(type="rss", name="OpenAI Blog"),
                ],
            )

            with patch("industry_radar.source_adapters.read_url", return_value=RSS_XML.encode("utf-8")):
                result = fetch_records(sources_path)

            self.assertEqual(result.fetched, 1)
            self.assertEqual(result.failed, 1)
            self.assertIn("Unsupported source type", result.errors[0])

    def test_fetcher_handles_arxiv_source(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            write_sources(sources_path, [arxiv_source_config()])

            with patch(
                "industry_radar.source_adapters.read_url",
                return_value=ARXIV_XML.encode("utf-8"),
            ):
                result = fetch_records(sources_path)

            self.assertEqual(result.fetched, 1)
            self.assertEqual(result.records[0]["title"], "Agent Research")
            self.assertEqual(result.records[0]["source"], "arXiv AI Agent Research")

    def test_arxiv_source_failure_does_not_stop_rss_source(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sources_path = Path(tmp_dir) / "sources.json"
            write_sources(
                sources_path,
                [
                    arxiv_source_config(name="Broken arXiv"),
                    source_config(type="rss", name="OpenAI Blog"),
                ],
            )

            def fake_read_url(url: str) -> bytes:
                if "export.arxiv.org" in url:
                    raise RuntimeError("arxiv failed")
                return RSS_XML.encode("utf-8")

            with patch("industry_radar.source_adapters.read_url", fake_read_url):
                result = fetch_records(sources_path)

            self.assertEqual(result.fetched, 1)
            self.assertEqual(result.failed, 1)
            self.assertIn("arxiv failed", result.errors[0])

    def test_fetcher_handles_local_file_source(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            notes_path = Path(tmp_dir) / "notes.md"
            notes_path.write_text("# AI Agent Notes\nAgent body", encoding="utf-8")
            sources_path = Path(tmp_dir) / "sources.json"
            write_sources(sources_path, [local_file_source_config(path=str(notes_path))])

            result = fetch_records(sources_path)

        self.assertEqual(result.fetched, 1)
        self.assertEqual(result.records[0]["title"], "AI Agent Notes")

    def test_local_file_failure_does_not_stop_other_source(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            notes_path = Path(tmp_dir) / "notes.md"
            notes_path.write_text("# AI Agent Notes\nAgent body", encoding="utf-8")
            sources_path = Path(tmp_dir) / "sources.json"
            write_sources(
                sources_path,
                [
                    local_file_source_config(name="Missing Notes", path=str(Path(tmp_dir) / "missing.md")),
                    local_file_source_config(path=str(notes_path)),
                ],
            )

            result = fetch_records(sources_path)

        self.assertEqual(result.fetched, 1)
        self.assertEqual(result.failed, 1)
        self.assertIn("local file not found", result.errors[0])


if __name__ == "__main__":
    unittest.main()
