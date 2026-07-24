from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CRONS = ["17 3 * * *", "37 3 * * *", "57 3 * * *"]


class ProductionContractSyncTests(unittest.TestCase):
    def test_config_workflow_and_editorial_thresholds_are_synchronized(self) -> None:
        production = json.loads(
            (ROOT / "automation/config/production-daily.json").read_text(
                encoding="utf-8"
            )
        )
        editorial = json.loads(
            (ROOT / "automation/config/editorial.json").read_text(encoding="utf-8")
        )
        workflow = (
            ROOT / ".github/workflows/daily-production.yml"
        ).read_text(encoding="utf-8")

        self.assertEqual(production["schedule_crons_utc"], EXPECTED_CRONS)
        self.assertEqual(production["schedule_cron_utc"], EXPECTED_CRONS[0])
        self.assertEqual(production["minimum_selected_stories"], 7)
        self.assertEqual(production["minimum_world_selected_stories"], 5)
        self.assertEqual(production["minimum_russian_selected_stories"], 2)
        self.assertTrue(production["coverage_audit_enabled"])
        self.assertEqual(production["coverage_audit_max_web_search_calls"], 5)

        # Six remains the legacy editorial "short digest" boundary. Production
        # publication is independently and strictly gated at 7 = 5 world + 2 Russia.
        self.assertEqual(editorial["story_counts"]["total_target_minimum"], 6)
        self.assertEqual(editorial["story_counts"]["world_target_minimum"], 5)
        self.assertEqual(editorial["story_counts"]["russian_target_minimum"], 2)

        self.assertEqual(workflow.count("cron:"), 3)
        for cron in EXPECTED_CRONS:
            self.assertEqual(workflow.count(f'cron: "{cron}"'), 1)
        self.assertIn("Enforce 5 world plus 2 Russian stories", workflow)
        self.assertIn("Validate final story coverage", workflow)
        self.assertIn("--minimum-total 7", workflow)
        self.assertIn("--minimum-world 5", workflow)
        self.assertIn("--minimum-russia 2", workflow)
        self.assertIn("--maximum-audit-web-search-calls 5", workflow)

    def test_same_contract_validator_used_by_ci_accepts_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "production-contract.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "automation/scripts/validate_production_daily_contract.py"
                    ),
                    "--config",
                    str(ROOT / "automation/config/production-daily.json"),
                    "--site-config",
                    str(ROOT / "automation/config/site.json"),
                    "--workflow",
                    str(ROOT / ".github/workflows/daily-production.yml"),
                    "--rss",
                    str(ROOT / "posts/rss.xml"),
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            diagnostics = (
                f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
            )
            self.assertEqual(completed.returncode, 0, diagnostics)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["schedule_utc"], EXPECTED_CRONS)
            self.assertEqual(
                payload["story_coverage_contract"],
                {
                    "minimum_total": 7,
                    "minimum_world": 5,
                    "minimum_russia": 2,
                    "audit_max_web_search_calls": 5,
                },
            )


if __name__ == "__main__":
    unittest.main()
