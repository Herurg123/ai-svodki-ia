from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "2026-08-29-coverage-unverified-exhaustion.json"

spec = importlib.util.spec_from_file_location(
    "coverage_aug29_exhaustion_test", SCRIPTS / "ensure_story_coverage.py"
)
assert spec and spec.loader
coverage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = coverage
spec.loader.exec_module(coverage)

_fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
SIGNALS = [
    {
        "signal_id": sid,
        "status": "unresolved",
        "title": "Nvidia reportedly agrees to acquire Hugging Face for $12.9 billion",
        "evidence_reason": "Nvidia Hugging Face $12.9 billion report remains unverified",
        "entities": ["Nvidia", "Hugging", "Face"],
        "likely_significance_score": 4,
        "resolution_required": True,
    }
    for sid in _fixture["expected_signal_ids"]
]
REJECTIONS = _fixture["rejections"]


def attempt(rejections=None):
    return {
        "direction_id": "general_coverage_gaps",
        "attempt": 2,
        "status": "checked_with_gaps",
        "search_strategy": coverage.UNRESOLVED_RESOLUTION_STRATEGY,
        "unresolved_resolution_version": 1,
        "signal_ids": [row["signal_id"] for row in SIGNALS],
        "required_query": _fixture["expected_query"],
        "allowed_domains": [],
        "actual_queries": [_fixture["expected_query"]],
        "candidates": [],
        "rejections": copy.deepcopy(REJECTIONS if rejections is None else rejections),
        "api": {
            "status": "completed",
            "web_search_calls_completed": 1,
            "web_search_call_items_total": 1,
        },
        "error": None,
    }


class Aug29CoverageUnverifiedExhaustionTests(unittest.TestCase):
    def test_real_incident_shape_is_bounded_complete_without_candidate(self):
        item = attempt()
        ids = coverage._bounded_unverified_signal_ids(
            item["rejections"],
            SIGNALS,
            api=item["api"],
            actual_queries=item["actual_queries"],
            allowed_domains=item["allowed_domains"],
        )
        self.assertEqual(ids, {row["signal_id"] for row in SIGNALS})
        quality = coverage._quality_from_resolution_attempt(SIGNALS, item)
        self.assertEqual(quality["status"], "complete")
        self.assertEqual(quality["remaining_required_signal_count"], 0)
        self.assertIn("event remains excluded", quality["reason"])

    def test_one_or_two_hosts_remain_fail_closed(self):
        for count in (1, 2):
            quality = coverage._quality_from_resolution_attempt(
                SIGNALS, attempt(REJECTIONS[:count])
            )
            self.assertEqual(quality["status"], "degraded")

    def test_same_host_repetition_remains_fail_closed(self):
        rows = copy.deepcopy(REJECTIONS)
        for index, row in enumerate(rows):
            row["url"] = f"https://same.example/{index}"
        quality = coverage._quality_from_resolution_attempt(SIGNALS, attempt(rows))
        self.assertEqual(quality["status"], "degraded")

    def test_unrelated_reports_remain_fail_closed(self):
        rows = [
            {
                "title": "OtherCo cloud update",
                "url": f"https://other{index}.example/x",
                "reason_code": "unverified",
                "reason": "OtherCo cloud update remains unverified",
            }
            for index in range(3)
        ]
        quality = coverage._quality_from_resolution_attempt(SIGNALS, attempt(rows))
        self.assertEqual(quality["status"], "degraded")

    def test_technical_ambiguity_remains_fail_closed(self):
        item = attempt()
        item["api"]["status"] = "failed"
        quality = coverage._quality_from_resolution_attempt(SIGNALS, item)
        self.assertEqual(quality["status"], "degraded")

    def test_domain_filtered_resolution_remains_fail_closed(self):
        item = attempt()
        item["allowed_domains"] = ["example.com"]
        quality = coverage._quality_from_resolution_attempt(SIGNALS, item)
        self.assertEqual(quality["status"], "degraded")

    def test_multiple_search_operations_remain_fail_closed(self):
        item = attempt()
        item["api"]["web_search_calls_completed"] = 2
        quality = coverage._quality_from_resolution_attempt(SIGNALS, item)
        self.assertEqual(quality["status"], "degraded")

    def test_saved_failed_run_is_reclassified_without_v8_or_new_search(self):
        mandatory = [
            {
                "direction_id": direction,
                "attempt": 1,
                "status": "checked",
                "api": {
                    "status": "completed",
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                },
            }
            for direction in coverage.AUDIT_DIRECTION_IDS
        ]
        prior = {
            "status": "error",
            "publication_date": "2026-08-29",
            "audit_state": "completed_unusable",
            "audit_status": "partial",
            "audit_error": "old failure",
            "error": "old failure",
            "web_search_performed": True,
            "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
            "partial_directions": [],
            "unchecked_directions": [],
            "directions": mandatory,
            "attempts": mandatory + [attempt()],
            "candidate_pool_before": {"total": 6},
            "api": {"status": "completed"},
            "search_budget": {
                "maximum_calls": 7,
                "completed_calls": 7,
                "remaining_calls": 0,
            },
            "retrieval_quality_contract_version": 1,
            "retrieval_quality": {"status": "degraded"},
        }
        with mock.patch.object(
            coverage, "_required_signals", return_value=copy.deepcopy(SIGNALS)
        ):
            prepared = coverage._prepare_prior_for_quality(prior, None)
            self.assertEqual(prepared["audit_state"], "completed_usable")
            self.assertEqual(prepared["audit_status"], "complete_with_gaps")
            self.assertEqual(prepared["search_budget"]["completed_calls"], 7)
            self.assertEqual(prepared["search_budget"]["remaining_calls"], 0)
            self.assertEqual(prepared["retrieval_quality"]["status"], "complete")
            with mock.patch.object(
                coverage,
                "_V8_EXECUTE",
                side_effect=AssertionError("must not rerun v8"),
            ):
                result = coverage.execute_audit_plan(
                    api_key="unused",
                    model="gpt-5.6-terra",
                    template="",
                    publication_date="2026-08-29",
                    search_window={},
                    missing_total=1,
                    maximum_web_search_calls=7,
                    existing_candidates=[{"id": "x"}],
                    archive={},
                    prior_plan=prior,
                )
            self.assertEqual(result["search_budget"]["completed_calls"], 7)
            self.assertEqual(result["retrieval_quality"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
