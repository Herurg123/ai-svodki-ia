from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HYGIENE = ROOT / ".github" / "workflows" / "repository-hygiene.yml"
CONTENT = ROOT / ".github" / "workflows" / "repository-cleanup.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
AGENTS = ROOT / "AGENTS.md"
ROOT_README = ROOT / "README.md"
AUTOMATION_README = ROOT / "automation" / "README.md"
GITIGNORE = ROOT / ".gitignore"


class RepositoryHygieneWorkflowTests(unittest.TestCase):
    def test_hygiene_is_separate_from_32_day_content_cleanup(self) -> None:
        hygiene = HYGIENE.read_text(encoding="utf-8")
        content = CONTENT.read_text(encoding="utf-8")
        self.assertIn('cron: "43 12 * * *"', hygiene)
        self.assertIn('cron: "43 22 * * *"', content)
        self.assertIn("minimum 32", content)
        self.assertNotIn("cleanup_repository_content.py", hygiene)
        self.assertNotIn("cleanup_public_posts.py", hygiene)

    def test_destructive_permissions_are_split_by_job(self) -> None:
        workflow = HYGIENE.read_text(encoding="utf-8")
        self.assertIn("contents: write", workflow)
        self.assertIn("actions: write", workflow)
        self.assertNotIn("permissions:\n  contents: write\n  actions: write", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_hygiene_writes_readable_summary_and_short_lived_json(self) -> None:
        workflow = HYGIENE.read_text(encoding="utf-8")
        self.assertNotIn("--output", workflow)
        self.assertEqual(workflow.count("--report automation/preview/repository-hygiene/"), 3)
        self.assertEqual(workflow.count("render_repository_hygiene_summary.py"), 3)
        self.assertEqual(workflow.count(' --summary "${GITHUB_STEP_SUMMARY}"'), 3)
        self.assertEqual(workflow.count("uses: actions/upload-artifact@v4"), 3)
        self.assertEqual(workflow.count("retention-days: 2"), 3)
        self.assertEqual(workflow.count("if-no-files-found: ignore"), 3)
        self.assertIn("--mode plan", workflow)
        self.assertIn("--scope branches", workflow)
        self.assertIn("--scope actions", workflow)

    def test_agent_contract_limits_automatic_mutation(self) -> None:
        text = " ".join(AGENTS.read_text(encoding="utf-8").split())
        self.assertIn("repository hygiene", text.lower())
        self.assertIn("ephemeral GitHub objects", text)
        self.assertIn("must not edit tracked project files", text)

    def test_readmes_and_runtime_ignores_document_hygiene(self) -> None:
        root_readme = ROOT_README.read_text(encoding="utf-8")
        automation_readme = AUTOMATION_README.read_text(encoding="utf-8")
        gitignore = GITIGNORE.read_text(encoding="utf-8")
        self.assertIn("repository-hygiene.yml", root_readme)
        self.assertIn("## Правила инженерной уборки GitHub", root_readme)
        self.assertIn("Actions → Repository hygiene", root_readme)
        self.assertIn("retention: 2 дня", root_readme)
        self.assertIn("repository-hygiene.yml", automation_readme)
        self.assertIn("## Repository hygiene", automation_readme)
        self.assertIn("automation/preview/", gitignore)
        self.assertIn("automation/recovery/", gitignore)

    def test_main_ci_runs_when_agent_contract_changes(self) -> None:
        ci = CI.read_text(encoding="utf-8")
        self.assertEqual(ci.count('- "AGENTS.md"'), 2)


if __name__ == "__main__":
    unittest.main()
