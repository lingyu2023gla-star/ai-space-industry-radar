import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from industry_radar.config import (
    PIPELINE_DEFAULTS,
    load_json_config,
    merge_pipeline_config,
    validate_pipeline_config,
)


class ConfigTest(unittest.TestCase):
    def test_load_json_config_reads_valid_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "pipeline.json"
            path.write_text('{"limit": 3}', encoding="utf-8")

            self.assertEqual(load_json_config(str(path)), {"limit": 3})

    def test_load_json_config_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_json_config("missing.json")

    def test_load_json_config_invalid_json_raises(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "pipeline.json"
            path.write_text("{bad json", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_json_config(str(path))

    def test_load_json_config_top_level_must_be_object(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "pipeline.json"
            path.write_text("[1, 2]", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_json_config(str(path))

    def test_validate_pipeline_config_rejects_unknown_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown pipeline config key: apply"):
            validate_pipeline_config({"apply": True})

    def test_validate_pipeline_config_normalizes_industry(self) -> None:
        result = validate_pipeline_config({"industry": "space"})

        self.assertEqual(result["industry"], "Commercial Space")

    def test_validate_pipeline_config_validates_dates(self) -> None:
        result = validate_pipeline_config({"since": "2026-06-01", "until": "2026-06-03"})

        self.assertEqual(result["since"], "2026-06-01")
        self.assertEqual(result["until"], "2026-06-03")

    def test_validate_pipeline_config_rejects_non_positive_limit(self) -> None:
        with self.assertRaises(ValueError):
            validate_pipeline_config({"limit": 0})

    def test_validate_pipeline_config_rejects_non_positive_top(self) -> None:
        with self.assertRaises(ValueError):
            validate_pipeline_config({"top": 0})

    def test_validate_pipeline_config_rejects_non_bool_enrich(self) -> None:
        with self.assertRaises(ValueError):
            validate_pipeline_config({"enrich": "true"})

    def test_merge_pipeline_config_precedence(self) -> None:
        result = merge_pipeline_config(
            {"limit": 5, "industry": None},
            {"limit": 3, "industry": "AI"},
            {"limit": 10},
        )

        self.assertEqual(result["limit"], 10)
        self.assertEqual(result["industry"], "AI")

    def test_merge_pipeline_config_cli_none_does_not_override(self) -> None:
        result = merge_pipeline_config(
            PIPELINE_DEFAULTS,
            {"industry": "AI", "top": 5},
            {"industry": None, "top": None},
        )

        self.assertEqual(result["industry"], "AI")
        self.assertEqual(result["top"], 5)

    def test_merge_pipeline_config_cli_enrich_overrides_config(self) -> None:
        result = merge_pipeline_config(
            PIPELINE_DEFAULTS,
            {"enrich": False},
            {"enrich": True},
        )

        self.assertTrue(result["enrich"])


if __name__ == "__main__":
    unittest.main()
