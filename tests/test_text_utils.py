import unittest

from industry_radar.text_utils import clean_text, truncate_text


class TextUtilsTest(unittest.TestCase):
    def test_clean_text_removes_html_tags(self) -> None:
        self.assertEqual(clean_text("<p>Hello<br>World</p>"), "Hello World")

    def test_clean_text_unescapes_html_entities(self) -> None:
        self.assertEqual(clean_text("AI &amp; Space"), "AI & Space")

    def test_clean_text_compresses_whitespace(self) -> None:
        self.assertEqual(clean_text(" A   B\n\tC "), "A B C")

    def test_truncate_text_appends_ellipsis_when_too_long(self) -> None:
        self.assertEqual(truncate_text("abcdef", 3), "abc...")

    def test_truncate_text_non_positive_max_length_returns_empty(self) -> None:
        self.assertEqual(truncate_text("abcdef", 0), "")
        self.assertEqual(truncate_text("abcdef", -1), "")


if __name__ == "__main__":
    unittest.main()
