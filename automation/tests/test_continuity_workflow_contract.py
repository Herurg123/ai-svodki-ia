
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ContinuityWorkflowContractTests(unittest.TestCase):
    def test_config_allows_skipped_days(self) -> None:
        config = json.loads(
            (
                ROOT / "automation/config/production-daily.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(config["require_previous_day_in_rss"])
        self.assertTrue(config["allow_skipped_publication_days"])
        self.assertTrue(
            config["verify_previous_release_on_live_site"]
        )

    def test_workflow_has_continuity_and_russian_status(self) -> None:
        workflow = (
            ROOT / ".github/workflows/daily-production.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("verify_previous_release.py", workflow)
        self.assertIn(
            "validate_search_window_continuity.py",
            workflow,
        )
        self.assertIn("summarize_production_status.py", workflow)
        self.assertIn("Publish Russian pipeline status", workflow)
        self.assertIn("Итог публикации", workflow)

        continuity = workflow.index(
            "Verify search window starts at last successful release"
        )
        research = workflow.index(
            "Run full research and editorial"
        )
        self.assertLess(continuity, research)


if __name__ == "__main__":
    unittest.main()
