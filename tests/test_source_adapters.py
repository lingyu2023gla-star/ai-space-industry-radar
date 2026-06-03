import unittest
from unittest.mock import patch

from industry_radar.source_adapters import (
    RSSSourceAdapter,
    get_source_adapter,
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
