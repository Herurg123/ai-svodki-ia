from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
TESTS = ROOT / "automation" / "tests"
sys.path[:0] = [str(SCRIPTS), str(TESTS)]

import ensure_story_coverage as coverage
import test_p3b_astra_regressions as controls
import test_p3b_astra_second_review as second
import weak_source_exact_binding_v4 as binder


def _raw_response(response_id: str) -> dict:
    payload = {
        "status": "complete_with_gaps",
        "direction_id": "general_coverage_gaps",
        "candidates": [],
        "rejections": [],
    }
    return {
        "id": response_id,
        "status": "completed",
        "model": "gpt-test",
        "output_text": json.dumps(payload, ensure_ascii=False),
        "output": [
            {
                "id": "search-1",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": "fixture exact query", "sources": []},
            }
        ],
    }



def ga_signal() -> dict:
    signal = second.launch_signal()
    signal["title"] = "DeepSeek V4.1 Flash general availability"
    signal["lifecycle_action_anchors"] = ["general_availability"]
    return signal


def ga_candidate() -> dict:
    item = second.launch_candidate()
    item["title"] = "DeepSeek V4.1 Flash general availability"
    item["event_type"] = "general_availability"
    item["event_summary"] = item["title"]
    item["primary_source"]["title"] = item["title"]
    item["primary_source"]["url"] = "https://www.deepseek.com/en/news/v4-1-flash-ga/"
    return item


