import unittest
from copy import deepcopy

from industry_radar.source_policy import filter_sources_by_health, should_skip_source


class SourcePolicyTest(unittest.TestCase):
    def test_should_skip_source_unknown_does_not_skip(self) -> None:
        skip, reason = should_skip_source("JPL News", {})

        self.assertFalse(skip)
        self.assertEqual(reason, "no health history")

    def test_should_skip_source_insufficient_history_does_not_skip(self) -> None:
        health = {"JPL News": {"runs_seen": 2, "failure_rate": 1.0}}

        skip, reason = should_skip_source("JPL News", health, min_runs=3)

        self.assertFalse(skip)
        self.assertEqual(reason, "insufficient history")

    def test_should_skip_source_threshold_or_above_skips(self) -> None:
        health = {"JPL News": {"runs_seen": 3, "failure_rate": 0.8}}

        skip, reason = should_skip_source("JPL News", health, failure_rate_threshold=0.8)

        self.assertTrue(skip)
        self.assertIn("failure_rate 80.0% >= threshold 80.0%", reason)

    def test_should_skip_source_below_threshold_does_not_skip(self) -> None:
        health = {"JPL News": {"runs_seen": 3, "failure_rate": 0.5}}

        skip, reason = should_skip_source("JPL News", health, failure_rate_threshold=0.8)

        self.assertFalse(skip)
        self.assertEqual(reason, "healthy enough")

    def test_should_skip_source_rejects_invalid_threshold(self) -> None:
        with self.assertRaises(ValueError):
            should_skip_source("JPL News", {}, failure_rate_threshold=1.1)

    def test_should_skip_source_rejects_invalid_min_runs(self) -> None:
        with self.assertRaises(ValueError):
            should_skip_source("JPL News", {}, min_runs=0)

    def test_filter_sources_by_health_returns_active_and_skipped_sources(self) -> None:
        sources = [{"name": "JPL News"}, {"name": "arXiv cs.AI"}]
        health = {
            "JPL News": {"runs_seen": 3, "failure_rate": 1.0},
            "arXiv cs.AI": {"runs_seen": 3, "failure_rate": 0.0},
        }

        active, skipped = filter_sources_by_health(sources, health)

        self.assertEqual([source["name"] for source in active], ["arXiv cs.AI"])
        self.assertEqual(skipped[0]["name"], "JPL News")

    def test_filter_sources_by_health_does_not_modify_original_sources(self) -> None:
        sources = [{"name": "JPL News", "meta": {"x": 1}}]
        original = deepcopy(sources)

        active, _skipped = filter_sources_by_health(sources, {})
        active[0]["meta"]["x"] = 2

        self.assertEqual(sources, original)


if __name__ == "__main__":
    unittest.main()
