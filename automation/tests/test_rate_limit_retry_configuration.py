from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RateLimitRetryConfigurationTests(unittest.TestCase):
    def test_text_api_clients_retry_transient_rate_limits(self) -> None:
        generator = (
            ROOT / "automation/scripts/generate_digest_preview.py"
        ).read_text(encoding="utf-8")
        coverage = (
            ROOT / "automation/scripts/ensure_story_coverage.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("max_retries=0", generator)
        self.assertNotIn('"max_retries": 0', generator)
        self.assertIn("max_retries=2", generator)
        self.assertEqual(generator.count('"max_retries": 2'), 2)
        self.assertNotIn("max_retries=0", coverage)
        self.assertIn("max_retries=2", coverage)
        self.assertIn(
            "max_tool_calls=args.maximum_research_web_search_calls",
            generator,
        )
        self.assertIn("maximum_web_search_calls=1", (
            ROOT / "automation/scripts/ensure_story_coverage_policy.py"
        ).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
