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
        self.assertNotIn("retention_days", hygiene)
        self.assertNotIn("cleanup_repository_content.py", hygiene)
        self.assertNotIn("cleanup_public_posts.py", hygiene)

    def test_destructive_permissions_are_split_by_job(self) -> None:
        workflow = HYGIENE.read_text(encoding="utf-8")
        self.assertIn("contents: write", workflow)
        self.assertIn("actions: write", workflow)
        self.assertNotIn("permissions:\n  contents: write\n  actions: write", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_hygiene_does_not_create_its_own_actions_artifact(self) -> None:
        workflow = HYGIENE.read_text(encoding="utf-8")
        self.assertNotIn("upload-artifact", workflow)
        self.assertIn("--mode plan", workflow)
        self.assertIn("--scope branches", workflow)
        self.assertIn("--scope actions", workflow)

    def test_agent_contract_limits_automatic_mutation(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("repository hygiene", text.lower())
        self.assertIn("ephemeral GitHub objects", text)
        self.assertIn("must not edit tracked project files", text)

    def test_readmes_and_runtime_ignores_document_hygiene(self) -> None:
        root_readme = ROOT_README.read_text(encoding="utf-8")
        automation_readme = AUTOMATION_README.read_text(encoding="utf-8")
        gitignore = GITIGNORE.read_text(encoding="utf-8")
        self.assertIn("repository-hygiene.yml", root_readme)
        self.assertIn("## Правила инженерной уборки GitHub", root_readme)
        self.assertIn("repository-hygiene.yml", automation_readme)
        self.assertIn("## Repository hygiene", automation_readme)
        self.assertIn("automation/preview/", gitignore)
        self.assertIn("automation/recovery/", gitignore)

    def test_main_ci_runs_when_agent_contract_changes(self) -> None:
        ci = CI.read_text(encoding="utf-8")
        self.assertEqual(ci.count('- "AGENTS.md"'), 2)


if __name__ == "__main__":
    unittest.main()
