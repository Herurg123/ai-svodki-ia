from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "automation/scripts/validate_production_daily_contract.py",
    '("git push", "git push origin HEAD:main"),',
    '("protected main push", "bash automation/scripts/push_protected_main.sh HEAD:main"),',
)

replace_once(
    "automation/tests/test_pr_gate_and_main_protection.py",
    '                self.assertIn("automation/scripts/push_protected_main.sh HEAD:main", text)\n                self.assertEqual(text.count("MAIN_PUSH_DEPLOY_KEY"), 1)\n',
    '                self.assertEqual(\n                    text.count("automation/scripts/push_protected_main.sh HEAD:main"), 1\n                )\n                self.assertEqual(\n                    text.count("MAIN_PUSH_DEPLOY_KEY: ${{ secrets.MAIN_PUSH_DEPLOY_KEY }}"),\n                    1,\n                )\n',
)

replace_once(
    "automation/tests/test_repository_hygiene_workflow.py",
    'CI = ROOT / ".github" / "workflows" / "ci.yml"\n',
    'CI = ROOT / ".github" / "workflows" / "ci.yml"\nPR_GATE = ROOT / ".github" / "workflows" / "pr-gate.yml"\n',
)
replace_once(
    "automation/tests/test_repository_hygiene_workflow.py",
    '    def test_main_ci_runs_when_agent_contract_changes(self) -> None:\n        ci = CI.read_text(encoding="utf-8")\n        self.assertEqual(ci.count(\'- "AGENTS.md"\'), 2)\n',
    '    def test_agent_contract_changes_are_covered_by_main_ci(self) -> None:\n        ci = CI.read_text(encoding="utf-8")\n        gate = PR_GATE.read_text(encoding="utf-8")\n        self.assertEqual(ci.count(\'- "AGENTS.md"\'), 1)\n        self.assertIn("workflow_call:", ci)\n        self.assertIn("pull_request:", gate)\n        self.assertIn("every path that is not proven video-only belongs to Main CI", gate)\n',
)

replace_once(
    "automation/tests/test_workflow_hygiene.py",
    '        self.assertIn("workflow_dispatch:", workflow)\n        self.assertIn("pull_request:", workflow)\n        self.assertIn("push:", workflow)\n',
    '        self.assertIn("workflow_dispatch:", workflow)\n        self.assertIn("workflow_call:", workflow)\n        self.assertNotIn("  pull_request:\\n", workflow)\n        self.assertIn("push:", workflow)\n        gate = (WORKFLOW_DIR / "pr-gate.yml").read_text(encoding="utf-8")\n        self.assertIn("pull_request:", gate)\n        self.assertIn("uses: ./.github/workflows/ci.yml", gate)\n',
)
