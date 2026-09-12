from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "weak-source-signal-retention-2026-09-11.json"
ARCHITECTURE = ROOT / "automation" / "ARCHITECTURE.md"
SEARCH_MATRIX = ROOT / "automation" / "specs" / "search-change-validation-matrix.md"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


primary = load("weak_source_p3_primary", "primary_recall_search.py")
coverage_pre = load("weak_source_p3_coverage", "ensure_story_coverage_pre_p0.py")


class WeakSourceSignalRetentionP3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def _signals_for(self, rejection: dict) -> list[dict]:
        return primary.collect_unresolved_signals([
            {
                "direction_id": self.fixture["positive_control"]["direction_id"],
                "status": "complete_with_gaps",
                "accepted_count": 0,
                "model_rejections": [rejection],
            }
        ])

    def test_saved_sep11_deepseek_weak_source_is_retained_as_evidence_only(self) -> None:
        control = self.fixture["positive_control"]
        signals = self._signals_for(control["rejection"])
        self.assertEqual(len(signals), 1)
        signal = signals[0]
        expected = control["expected"]
        for key, value in expected.items():
            self.assertEqual(signal.get(key), value)
        self.assertEqual(signal["reason_code"], "weak_source")
        self.assertEqual(signal["status"], "unresolved")
        self.assertEqual(
            signal["source_provenance"]["url"],
            control["rejection"]["url"],
        )
        self.assertEqual(signal["source_provenance"]["reason_code"], "weak_source")
        self.assertEqual(signal["source_provenance"]["reason"], control["rejection"]["reason"])
        self.assertEqual(signal["resolution_eligibility"], "deferred_exact_authoritative_binding")

    def test_unqualified_weak_source_controls_are_not_promoted_into_queue(self) -> None:
        for case in self.fixture["negative_controls"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(self._signals_for(case["rejection"]), [])

    def test_weak_source_queue_does_not_reserve_existing_coverage_resolution_slot(self) -> None:
        control = self.fixture["positive_control"]
        signal = self._signals_for(control["rejection"])[0]
        original = coverage_pre._primary_quality_report
        try:
            coverage_pre._primary_quality_report = lambda _date: {
                "retrieval_quality_contract_version": coverage_pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
                "unresolved_signals": [signal],
            }
            self.assertEqual(coverage_pre._required_signals("2026-09-11"), [])
        finally:
            coverage_pre._primary_quality_report = original

    def test_existing_high_signal_unverified_resolution_behavior_is_unchanged(self) -> None:
        reports = [{
            "direction_id": "independent_missing_events",
            "model_rejections": [{
                "title": "Nvidia eyes up to $3b in SB Energy for OpenAI data center",
                "reason_code": "unverified",
                "reason": "Fresh Reuters result indicates investment but direct verification was unavailable.",
            }],
        }]
        signals = primary.collect_unresolved_signals(reports)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["reason_code"], "unverified")
        self.assertTrue(signals[0]["resolution_required"])
        self.assertNotIn("candidate_eligible", signals[0])

    def test_semantic_weak_source_evidence_survives_rejection_order_perturbation(self) -> None:
        control = self.fixture["positive_control"]["rejection"]
        unrelated = {
            "title": "Unrelated stale card",
            "url": "https://example.com/stale-card",
            "reason_code": "outside_window",
            "reason": "Outside the saved window.",
        }
        rows = []
        for rejections in ([control, unrelated], [unrelated, control]):
            signals = primary.collect_unresolved_signals([{
                "direction_id": "independent_missing_events",
                "model_rejections": rejections,
            }])
            weak = [item for item in signals if item.get("reason_code") == "weak_source"]
            self.assertEqual(len(weak), 1)
            semantic = dict(weak[0])
            semantic.pop("signal_id", None)
            rows.append(semantic)
        self.assertEqual(rows[0], rows[1])

    def test_p3a_is_zero_search_and_does_not_enable_authoritative_binding(self) -> None:
        self.assertEqual(self.fixture["production_api_calls"], 0)
        self.assertEqual(self.fixture["web_search_operations"], 0)
        self.assertEqual(self.fixture["search_budget_change"], 0)
        self.assertFalse(self.fixture["invariants"]["automatic_authoritative_binding_enabled"])
        control = self.fixture["positive_control"]
        self.assertIn("future_authoritative_binding_reference_only", control)
        self.assertFalse(control["expected"]["resolution_required"])
        self.assertFalse(control["expected"]["candidate_eligible"])

    def test_canonical_docs_keep_p3a_evidence_only_and_p3b_deferred(self) -> None:
        architecture = ARCHITECTURE.read_text(encoding="utf-8")
        matrix = SEARCH_MATRIX.read_text(encoding="utf-8")
        self.assertIn("P3a weak-source signal retention changes only Primary diagnostic provenance", architecture)
        self.assertIn("`resolution_required=false`, `candidate_eligible=false`", architecture)
        self.assertIn("Exact authoritative\nbinding and automatic closure are a separate deferred P3b boundary", architecture)
        self.assertIn("| D6 | Degradation / weak source |", matrix)
        self.assertIn("queue-positive не становится retrieval-positive", matrix)
        self.assertIn("восьмой\nCoverage search не появляется", architecture)


if __name__ == "__main__":
    unittest.main()
