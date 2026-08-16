from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


primary = load("retrieval_quality_primary_test", "primary_recall_search.py")
hybrid = load("retrieval_quality_hybrid_test", "hybrid_search_completeness.py")
coverage = load("retrieval_quality_coverage_test", "ensure_story_coverage.py")
recovery = load("retrieval_quality_recovery_test", "recover_digest_artifact.py")


class RetrievalQualityPrimaryTests(unittest.TestCase):
    def test_aug16_unverified_signals_are_preserved(self):
        reports = [{
            "direction_id": "independent_missing_events",
            "status": "complete_with_gaps",
            "accepted_count": 0,
            "model_rejections": [
                {
                    "title": "Nvidia eyes up to $3b in SB Energy for OpenAI data center",
                    "reason_code": "unverified",
                    "reason": "Fresh Reuters result indicates investment but direct verification was unavailable.",
                },
                {
                    "title": "Nvidia Downsizes $250 Billion Guarantee of OpenAI Data Center",
                    "reason_code": "unverified",
                    "reason": "Wall Street Journal result indicates a material guarantee change but direct verification was unavailable.",
                },
            ],
        }]
        signals = primary.collect_unresolved_signals(reports)
        self.assertEqual(len(signals), 2)
        self.assertTrue(all(item["resolution_required"] for item in signals))
        self.assertTrue(all(item["query_terms_are_hints_not_filters"] for item in signals))

    def test_weak_unverified_is_nonblocking(self):
        reports = [{
            "direction_id": "independent_missing_events",
            "model_rejections": [{
                "title": "TinyApp AI feature mention",
                "reason_code": "unverified",
                "reason": "Weak aggregated card could not be verified.",
            }],
        }]
        signal = primary.collect_unresolved_signals(reports)[0]
        self.assertFalse(signal["resolution_required"])

    def test_regional_zero_means_health_check_not_quota(self):
        reports = [
            {"direction_id": "china_asia_models", "status": "complete", "accepted_count": 0},
            {"direction_id": "china_asia_integrations", "status": "complete_with_gaps", "accepted_count": 0},
            {"direction_id": "russia", "status": "complete", "accepted_count": 0},
        ]
        health = primary.regional_health(reports)
        self.assertTrue(health["asia"]["health_check_needed"])
        self.assertTrue(health["russia"]["health_check_needed"])
        self.assertIn("never a publication quota", health["policy"])


class RetrievalQualityQueryTests(unittest.TestCase):
    def signals(self):
        return [
            {"signal_id": "sig-1", "title": "Nvidia eyes investment in SB Energy for OpenAI data center", "evidence_reason": "Reuters result mentioned investment and Ohio project", "entities": ["Nvidia", "OpenAI", "SB", "Energy"], "anchors": ["$3 billion"], "source_hint": "Reuters", "likely_significance_score": 5},
            {"signal_id": "sig-2", "title": "Nvidia downsizes guarantee for OpenAI data center", "evidence_reason": "WSJ result mentioned guarantee reduction", "entities": ["Nvidia", "OpenAI"], "anchors": ["$250 billion", "$120 billion"], "source_hint": "Wall Street Journal", "likely_significance_score": 5},
        ]

    def test_resolution_query_is_minimal_and_source_neutral(self):
        cluster = coverage.resolution_cluster(self.signals())
        query = coverage.build_resolution_query(cluster).casefold()
        self.assertIn("nvidia", query)
        self.assertIn("openai", query)
        self.assertIn("latest", query)
        self.assertNotIn("reuters", query)
        self.assertNotIn("site:", query)
        self.assertNotIn("sb", query)

    def test_regional_health_query_has_no_company_or_publisher_whitelist(self):
        query = hybrid.regional_health_query(("asia", "russia")).casefold()
        for forbidden in ("reuters", "nvidia", "openai", "alibaba", "yandex", "site:"):
            self.assertNotIn(forbidden, query)
        self.assertIn("russia", query)
        self.assertIn("china", query)
        self.assertIn("asia", query)

    def test_max_search_budget_remains_23(self):
        self.assertEqual(primary.DEFAULT_MAXIMUM_SEARCH_CALLS, 12)
        self.assertEqual(hybrid.DEFAULT_MAXIMUM_SEARCH_CALLS, 4)
        self.assertEqual(coverage.DEFAULT_MAXIMUM_AUDIT_CALLS, 7)
        self.assertEqual(primary.DEFAULT_MAXIMUM_SEARCH_CALLS + hybrid.DEFAULT_MAXIMUM_SEARCH_CALLS + coverage.DEFAULT_MAXIMUM_AUDIT_CALLS, 23)


class RetrievalQualityRecoveryTests(unittest.TestCase):
    def test_quality_migration_reuses_six_mandatory_and_frees_one_slot(self):
        attempts = []
        for direction in coverage.AUDIT_DIRECTION_IDS:
            attempts.append({
                "direction_id": direction,
                "attempt": 1,
                "status": "checked",
                "api": {"status": "completed", "web_search_calls_completed": 1, "web_search_call_items_total": 1},
            })
        attempts.append({
            "direction_id": "general_coverage_gaps",
            "attempt": 2,
            "status": "checked_with_gaps",
            "search_strategy": coverage.AGENCY_RESCUE_STRATEGY,
            "api": {"status": "completed", "web_search_calls_completed": 1, "web_search_call_items_total": 1},
        })
        prior = {
            "audit_status": "complete_with_gaps",
            "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
            "attempts": attempts,
            "directions": attempts[:6],
            "search_budget": {"maximum_calls": 7, "completed_calls": 7, "remaining_calls": 0},
        }
        prepared = coverage._prepare_prior_for_quality(prior, None)
        self.assertEqual(len(prepared["attempts"]), 6)
        self.assertEqual(prepared["search_budget"]["completed_calls"], 6)
        self.assertEqual(prepared["search_budget"]["remaining_calls"], 1)

    def test_old_modern_full_artifact_is_downgraded_not_discarded(self):
        with tempfile.TemporaryDirectory() as raw:
            root, source = Path(raw), Path(raw) / "artifact"
            source.mkdir()
            (source / "primary-recall.json").write_text("{}\n", encoding="utf-8")
            original = recovery._BASE_CHOOSE_SOURCE
            try:
                recovery._BASE_CHOOSE_SOURCE = lambda *_a, **_k: (source, "full", [])
                chosen, mode, diagnostics = recovery.choose_source(root, "2026-08-16")
            finally:
                recovery._BASE_CHOOSE_SOURCE = original
            self.assertEqual(chosen, source)
            self.assertEqual(mode, "partial_editorial")
            self.assertTrue(any(item.get("status") == "quality-contract-upgrade" for item in diagnostics))

    def test_current_quality_keeps_full_recovery(self):
        with tempfile.TemporaryDirectory() as raw:
            root, source = Path(raw), Path(raw) / "artifact"
            source.mkdir()
            (source / "primary-recall.json").write_text("{}\n", encoding="utf-8")
            (root / "coverage-audit.json").write_text(json.dumps({
                "publication_date": "2026-08-16",
                "retrieval_quality_contract_version": 1,
                "retrieval_quality": {"status": "complete"},
            }) + "\n", encoding="utf-8")
            original = recovery._BASE_CHOOSE_SOURCE
            try:
                recovery._BASE_CHOOSE_SOURCE = lambda *_a, **_k: (source, "full", [])
                _chosen, mode, _diagnostics = recovery.choose_source(root, "2026-08-16")
            finally:
                recovery._BASE_CHOOSE_SOURCE = original
            self.assertEqual(mode, "full")


if __name__ == "__main__":
    unittest.main()
