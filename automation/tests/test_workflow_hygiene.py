from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


class WorkflowHygieneTests(unittest.TestCase):
    def test_workflows_have_stable_human_names(self) -> None:
        workflows = sorted(
            [*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")]
        )
        self.assertTrue(workflows, "No GitHub Actions workflows found")

        forbidden_name_prefixes = (
            "apply ",
            "diagnose ",
            "temporary ",
            "patch ",
        )
        forbidden_path_fragments = (
            "apply-",
            "apply_",
            "diagnose-",
            "diagnose_",
            "temporary-",
            "temporary_",
            "patch-",
            "patch_",
        )

        for path in workflows:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                match = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
                self.assertIsNotNone(match, f"{path.name} has no top-level name")
                assert match is not None
                name = match.group(1).strip().strip("\"'")
                normalized = name.casefold()
                self.assertTrue(name, f"{path.name} has an empty workflow name")
                self.assertFalse(
                    name.startswith(".github/workflows/"),
                    f"{path.name} exposes an internal path instead of a human name",
                )
                self.assertFalse(
                    normalized.startswith(forbidden_name_prefixes),
                    f"Temporary workflow name must not be committed: {name}",
                )
                stem = path.stem.casefold()
                self.assertFalse(
                    any(fragment in stem for fragment in forbidden_path_fragments),
                    f"Temporary workflow file must not be committed: {path.name}",
                )

    def test_main_ci_is_permanent_read_only_validation(self) -> None:
        workflow = (WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("name: Main CI", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("workflow_call:", workflow)
        self.assertNotIn("  pull_request:\n", workflow)
        self.assertIn("push:", workflow)
        gate = (WORKFLOW_DIR / "pr-gate.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", gate)
        self.assertIn("uses: ./.github/workflows/ci.yml", gate)
        self.assertIn("contents: read", workflow)
        self.assertIn("Offline production checks", workflow)
        self.assertNotIn("github.head_ref", workflow)
        self.assertNotIn("automation/patches/", workflow)
        self.assertNotIn("contents: write", workflow)


if __name__ == "__main__":
    unittest.main()
