"""Offline retirement contract: Sol must not run as part of daily production.

Do not import the archived Sol scripts or call any provider API here.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-production.yml"
GENERATOR = ROOT / "automation" / "scripts" / "generate_digest_preview.py"
ARCHIVE = ROOT / "automation" / "audits" / "experiments" / "2026-10-29-sol61-editorial-shadow"


class RetiredSolExperimentTests(unittest.TestCase):
    def test_no_sol_job_or_expensive_shadow_call_in_daily_workflow(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for forbidden in (
            "sol61_editorial_shadow:",
            "sol61_full_editorial_shadow.py",
            "sol61_editorial_shadow_once.py",
            "SOL_EDITORIAL_AUDIT_ENABLED",
            "sol61-independent-editorial-",
        ):
            self.assertNotIn(forbidden, workflow)
        self.assertEqual(workflow.count('cron: "17 23 * * *"'), 1)
        self.assertIn("needs.production.result == 'success'", workflow)

    def test_terra_text_model_and_publishing_contract_unchanged(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("vars.OPENAI_TEXT_MODEL || 'gpt-5.6-terra'", workflow)
        self.assertIn('[[ "${OPENAI_TEXT_MODEL}" == "gpt-5.6-terra" ]]', workflow)
        self.assertIn("Run full research and editorial", workflow)
        self.assertIn("Complete mandatory coverage audit for a short digest", workflow)
        self.assertIn("Deploy published posts", workflow)

    def test_no_passive_sol_input_capture_on_production_path(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertNotIn("editorial-input-snapshots", text)
        self.assertNotIn("Optional shadow evidence", text)
        self.assertIn('output_dir / "editorial-prompt-input.txt"', text)
        self.assertIn('call_with_usage("editorial", client.responses.create,', text)

    def test_historical_experiment_evidence_stays_accessible(self):
        self.assertTrue((ARCHIVE / "PLAN.md").is_file())
        self.assertTrue((ARCHIVE / "RESULTS_AND_RESTART.md").is_file())
        self.assertTrue((ARCHIVE / "evidence-index.json").is_file())
        self.assertTrue((ARCHIVE / "archived-tests" / "test_sol61_editorial_shadow_once.py").is_file())
        self.assertTrue((ARCHIVE / "archived-tests" / "test_sol61_full_editorial_shadow.py").is_file())
        self.assertTrue((ROOT / "automation" / "scripts" / "sol61_full_editorial_shadow.py").is_file())
        self.assertTrue((ROOT / "automation" / "scripts" / "sol61_editorial_shadow_once.py").is_file())


if __name__ == "__main__":
    unittest.main()
