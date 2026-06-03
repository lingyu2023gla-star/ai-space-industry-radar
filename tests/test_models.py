import unittest

from industry_radar.models import (
    clean_prompt_value,
    normalize_importance,
    normalize_industry,
    normalize_tags,
    validate_date,
)


class CleanPromptValueTest(unittest.TestCase):
    def test_clean_prompt_value_with_simple_label(self) -> None:
        self.assertEqual(clean_prompt_value("Category: Agent"), "Agent")

    def test_clean_prompt_value_with_label_hint(self) -> None:
        self.assertEqual(
            clean_prompt_value("Industry [AI/Commercial Space]: AI"),
            "AI",
        )

    def test_clean_prompt_value_with_importance_label(self) -> None:
        self.assertEqual(clean_prompt_value("Importance [1-5]: 5"), "5")

    def test_clean_prompt_value_without_label(self) -> None:
        self.assertEqual(clean_prompt_value("AI"), "AI")

    def test_clean_prompt_value_strips_whitespace(self) -> None:
        self.assertEqual(clean_prompt_value(" 商业航天 "), "商业航天")

    def test_clean_prompt_value_empty_input(self) -> None:
        self.assertEqual(clean_prompt_value(None), "")
        self.assertEqual(clean_prompt_value(""), "")


class NormalizeIndustryTest(unittest.TestCase):
    def test_normalize_industry_ai_lowercase(self) -> None:
        self.assertEqual(normalize_industry("ai"), "AI")

    def test_normalize_industry_ai_chinese(self) -> None:
        self.assertEqual(normalize_industry("人工智能"), "AI")

    def test_normalize_industry_llm(self) -> None:
        self.assertEqual(normalize_industry("LLM"), "AI")

    def test_normalize_industry_commercial_space_chinese(self) -> None:
        self.assertEqual(normalize_industry("商业航天"), "Commercial Space")

    def test_normalize_industry_space_alias(self) -> None:
        self.assertEqual(normalize_industry("space"), "Commercial Space")

    def test_normalize_industry_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            normalize_industry("finance")


class NormalizeImportanceTest(unittest.TestCase):
    def test_normalize_importance_plain_value(self) -> None:
        self.assertEqual(normalize_importance("5"), 5)

    def test_normalize_importance_with_label(self) -> None:
        self.assertEqual(normalize_importance("Importance [1-5]: 5"), 5)

    def test_normalize_importance_out_of_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            normalize_importance("6")


class NormalizeTagsTest(unittest.TestCase):
    def test_normalize_tags_plain_values(self) -> None:
        self.assertEqual(normalize_tags("Agent;RAG"), "Agent;RAG")

    def test_normalize_tags_strips_and_normalizes_separator(self) -> None:
        self.assertEqual(
            normalize_tags(" Agent ; RAG；Product "),
            "Agent;RAG;Product",
        )

    def test_normalize_tags_empty_input(self) -> None:
        self.assertEqual(normalize_tags(""), "")


class ValidateDateTest(unittest.TestCase):
    def test_validate_date_valid_value(self) -> None:
        self.assertEqual(validate_date("2026-06-02"), "2026-06-02")

    def test_validate_date_invalid_calendar_date_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_date("2026-99-99")

    def test_validate_date_invalid_format_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_date("06-02-2026")


if __name__ == "__main__":
    unittest.main()
