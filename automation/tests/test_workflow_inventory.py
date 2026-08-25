from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"


class WorkflowInventoryTests(unittest.TestCase):
    def test_only_canonical_workflows_remain(self) -> None:
        actual = {path.name for path in WORKFLOW_ROOT.glob("*.yml")}
        self.assertEqual(
            actual,
            {
                "pr-gate.yml",
                "ci.yml",
                "video-ci.yml",
                "daily-production.yml",
                "deploy-posts.yml",
                "repository-cleanup.yml",
                "repository-hygiene.yml",
            },
        )

    def test_no_one_shot_or_emergency_dispatchers_remain(self) -> None:
        names = {path.name.casefold() for path in WORKFLOW_ROOT.glob("*.yml")}
        self.assertFalse(any("one-shot" in name for name in names))
        self.assertFalse(any("emergency" in name for name in names))


if __name__ == "__main__":
    unittest.main()
