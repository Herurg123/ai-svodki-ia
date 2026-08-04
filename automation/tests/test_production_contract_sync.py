from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CRONS = ["17 23 * * *", "37 23 * * *", "57 23 * * *"]

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
        self.assertEqual(production["minimum_publishable_stories"], 1)
        self.assertFalse(production["regional_story_quotas_enabled"])
        self.assertFalse(
            production["coverage_audit_failure_blocks_publication"]
        )
        self.assertTrue(production["coverage_audit_enabled"])
        self.assertEqual(production["coverage_audit_max_web_search_calls"], 5)
        self.assertEqual(
            production["minimum_legacy_items"],
            0,
            "32-day retention must be allowed to remove every legacy item",
        )
        # Seven is the ordinary-volume boundary; one worthy story is enough
        # to publish and regional sections never have numeric quotas.
        self.assertEqual(editorial["story_counts"]["total_target_minimum"], 7)
        self.assertEqual(editorial["story_counts"]["short_digest_minimum"], 1)
        self.assertFalse(
            editorial["story_counts"]["regional_story_quotas_enabled"]
        )
        self.assertTrue(editorial["article"]["allow_missing_china_section"])
        self.assertTrue(editorial["article"]["allow_missing_russian_section"])
        self.assertEqual(workflow.count("cron:"), 3)
        for cron in EXPECTED_CRONS:
            self.assertEqual(workflow.count(f'cron: "{cron}"'), 1)
        self.assertIn("Supplement a short digest when possible", workflow)
        self.assertIn(
            "Validate publishable story count and short digest marker",
            workflow,
        )
        self.assertIn("--usual-total 7", workflow)
        self.assertIn("--minimum-publishable 1", workflow)
        self.assertNotIn("--minimum-world", workflow)
        self.assertNotIn("--minimum-russia", workflow)
        self.assertNotIn("--minimum-russian-candidates", workflow)
        self.assertIn("--maximum-audit-web-search-calls 5", workflow)
        self.assertIn(
            "Reuse completed editorial stop without paid APIs", workflow
        )
        self.assertIn('echo "stop=${stop}" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn(
            "steps.terminal_reuse.outputs.stop != 'true'", workflow
        )
        self.assertIn("needs.production.outputs.commit_sha != ''", workflow)
        self.assertIn("if: steps.recovery.outputs.reused != 'true'", workflow)
        self.assertIn("/actions/runs/${candidate_run_id}/jobs?per_page=100", workflow)
        self.assertIn('echo "reused=false" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn(r'stream.write("reused=true\n")', workflow)
        self.assertIn(r'+ "\n"', workflow)
        self.assertIn("candidate_pool_after", workflow)
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
                payload["schedule_local"],
                [
                    "02:17 Europe/Moscow",
                    "02:37 Europe/Moscow",
                    "02:57 Europe/Moscow",
                ],
            )
            self.assertEqual(
                payload["story_coverage_contract"],
                {
                    "usual_total": 7,
                    "minimum_publishable": 1,
                    "regional_story_quotas_enabled": False,
                    "audit_failure_blocks_publication": False,
                    "audit_max_web_search_calls": 5,
                },
            )

if __name__ == "__main__":
    unittest.main()