class AstraFourthReviewRegressions(unittest.TestCase):
    def test_public_runtime_still_uses_active_v4_binder(self) -> None:
        self.assertEqual(coverage._impl.__name__, "ensure_story_coverage_p3b_v7")
        self.assertTrue(coverage._impl._v6.__name__.endswith("p3b_v6_preserved"))
        self.assertIs(coverage._exact_binding, binder)
        self.assertEqual(coverage.P3B_EXACT_BINDING_VERSION, 2)
        self.assertEqual(binder.EVIDENCE_VERSION, 6)
        self.assertEqual(coverage.P3B_BINDER_EVIDENCE_VERSION, binder.EVIDENCE_VERSION)

    def test_suffix_modal_uncertain_launch_assertions_fail_closed(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        bad_surfaces = (
            "DeepSeek reportedly launched V4.1 Flash",
            "DeepSeek V4.1 Flash launch expected next month",
            "DeepSeek V4.1 Flash launch may happen next month",
            "DeepSeek V4.1 Flash launch might happen next month",
            "DeepSeek V4.1 Flash launch could happen next month",
            "DeepSeek V4.1 Flash launch denied",
            "DeepSeek V4.1 Flash launch was reportedly cancelled",
        )
        for surface in bad_surfaces:
            with self.subTest(surface=surface):
                result = second.process_candidate(
                    signal=signal,
                    candidate=item,
                    surface=surface,
                )
                self.assertEqual(result["candidates"], [], msg=surface)
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                    msg=surface,
                )

        positive = second.process_candidate(
            signal=signal,
            candidate=item,
            surface="DeepSeek launched V4.1 Flash today",
        )
        self.assertEqual(len(positive["candidates"]), 1)

    def test_ga_suffix_noncurrent_assertions_fail_closed(self) -> None:
        signal = ga_signal()
        item = ga_candidate()
        bad_surfaces = (
            "DeepSeek V4.1 Flash general availability planned next month",
            "DeepSeek V4.1 Flash general availability cancelled",
            "DeepSeek V4.1 Flash general availability may happen next month",
        )
        for surface in bad_surfaces:
            with self.subTest(surface=surface):
                result = second.process_candidate(
                    signal=signal,
                    candidate=item,
                    surface=surface,
                )
                self.assertEqual(result["candidates"], [], msg=surface)
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                    msg=surface,
                )

        positive = second.process_candidate(
            signal=signal,
            candidate=item,
            surface="DeepSeek V4.1 Flash is now generally available",
        )
        self.assertEqual(len(positive["candidates"]), 1)

    def test_ga_preview_conflict_across_local_claims_fails_closed(self) -> None:
        signal = ga_signal()
        item = ga_candidate()
        surface = (
            "DeepSeek V4.1 Flash general availability. "
            "DeepSeek V4.1 Flash remains in preview."
        )
        result = second.process_candidate(
            signal=signal,
            candidate=item,
            surface=surface,
        )
        self.assertEqual(result["candidates"], [])
        reasons = {
            row.get("reason")
            for row in result["attempts"][-1]["binding_rejections"]
        }
        self.assertIn("authoritative_page_preview_ga_mismatch", reasons)

    def test_clean_claim_cannot_override_same_event_noncurrent_claim(self) -> None:
        cases = (
            (
                ga_signal(),
                ga_candidate(),
                "DeepSeek V4.1 Flash general availability. "
                "DeepSeek V4.1 Flash general availability planned next month.",
            ),
            (
                second.launch_signal(),
                second.launch_candidate(),
                "DeepSeek launched V4.1 Flash today. "
                "DeepSeek V4.1 Flash launch cancelled.",
            ),
        )
        for signal, item, surface in cases:
            with self.subTest(surface=surface):
                result = second.process_candidate(
                    signal=signal,
                    candidate=item,
                    surface=surface,
                )
                self.assertEqual(result["candidates"], [], msg=surface)
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                    msg=surface,
                )

    def test_current_claim_can_coexist_with_historical_background(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        surface = (
            "DeepSeek announces V4.1 Flash launch today. "
            "DeepSeek announces V4.1 Flash launch in 2025."
        )
        ok, reason = binder.exact_event_identity(surface, copy.deepcopy(signal))
        self.assertTrue(ok, msg=reason)
        self.assertEqual(reason, "exact_event_identity")

        bound, bound_reason = binder.candidate_exact_binding(
            copy.deepcopy(item),
            copy.deepcopy(signal),
            authoritative_domains=("deepseek.com",),
            authoritative_page_surface=surface,
            authoritative_final_url=item["primary_source"]["url"],
        )
        self.assertTrue(bound, msg=bound_reason)
        self.assertEqual(bound_reason, "exact_authoritative_page_binding")

        historical_only, historical_reason = binder.exact_event_identity(
            "DeepSeek announces V4.1 Flash launch in 2025.",
            copy.deepcopy(signal),
        )
        self.assertFalse(historical_only)
        self.assertEqual(historical_reason, "historical_event_context")

    def test_direct_binder_counterexamples_are_not_exact_event_identity(self) -> None:
        launch = second.launch_signal()
        ga = ga_signal()
        for signal, surface in (
            (launch, "DeepSeek reportedly launched V4.1 Flash"),
            (launch, "DeepSeek V4.1 Flash launch may happen next month"),
            (launch, "DeepSeek V4.1 Flash launch was reportedly cancelled"),
            (ga, "DeepSeek V4.1 Flash general availability cancelled"),
            (
                ga,
                "DeepSeek V4.1 Flash general availability. "
                "DeepSeek V4.1 Flash remains in preview.",
            ),
            (
                ga,
                "DeepSeek V4.1 Flash general availability. "
                "DeepSeek V4.1 Flash general availability planned next month.",
            ),
        ):
            with self.subTest(surface=surface):
                ok, _reason = binder.exact_event_identity(surface, copy.deepcopy(signal))
                self.assertFalse(ok, msg=surface)

    def test_positive_processed_snapshot_before_current_evidence_is_stale(self) -> None:
        for evidence_version in (1, 2, 3, 4, 5):
            with self.subTest(evidence_version=evidence_version), tempfile.TemporaryDirectory() as raw:
                state = Path(raw)
                helper = controls.AstraP3bRuntimeRegressions()
                plan, _ = helper._real_six_plan(state)
                reservation = helper._reservation(state, plan)
                saved = copy.deepcopy(plan)
                stale_candidate = controls.candidate()
                stale_candidate["audit_direction"] = "weak_source_exact_binding"
                saved["candidates"] = [stale_candidate]
                saved["weak_source_exact_binding"] = {
                    "version": 2,
                    "mode": coverage.P3B_MODE,
                    "status": "bound_candidate",
                    "disposition": "positive_exact_binding",
                    "candidate_count": 1,
                    "binder_evidence_version": evidence_version,
                }
                reservation.mark_request_started()
                raw_response = _raw_response(f"evidence-v{evidence_version}")
                reservation.save_raw_response(raw_response)
                _parsed, result_snapshot = coverage.replay_raw_response(
                    coverage._runtime,
                    raw_response,
                    maximum_web_search_calls=1,
                )
                reservation.save_result_snapshot(result_snapshot)
                reservation.mark_processed(saved)

                stale_snapshot = coverage._impl._load_stale_positive_snapshot(
                    state, controls.DATE
                )
                self.assertIsNotNone(stale_snapshot)


if __name__ == "__main__":
    unittest.main()
