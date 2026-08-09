from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import hybrid_search_completeness as hc


class HybridSearchBudgetContractTests(unittest.TestCase):
    def test_budget_contract_is_three_plus_optional_one(self):
        self.assertEqual(hc.FIXED_SEARCH_CALLS, 3)
        self.assertEqual(hc.DEFAULT_MAXIMUM_SEARCH_CALLS, 4)
        self.assertEqual(len(hc.COMPLETENESS_DIRECTIONS), 3)
        self.assertEqual(hc.ADAPTIVE_DIRECTION_ID, "adaptive_gap")

    def test_primary_is_not_part_of_hybrid_budget(self):
        self.assertNotIn("primary", hc.DIRECTION_IDS)


if __name__ == "__main__":
    unittest.main()
