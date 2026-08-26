from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
RULESET = ROOT / "automation" / "config" / "main-branch-ruleset.json"
PUSH_HELPER = ROOT / "automation" / "scripts" / "push_protected_main.sh"


class PrGateAndMainProtectionTests(unittest.TestCase):
    @staticmethod
    def _route_script() -> str:
        gate = (WORKFLOW_ROOT / "pr-gate.yml").read_text(encoding="utf-8")
        step = "      - name: Route changed paths to CI domains\n"
        step_start = gate.index(step)
        run_marker = "        run: |\n"
        run_start = gate.index(run_marker, step_start) + len(run_marker)
        run_end = gate.index("\n\n  main-ci:", run_start)
        return textwrap.dedent(gate[run_start:run_end])

    def _run_route_for_paths(self, changed_paths: list[str]) -> tuple[dict[str, str], str]:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "PR Gate test"], cwd=repo, check=True)

            (repo / "seed.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

            for relative in changed_paths:
                target = repo / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("changed\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "head"], cwd=repo, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

            github_output = repo / "github-output.txt"
            env = os.environ.copy()
            env.update(
                BASE_SHA=base,
                HEAD_SHA=head,
                GITHUB_OUTPUT=str(github_output),
            )
            completed = subprocess.run(
                ["bash", "-c", self._route_script()],
                cwd=repo,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            outputs = dict(
                line.split("=", 1)
                for line in github_output.read_text(encoding="utf-8").splitlines()
                if line
            )
            return outputs, completed.stdout

    def test_pr_gate_always_exists_for_pull_requests(self) -> None:
        gate = (WORKFLOW_ROOT / "pr-gate.yml").read_text(encoding="utf-8")
        self.assertIn("name: PR Gate", gate)
        self.assertIn("pull_request:", gate)
        self.assertIn("name: Required PR Gate", gate)
        self.assertIn("uses: ./.github/workflows/ci.yml", gate)
        self.assertIn("uses: ./.github/workflows/video-ci.yml", gate)
        self.assertIn('path == ".github/workflows/pr-gate.yml"', gate)
        self.assertIn('path.startswith("automation/notebooklm-video/")', gate)
        self.assertIn('["git", "diff", "--name-only", "-z", "--diff-filter=ACMRD", base, head]', gate)
        self.assertIn('raw.split(b"\\0")', gate)
        self.assertIn("os.fsdecode(path)", gate)
        self.assertIn("if not changed:", gate)
        self.assertIn("every path that is not proven video-only belongs to Main CI", gate)
        self.assertNotIn("OPENAI_API_KEY", gate)
        self.assertNotIn("contents: write", gate)

    def test_unicode_video_only_path_routes_only_video_ci(self) -> None:
        outputs, stdout = self._run_route_for_paths(
            ["automation/notebooklm-video/НАСТРОЙКИ.txt"]
        )
        self.assertEqual(outputs, {"main": "false", "video": "true"})
        self.assertIn("automation/notebooklm-video/НАСТРОЙКИ.txt", stdout)

    def test_unknown_path_still_routes_fail_safe_to_main_ci(self) -> None:
        outputs, _ = self._run_route_for_paths(["unexpected/new-file.txt"])
        self.assertEqual(outputs, {"main": "true", "video": "false"})

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
        self.assertEqual(
            writers,
            {
                "daily-production.yml",
                "repository-cleanup.yml",
                "video-rss-enrichment.yml",
            },
        )

        for path in WORKFLOW_ROOT.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("git push origin HEAD:main", text)
            if path.name in writers:
                self.assertEqual(
                    text.count("automation/scripts/push_protected_main.sh HEAD:main"), 1
                )
                self.assertEqual(
                    text.count("MAIN_PUSH_DEPLOY_KEY: ${{ secrets.MAIN_PUSH_DEPLOY_KEY }}"),
                    1,
                )

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
