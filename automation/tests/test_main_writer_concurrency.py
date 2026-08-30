from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
SHARED_GROUP = "daily-production-main"


class MainWriterConcurrencyTests(unittest.TestCase):
    def test_production_and_cleanup_share_non_cancelling_mutex(self) -> None:
        writers = (
            WORKFLOW_ROOT / "daily-production.yml",
            WORKFLOW_ROOT / "repository-cleanup.yml",
        )
        expected = f"group: {SHARED_GROUP}\n  cancel-in-progress: false"
        for path in writers:
            text = path.read_text(encoding="utf-8")
            self.assertIn("concurrency:\n", text, path.name)
            self.assertIn(expected, text, path.name)

    def test_cleanup_still_runs_before_production_without_changing_crons(self) -> None:
        cleanup = (WORKFLOW_ROOT / "repository-cleanup.yml").read_text(encoding="utf-8")
        production = (WORKFLOW_ROOT / "daily-production.yml").read_text(encoding="utf-8")
        self.assertIn('- cron: "43 22 * * *"', cleanup)
        self.assertIn('- cron: "17 23 * * *"', production)


if __name__ == "__main__":
    unittest.main()
