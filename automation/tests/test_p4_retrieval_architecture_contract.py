from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agency_discovery_rescue_v5 as agency_v5
import ensure_story_coverage_policy as coverage
import hybrid_search_completeness as hybrid

ARCHITECTURE = ROOT / "automation" / "ARCHITECTURE.md"
AGENTS = ROOT / "AGENTS.md"


class P4RetrievalArchitectureContractTests(unittest.TestCase):
    def test_search_budgets_and_coverage_inventory_are_unchanged(self) -> None:
        self.assertEqual(hybrid.DEFAULT_MAXIMUM_SEARCH_CALLS, 4)
        self.assertEqual(hybrid.CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS, 5)
        self.assertEqual(hybrid.PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS, 24)
        self.assertEqual(hybrid.PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS, 25)
        self.assertEqual(agency_v5.MAXIMUM_SEARCH_OPERATIONS, 1)
        self.assertEqual(
            coverage.AUDIT_DIRECTION_IDS,
            (
                "security_world",
                "security_russia",
                "security_asia",
                "legal_copyright_scraping",
                "curiosity",
                "general_coverage_gaps",
            ),
        )
        self.assertEqual(coverage.DEFAULT_MAXIMUM_AUDIT_CALLS, 7)

    def test_architecture_describes_active_v5_not_old_gap_aware_v4(self) -> None:
        text = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("Query v5 остаётся\nglobal", text)
        self.assertIn("Preserved v4 остаётся\nreplay/rollback", text)
        self.assertNotIn("V4 делает единственный query gap-aware", text)

    def test_p4_is_one_way_and_zero_paid(self) -> None:
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        agents = AGENTS.read_text(encoding="utf-8")
        self.assertIn("может только переоткрыть", architecture)
        self.assertIn("may only **re-open**", agents)
        self.assertIn("true никогда не становится false", architecture)
        self.assertIn("0 OpenAI/Web Search operations", architecture)
        self.assertIn("must never turn\n`health_check_needed=true` into false", agents)

    def test_p4_does_not_authorize_regional_coverage_expansion(self) -> None:
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        agents = AGENTS.read_text(encoding="utf-8")
        self.assertIn("не входят в active contract", architecture)
        self.assertIn("Additional regional Coverage searches", agents)


if __name__ == "__main__":
    unittest.main()
