from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "repository_hygiene_policy",
    SCRIPT_DIR / "repository_hygiene_policy.py",
)
assert SPEC and SPEC.loader
policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = policy
SPEC.loader.exec_module(policy)


class SearchBaselineArchiveTests(unittest.TestCase):
    def test_pre_hybrid_baseline_branch_is_permanent(self):
        name = "archive/search-baseline-pre-hybrid-2026-08-09"
        self.assertIn(name, policy.PERMANENT_ARCHIVE_BRANCHES)
        classification, reason, _ = policy.classify_branch(
            {"name": name, "protected": False, "commit": {"sha": "a" * 40}},
            repository="Herurg123/ai-svodki-ia",
            default_branch="main",
            prs=[],
            recent_numbers=set(),
        )
        self.assertEqual((classification, reason), ("protected", "permanent_archive_branch"))


if __name__ == "__main__":
    unittest.main()
