import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from industry_radar.source_adapters import (
    ArxivSourceAdapter,
    RSSSourceAdapter,
    build_arxiv_api_url,
    get_source_adapter,
    parse_arxiv_atom,
    parse_feed_xml,
    validate_source_config,
)


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
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>https://arxiv.org/abs/2606.00001</id>
    <updated>2026-06-03T08:00:00Z</updated>
    <published>2026-06-02T17:30:00Z</published>
    <title>Agent Research &amp; Evaluation</title>
    <summary>
      <p>This paper studies AI agents and product workflows.</p>
    </summary>
    <author>
      <name>Alice Example</name>
    </author>
    <category term="cs.AI" />
    <category term="cs.CL" />
    <arxiv:primary_category term="cs.AI" />
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
        "sort_by": "submittedDate",
        "sort_order": "descending",
    }
    source.update(overrides)
    return source


class SourceAdaptersTest(unittest.TestCase):
    def test_get_source_adapter_rss(self) -> None:
        self.assertIsInstance(get_source_adapter("rss"), RSSSourceAdapter)

    def test_get_source_adapter_is_case_insensitive(self) -> None:
        self.assertIsInstance(get_source_adapter("RSS"), RSSSourceAdapter)

    def test_get_source_adapter_defaults_to_rss(self) -> None:
        self.assertIsInstance(get_source_adapter(None), RSSSourceAdapter)

    def test_get_source_adapter_unknown_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            get_source_adapter("unknown")

    def test_get_source_adapter_arxiv(self) -> None:
        self.assertIsInstance(get_source_adapter("arxiv"), ArxivSourceAdapter)

    def test_validate_source_config_defaults_type_to_rss(self) -> None:
        source = validate_source_config(source_config())

        self.assertEqual(source["type"], "rss")

    def test_validate_source_config_normalizes_industry(self) -> None:
        source = validate_source_config(source_config(industry="商业航天"))

        self.assertEqual(source["industry"], "Commercial Space")

    def test_validate_source_config_normalizes_default_tags(self) -> None:
        source = validate_source_config(source_config(default_tags=" AI ; RAG；Product "))

        self.assertEqual(source["default_tags"], "AI;RAG;Product")

    def test_validate_source_config_missing_name_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            validate_source_config(source_config(name=""))

    def test_validate_source_config_rss_missing_url_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            validate_source_config(source_config(url=""))

    def test_validate_source_config_accepts_arxiv_query_config(self) -> None:
        source = validate_source_config(arxiv_source_config())

        self.assertEqual(source["type"], "arxiv")
        self.assertEqual(source["query"], "cat:cs.AI AND all:agent")
        self.assertEqual(source["sort_by"], "submittedDate")
        self.assertEqual(source["sort_order"], "descending")

    def test_validate_source_config_accepts_arxiv_category_config(self) -> None:
        source = validate_source_config(
            arxiv_source_config(query="", arxiv_category="cs.AI")
        )

        self.assertEqual(source["arxiv_category"], "cs.AI")

    def test_validate_source_config_arxiv_missing_query_and_category_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_source_config(arxiv_source_config(query="", arxiv_category=""))

    def test_validate_source_config_arxiv_invalid_sort_by_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_source_config(arxiv_source_config(sort_by="newest"))

    def test_validate_source_config_arxiv_invalid_sort_order_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_source_config(arxiv_source_config(sort_order="latest"))

    def test_build_arxiv_api_url_includes_expected_params(self) -> None:
        url = build_arxiv_api_url(validate_source_config(arxiv_source_config()), limit=5)
        params = parse_qs(urlparse(url).query)

        self.assertEqual(params["search_query"], ["cat:cs.AI AND all:agent"])
        self.assertEqual(params["max_results"], ["5"])
        self.assertEqual(params["sortBy"], ["submittedDate"])
        self.assertEqual(params["sortOrder"], ["descending"])

    def test_build_arxiv_api_url_encodes_query(self) -> None:
        url = build_arxiv_api_url(
            validate_source_config(arxiv_source_config(query='cat:cs.AI AND all:"agent workflow"')),
            limit=3,
        )

        self.assertIn("search_query=cat%3Acs.AI+AND+all%3A%22agent+workflow%22", url)

    def test_parse_arxiv_atom_parses_basic_atom_xml(self) -> None:
        records = parse_arxiv_atom(ARXIV_XML, validate_source_config(arxiv_source_config()))

        self.assertEqual(len(records), 1)

    def test_parse_arxiv_atom_extracts_core_fields(self) -> None:
        record = parse_arxiv_atom(ARXIV_XML, validate_source_config(arxiv_source_config()))[0]

        self.assertEqual(record["title"], "Agent Research & Evaluation")
        self.assertEqual(record["source_url"], "https://arxiv.org/abs/2606.00001")
        self.assertEqual(record["summary"], "This paper studies AI agents and product workflows.")

    def test_parse_arxiv_atom_converts_published_to_date(self) -> None:
        record = parse_arxiv_atom(ARXIV_XML, validate_source_config(arxiv_source_config()))[0]

        self.assertEqual(record["date"], "2026-06-02")

    def test_parse_arxiv_atom_merges_default_tags_and_category_terms(self) -> None:
        record = parse_arxiv_atom(ARXIV_XML, validate_source_config(arxiv_source_config()))[0]

        self.assertEqual(record["tags"], "AI;Research;arXiv;Agent;cs.AI;cs.CL")

    def test_arxiv_source_adapter_fetch_uses_mocked_network(self) -> None:
        with patch(
            "industry_radar.source_adapters.read_url",
            return_value=ARXIV_XML.encode("utf-8"),
        ):
            records = ArxivSourceAdapter().fetch(
                validate_source_config(arxiv_source_config()),
                limit=2,
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source"], "arXiv AI Agent Research")

    def test_rss_source_adapter_parses_basic_rss_xml(self) -> None:
        with patch(
            "industry_radar.source_adapters.read_url",
            return_value=RSS_XML.encode("utf-8"),
        ):
            records = RSSSourceAdapter().fetch(validate_source_config(source_config()))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "OpenAI Agent update")
        self.assertEqual(records[0]["source_url"], "https://example.com/openai-agent")

    def test_rss_source_adapter_parses_basic_atom_xml(self) -> None:
        with patch(
            "industry_radar.source_adapters.read_url",
            return_value=ATOM_XML.encode("utf-8"),
        ):
            records = RSSSourceAdapter().fetch(
                validate_source_config(
                    source_config(name="Space News", industry="Commercial Space")
                )
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "Space launch update")
        self.assertEqual(records[0]["industry"], "Commercial Space")

    def test_rss_source_adapter_outputs_complete_candidate_dict(self) -> None:
        with patch(
            "industry_radar.source_adapters.read_url",
            return_value=RSS_XML.encode("utf-8"),
        ):
            record = RSSSourceAdapter().fetch(validate_source_config(source_config()))[0]

        self.assertEqual(
            set(record.keys()),
            {
                "date",
                "industry",
                "category",
                "company",
                "title",
                "source",
                "source_url",
                "summary",
                "signal",
                "tags",
                "importance",
            },
        )
        self.assertEqual(record["source"], "OpenAI Blog")
        self.assertEqual(record["company"], "OpenAI Blog")
        self.assertEqual(record["importance"], 3)

    def test_parse_feed_xml_still_parses_rss_directly(self) -> None:
        self.assertEqual(parse_feed_xml(RSS_XML)[0]["title"], "OpenAI Agent update")


if __name__ == "__main__":
    unittest.main()
