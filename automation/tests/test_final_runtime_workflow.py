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

    def test_recovered_coverage_has_sdk_before_editorial_repair(self) -> None:
        # Regression for 2026-11-16 run 43808498660: a completed prior audit
        # set text_api_needed=false, but Coverage then resumed Editorial Repair.
        workflow = (
            ROOT / ".github" / "workflows" / "daily-production.yml"
        ).read_text(encoding="utf-8")
        install = workflow.split(
            "      - name: Install pinned OpenAI SDK\n", 1
        )[1].split("      - name: Validate API configuration\n", 1)[0]
        self.assertIn(
            "if: steps.terminal_reuse.outputs.stop != 'true'\n", install
        )
        self.assertNotIn("steps.recovery.outputs", install)
        self.assertIn('openai==2.45.0', install)
        self.assertLess(
            workflow.index("- name: Install pinned OpenAI SDK"),
            workflow.index("- name: Complete mandatory coverage audit for a short digest"),
        )
        self.assertIn("recovery_mode == \"full\"", workflow)
        self.assertIn("completed_prior_audit", workflow)
        self.assertIn(
            "text_api_needed = not (full_story_target or prior_complete)",
            workflow,
        )
        # The API-configuration gate remains separate from SDK installation.
        self.assertIn("steps.recovery.outputs.openai_needed == 'true'", workflow)


if __name__ == "__main__":
    unittest.main()
