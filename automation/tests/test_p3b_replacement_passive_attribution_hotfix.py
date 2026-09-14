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

DATE = controls.DATE
MODEL = controls.MODEL
WINDOW = controls.WINDOW
TEMPLATE = controls.TEMPLATE
SIGNAL = controls.SIGNAL


class P3bReplacementPassiveAttributionHotfixTests(unittest.TestCase):
    def test_active_binder_evidence_version_is_3(self) -> None:
        self.assertIs(coverage._exact_binding, binder)
        self.assertEqual(binder.EVIDENCE_VERSION, 3)
        self.assertEqual(coverage.P3B_BINDER_EVIDENCE_VERSION, 3)
        self.assertEqual(coverage.P3B_EXACT_BINDING_VERSION, 2)

    def test_replacement_foreign_trailing_agent_fails_closed(self) -> None:
        item = controls.candidate()
        surfaces = (
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by openai",
            "DeepSeek replaces V4 Pro with V4.1 Flash by OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash, by OpenAI",
        )
        for surface in surfaces:
            with self.subTest(surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, SIGNAL),
                    (False, "organization_event_attribution_mismatch"),
                )
                result = second.process_candidate(
                    signal=copy.deepcopy(SIGNAL),
                    candidate=copy.deepcopy(item),
                    surface=surface,
                )
                self.assertEqual(result["candidates"], [])
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                )

    def test_replacement_positive_controls_remain_positive(self) -> None:
        item = controls.candidate()
        surfaces = (
            "DeepSeek replaces V4 Pro with V4.1 Flash",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash",
            "V4 Pro was replaced by V4.1 Flash by DeepSeek",
        )
        for surface in surfaces:
            with self.subTest(surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, SIGNAL),
                    (True, "exact_event_identity"),
                )
                result = second.process_candidate(
                    signal=copy.deepcopy(SIGNAL),
                    candidate=copy.deepcopy(item),
                    surface=surface,
                )
                self.assertEqual(len(result["candidates"]), 1)
                self.assertEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                )
                self.assertEqual(
                    result["weak_source_exact_binding"]["binder_evidence_version"],
                    3,
                )

    def test_evidence_v2_positive_processed_snapshot_is_not_reused(self) -> None:
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
                "binder_evidence_version": 2,
                "binder_implementation": "weak_source_exact_binding_v4",
                "status": "bound_candidate",
                "disposition": "positive_exact_binding",
                "candidate_count": 1,
            }
            reservation.mark_request_started()
            reservation.save_raw_response({"id": "evidence-v2", "status": "completed"})
            reservation.mark_processed(saved)

            common = dict(
                api_key="offline",
                model=MODEL,
                template=TEMPLATE,
                publication_date=DATE,
                search_window=copy.deepcopy(WINDOW),
                missing_total=1,
                maximum_web_search_calls=7,
                existing_candidates=[{"title": "existing", "recommendation": "include"}],
                archive={"items": []},
                prior_plan=copy.deepcopy(plan),
            )
            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage,
                    "run_audit_request",
                    side_effect=AssertionError("stale processed evidence must not run ordinary search"),
                ) as ordinary,
                mock.patch.object(
                    coverage,
                    "protected_policy_audit_request",
                    side_effect=AssertionError("stale processed evidence must not retry paid search"),
                ) as protected,
                mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
                mock.patch.object(
                    coverage,
                    "_p3b_signals",
                    return_value=[copy.deepcopy(SIGNAL)],
                ),
                mock.patch.object(
                    coverage._source_freshness,
                    "fetch_source_html",
                    side_effect=AssertionError("stale processed evidence must not refetch page"),
                ) as pages,
            ):
                result = coverage.execute_audit_plan(**common)

            self.assertEqual(ordinary.call_count, 0)
            self.assertEqual(protected.call_count, 0)
            self.assertEqual(pages.call_count, 0)
            self.assertEqual(result.get("candidates"), [])
            self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
            self.assertIn("predates", result["weak_source_exact_binding"]["reason"])
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)


if __name__ == "__main__":
    unittest.main()
