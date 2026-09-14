from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ensure_story_coverage as coverage
import hybrid_search_completeness as hybrid
import weak_source_exact_binding_v4 as binder

ARCHITECTURE = ROOT / "automation" / "ARCHITECTURE.md"
MATRIX = ROOT / "automation" / "specs" / "p3b-exact-authoritative-binding-matrix.md"


class P3bArchitectureContractTests(unittest.TestCase):
    def test_docs_pin_active_v6_binder_v4_and_atomic_transfer(self) -> None:
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        matrix = MATRIX.read_text(encoding="utf-8")

        for text in (architecture, matrix):
            normalized = text.lower()
            self.assertIn("active p3b", normalized)
            self.assertIn("v6", normalized)
            self.assertIn("weak_source_exact_binding_v4.py", text)
            self.assertIn("coverage_slot_handoff", text)
            self.assertIn("atomic", text)
            self.assertIn("восьм", text)

        self.assertIn("release-then-reserve", architecture)
        self.assertIn("slot lock", matrix)
        self.assertIn("request admission", matrix)

    def test_runtime_and_search_ceilings_match_documented_contract(self) -> None:
        self.assertEqual(coverage._impl.__name__, "ensure_story_coverage_p3b_v6")
        self.assertIs(coverage._exact_binding, binder)
        self.assertEqual(coverage.P3B_EXACT_BINDING_VERSION, 2)
        self.assertEqual(coverage.P3B_BINDER_EVIDENCE_VERSION, binder.EVIDENCE_VERSION)
        self.assertEqual(coverage.DEFAULT_MAXIMUM_AUDIT_CALLS, 7)
        self.assertEqual(hybrid.PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS, 24)
        self.assertEqual(hybrid.PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS, 25)

        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("= 24 Web Search operations", architecture)
        self.assertIn("= 25 Web Search operations", architecture)


if __name__ == "__main__":
    unittest.main()
