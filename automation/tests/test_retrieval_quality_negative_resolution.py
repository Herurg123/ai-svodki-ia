from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coverage = load(
    "retrieval_quality_negative_resolution_test",
    "ensure_story_coverage.py",
)


RILLET_SIGNAL = {
    "signal_id": "sig-business_investment_partnerships-02",
    "status": "unresolved",
    "title": "Rillet Lands $100M to Scale AI ERP",
    "origin_direction": "business_investment_partnerships",
    "reason_code": "unverified",
    "evidence_reason": (
        "Only AIPressRoom claimed $100M Series C; Rillet primary confirms "
        "AI-native ERP but not round/date/valuation/investors."
    ),
    "likely_significance_score": 4,
    "entities": ["Rillet", "Lands", "Scale", "ERP"],
    "anchors": ["$100M", "$100 млн"],
    "resolution_required": True,
}

RILLET_OUTSIDE_WINDOW = {
    "title": "Rillet Raises $100M Series C at $1B Valuation",
    "url": "https://example.com/rillet",
    "reason_code": "outside_window",
    "reason": (
        "Rillet announced the $100M Series C on 19 August; later articles are "
        "reprints and there is no new material update inside the current window."
    ),
}


def fake_result(*, rejections: list[dict], candidates: list[dict] | None = None):
    return types.SimpleNamespace(
        payload={
            "status": "complete_with_gaps",
            "candidates": candidates or [],
            "rejections": rejections,
            "notes": "bounded resolution completed",
        },
        metadata={
            "response_id": "resp_test",
            "status": "completed",
            "model": "gpt-5.6-terra",
            "actual_queries": ["Rillet Lands Scale ERP latest"],
            "consulted_sources": [],
            "web_search_calls": 1,
            "web_search_calls_completed": 1,
            "web_search_call_items_total": 1,
            "web_search_call_statuses": {"completed": 1},
            "web_search_action_type_counts": {"search": 1},
            "web_search_search_statuses": {"completed": 1},
            "web_search_navigation_items_total": 0,
            "usage": {},
        },
    )


def base_plan() -> dict:
    return {
        "audit_status": "complete",
        "attempts": [],
        "candidates": [],
        "search_budget": {
            "maximum_calls": 7,
            "completed_calls": 0,
            "remaining_calls": 7,
        },
    }


class NegativeResolutionClassificationTests(unittest.TestCase):
    def run_resolution(self, rejections: list[dict]):
        with mock.patch.object(
            coverage._runtime,
            "_policy_audit_request",
            return_value=fake_result(rejections=rejections),
        ):
            return coverage._run_resolution(
                plan=base_plan(),
                signals=[dict(RILLET_SIGNAL)],
                api_key="unused-test-key",
                model="gpt-5.6-terra",
                search_window={
                    "start_at": "2026-08-23T09:07:30+03:00",
                    "end_at": "2026-08-25T04:43:30+03:00",
                },
                archive={"items": []},
                maximum_web_search_calls=7,
            )

    def test_outside_window_is_terminal_negative_not_failure(self):
        result = self.run_resolution([dict(RILLET_OUTSIDE_WINDOW)])
        self.assertEqual(result["audit_status"], "complete")
        self.assertEqual(result["retrieval_quality"]["status"], "complete")
        self.assertEqual(
            result["retrieval_quality"]["remaining_required_signal_count"], 0
        )
        self.assertEqual(result["candidates"], [])
        attempt = result["attempts"][-1]
        self.assertEqual(attempt["outcome"], "resolved_no_candidate")
        self.assertEqual(attempt["resolution_disposition"], "terminal_negative")
        self.assertEqual(
            attempt["terminal_negative_signal_ids"],
            ["sig-business_investment_partnerships-02"],
        )

    def test_unverified_remains_fail_closed(self):
        rejection = dict(RILLET_OUTSIDE_WINDOW)
        rejection["reason_code"] = "unverified"
        result = self.run_resolution([rejection])
        self.assertEqual(result["audit_status"], "partial")
        self.assertEqual(result["retrieval_quality"]["status"], "degraded")
        self.assertEqual(result["attempts"][-1]["outcome"], "unresolved")

    def test_weak_source_remains_fail_closed(self):
        rejection = dict(RILLET_OUTSIDE_WINDOW)
        rejection["reason_code"] = "weak_source"
        result = self.run_resolution([rejection])
        self.assertEqual(result["audit_status"], "partial")
        self.assertEqual(result["retrieval_quality"]["status"], "degraded")

    def test_subjective_insufficient_significance_remains_fail_closed(self):
        rejection = dict(RILLET_OUTSIDE_WINDOW)
        rejection["reason_code"] = "insufficient_significance"
        result = self.run_resolution([rejection])
        self.assertEqual(result["audit_status"], "partial")
        self.assertEqual(result["retrieval_quality"]["status"], "degraded")

    def test_unrelated_terminal_rejection_does_not_clear_signal(self):
        rejection = {
            "title": "DifferentCo announced an old cloud feature",
            "url": "https://example.com/different",
            "reason_code": "outside_window",
            "reason": "DifferentCo published the feature before the current window.",
        }
        result = self.run_resolution([rejection])
        self.assertEqual(result["audit_status"], "partial")
        self.assertEqual(result["retrieval_quality"]["status"], "degraded")

    def test_second_unrelated_required_signal_keeps_resolution_partial(self):
        other = {
            "signal_id": "sig-other",
            "status": "unresolved",
            "title": "CompletelyDifferent model release",
            "evidence_reason": "A fresh model release could not be verified",
            "entities": ["CompletelyDifferent"],
            "anchors": ["Model X"],
            "likely_significance_score": 3,
            "resolution_required": True,
        }
        with mock.patch.object(
            coverage._runtime,
            "_policy_audit_request",
            return_value=fake_result(rejections=[dict(RILLET_OUTSIDE_WINDOW)]),
        ):
            result = coverage._run_resolution(
                plan=base_plan(),
                signals=[dict(RILLET_SIGNAL), other],
                api_key="unused-test-key",
                model="gpt-5.6-terra",
                search_window={
                    "start_at": "2026-08-23T09:07:30+03:00",
                    "end_at": "2026-08-25T04:43:30+03:00",
                },
                archive={"items": []},
                maximum_web_search_calls=7,
            )
        self.assertEqual(result["audit_status"], "partial")
        self.assertEqual(
            result["retrieval_quality"]["remaining_required_signal_count"], 1
        )


