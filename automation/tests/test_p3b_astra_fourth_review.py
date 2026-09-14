from __future__ import annotations

import copy
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
        self.assertEqual(coverage._impl.__name__, "ensure_story_coverage_p3b_v6")
        self.assertIs(coverage._exact_binding, binder)
        self.assertEqual(coverage.P3B_EXACT_BINDING_VERSION, 2)
        self.assertEqual(binder.EVIDENCE_VERSION, 2)
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

    def test_direct_binder_counterexamples_are_not_exact_event_identity(self) -> None:
        launch = second.launch_signal()
        ga = ga_signal()
        for signal, surface in (
            (launch, "DeepSeek reportedly launched V4.1 Flash"),
            (launch, "DeepSeek V4.1 Flash launch may happen next month"),
            (ga, "DeepSeek V4.1 Flash general availability cancelled"),
            (
                ga,
                "DeepSeek V4.1 Flash general availability. "
                "DeepSeek V4.1 Flash remains in preview.",
            ),
        ):
            with self.subTest(surface=surface):
                ok, _reason = binder.exact_event_identity(surface, copy.deepcopy(signal))
                self.assertFalse(ok, msg=surface)

    def test_positive_processed_snapshot_from_evidence_v1_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
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
                "binder_evidence_version": 1,
            }
            reservation.mark_request_started()
            reservation.save_raw_response({"id": "evidence-v1", "status": "completed"})
            reservation.mark_processed(saved)

            with mock.patch.object(coverage._impl, "STATE_DIR", state):
                self.assertTrue(
                    coverage._impl._processed_positive_snapshot_is_stale(controls.DATE)
                )


if __name__ == "__main__":
    unittest.main()
