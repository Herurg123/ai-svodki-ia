from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"


class NoStaleDispatchersTests(unittest.TestCase):
    def test_no_workflow_contains_fixed_recovery_run_id(self) -> None:
        for path in WORKFLOW_ROOT.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(
                text,
                r'recovery_run_id["\s:]+312\d+',
                msg=f"{path.name} contains a fixed recovery run id",
            )


if __name__ == "__main__":
    unittest.main()
