from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_editorial_scenarios import run_scenarios  # noqa: E402


class EditorialScenarioMatrixTests(unittest.TestCase):
    def test_all_declared_scenarios_pass(self) -> None:
        report = run_scenarios()
        failures = [
            f"{item['scenario_id']}: {item['error']}"
            for item in report["results"]
            if item["status"] != "passed"
        ]
        self.assertEqual(failures, [], "\n".join(failures))
        self.assertEqual(report["scenario_count"], 14)
        self.assertFalse(report["network_used"])
        self.assertFalse(report["openai_used"])


if __name__ == "__main__":
    unittest.main()