class NegativeResolutionRecoveryTests(unittest.TestCase):
    def mandatory_attempts(self):
        return [
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

    def test_bogus_complete_diagnostics_do_not_block_quality_retry(self):
        attempts = self.mandatory_attempts()
        attempts.append(
            {
                "direction_id": "general_coverage_gaps",
                "attempt": 2,
                "status": "checked",
                "search_strategy": coverage.UNRESOLVED_RESOLUTION_STRATEGY,
                "unresolved_resolution_version": 1,
                "signal_ids": ["sig-business_investment_partnerships-02"],
                "candidates": [],
                "rejections": [dict(RILLET_OUTSIDE_WINDOW)],
                "api": {
                    "status": "completed",
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                },
            }
        )
        prior = {
            "audit_status": "partial",
            "audit_state": "completed_unusable",
            "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
            "attempts": attempts,
            "directions": attempts[:6],
            "search_budget": {
                "maximum_calls": 7,
                "completed_calls": 7,
                "remaining_calls": 0,
            },
            "web_search_performed": True,
            "api": {"status": "completed"},
            "retrieval_quality_contract_version": 1,
            "retrieval_quality": {
                "status": "complete",
                "required_signal_count": 0,
            },
        }
        prepared = coverage._prepare_prior_for_quality(prior, None)
        self.assertEqual(len(prepared["attempts"]), 6)
        self.assertEqual(prepared["search_budget"]["completed_calls"], 6)
        self.assertEqual(prepared["search_budget"]["remaining_calls"], 1)
        self.assertNotIn("retrieval_quality", prepared)

    def test_finalizer_reconstructs_negative_resolution_diagnostics(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            production = root / "automation" / "preview" / "production-daily"
            production.mkdir(parents=True)
            primary = {
                "publication_date": "2026-08-25",
                "retrieval_quality_contract_version": 1,
                "unresolved_signals": [dict(RILLET_SIGNAL)],
            }
            (production / "primary-recall-2026-08-25.json").write_text(
                json.dumps(primary, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            report_path = production / "coverage-audit.json"
            report = {
                "publication_date": "2026-08-25",
                "audit_status": "complete",
                "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
                "attempts": [
                    {
                        "direction_id": "general_coverage_gaps",
                        "attempt": 2,
                        "status": "checked_with_gaps",
                        "search_strategy": coverage.UNRESOLVED_RESOLUTION_STRATEGY,
                        "unresolved_resolution_version": 1,
                        "signal_ids": ["sig-business_investment_partnerships-02"],
                        "required_query": "Scale Lands Rillet 100M latest",
                        "candidates": [],
                        "rejections": [dict(RILLET_OUTSIDE_WINDOW)],
                        "error": None,
                    }
                ],
                "retrieval_quality_contract_version": 1,
                "retrieval_quality": {
                    "status": "complete",
                    "required_signal_count": 0,
                },
            }
            report_path.write_text(
                json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            original_root = coverage.REPOSITORY_ROOT
            try:
                coverage.REPOSITORY_ROOT = root
                coverage._finalize_quality_report(report_path)
            finally:
                coverage.REPOSITORY_ROOT = original_root
            saved = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["retrieval_quality"]["status"], "complete")
            self.assertEqual(saved["retrieval_quality"]["required_signal_count"], 1)
            self.assertEqual(
                saved["retrieval_quality"]["remaining_required_signal_count"], 0
            )
            self.assertIsInstance(saved["unresolved_resolution"], dict)
            self.assertIn(
                "conclusively rejected",
                saved["retrieval_quality"]["reason"],
            )


if __name__ == "__main__":
    unittest.main()
