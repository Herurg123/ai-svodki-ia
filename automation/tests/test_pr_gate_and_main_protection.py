from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
RULESET = ROOT / "automation" / "config" / "main-branch-ruleset.json"
PUSH_HELPER = ROOT / "automation" / "scripts" / "push_protected_main.sh"


class PrGateAndMainProtectionTests(unittest.TestCase):
    def test_pr_gate_always_exists_for_pull_requests(self) -> None:
        gate = (WORKFLOW_ROOT / "pr-gate.yml").read_text(encoding="utf-8")
        self.assertIn("name: PR Gate", gate)
        self.assertIn("pull_request:", gate)
        self.assertIn("name: Required PR Gate", gate)
        self.assertIn("uses: ./.github/workflows/ci.yml", gate)
        self.assertIn("uses: ./.github/workflows/video-ci.yml", gate)
        self.assertIn('path == ".github/workflows/pr-gate.yml"', gate)
        self.assertIn('path.startswith("automation/notebooklm-video/")', gate)
        self.assertNotIn("OPENAI_API_KEY", gate)
        self.assertNotIn("contents: write", gate)

    def test_domain_ci_workflows_are_reusable_and_not_direct_pr_triggers(self) -> None:
        main = (WORKFLOW_ROOT / "ci.yml").read_text(encoding="utf-8")
        video = (WORKFLOW_ROOT / "video-ci.yml").read_text(encoding="utf-8")
        for text in (main, video):
            self.assertIn("workflow_call:", text)
            self.assertNotIn("  pull_request:\n", text)
        self.assertIn('!automation/notebooklm-video/**', main)
        self.assertIn('!.github/workflows/video-ci.yml', main)
        self.assertIn('automation/notebooklm-video/**', video)

    def test_only_approved_workflows_receive_main_push_secret(self) -> None:
        writers = {
            path.name
            for path in WORKFLOW_ROOT.glob("*.yml")
            if "MAIN_PUSH_DEPLOY_KEY" in path.read_text(encoding="utf-8")
        }
        self.assertEqual(writers, {"daily-production.yml", "repository-cleanup.yml"})

        for name in writers:
            text = (WORKFLOW_ROOT / name).read_text(encoding="utf-8")
            self.assertIn("automation/scripts/push_protected_main.sh HEAD:main", text)

    def test_push_helper_is_narrow_and_pins_github_host_key(self) -> None:
        helper = PUSH_HELPER.read_text(encoding="utf-8")
        self.assertIn('refspec="${1:-HEAD:main}"', helper)
        self.assertIn('"${refspec}" != "HEAD:main"', helper)
        self.assertIn("MAIN_PUSH_DEPLOY_KEY", helper)
        self.assertIn(
            "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl",
            helper,
        )
        self.assertIn("StrictHostKeyChecking=yes", helper)
        self.assertIn('git push "git@github.com:${repository}.git" "${refspec}"', helper)
        self.assertIn('git push origin "${refspec}"', helper)

    def test_ruleset_targets_only_main_with_one_required_gate(self) -> None:
        data = json.loads(RULESET.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "Protect main")
        self.assertEqual(data["target"], "branch")
        self.assertEqual(data["enforcement"], "active")
        self.assertEqual(data["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(data["conditions"]["ref_name"]["exclude"], [])
        self.assertEqual(
            data["bypass_actors"],
            [{"actor_id": None, "actor_type": "DeployKey", "bypass_mode": "always"}],
        )

        rules = {rule["type"]: rule for rule in data["rules"]}
        self.assertTrue({"deletion", "non_fast_forward", "required_linear_history"} <= rules.keys())

        pr = rules["pull_request"]["parameters"]
        self.assertEqual(pr["required_approving_review_count"], 0)
        self.assertTrue(pr["required_review_thread_resolution"])
        self.assertEqual(pr["allowed_merge_methods"], ["squash", "rebase"])

        checks = rules["required_status_checks"]["parameters"]
        self.assertTrue(checks["strict_required_status_checks_policy"])
        self.assertFalse(checks["do_not_enforce_on_create"])
        self.assertEqual(checks["required_status_checks"], [{"context": "Required PR Gate"}])


if __name__ == "__main__":
    unittest.main()
