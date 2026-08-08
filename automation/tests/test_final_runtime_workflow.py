from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FinalRuntimeWorkflowTests(unittest.TestCase):
    def test_site_policy_consumers_use_wrappers(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "daily-production.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("run_build_site.py", workflow)
        self.assertIn("run_validate_site.py", workflow)
        self.assertNotIn("python automation/scripts/build_site.py", workflow)
        self.assertNotIn("python automation/scripts/validate_site.py", workflow)

    def test_recovered_image_skips_paid_image_api(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "daily-production.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            workflow.count("steps.recovery.outputs.image_recovered != 'true'"),
            2,
        )
        self.assertEqual(
            workflow.count("steps.recovery.outputs.image_recovered == 'true'"),
            1,
        )
        self.assertIn("--image-target-dir", workflow)

    def test_complete_recovery_can_skip_openai_setup(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "daily-production.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("openai_needed", workflow)
        self.assertEqual(
            workflow.count("steps.recovery.outputs.openai_needed == 'true'"),
            2,
        )
        self.assertIn("recovery_mode == \"full\"", workflow)
        self.assertIn("completed_prior_audit", workflow)


if __name__ == "__main__":
    unittest.main()
