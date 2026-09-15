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
            "DeepSeek says V4 Pro was replaced by V4.1 Flash: by OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash (by OpenAI)",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash — by OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek's rival OpenAI",
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

    def test_cross_claim_foreign_attribution_vetoes_positive_duplicate(self) -> None:
        surface = (
            "DeepSeek replaces V4 Pro with V4.1 Flash | "
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek's rival OpenAI"
        )
        self.assertEqual(
            binder.exact_event_identity(surface, SIGNAL),
            (False, "organization_event_attribution_mismatch"),
        )

    def test_replacement_positive_controls_remain_positive(self) -> None:
        item = controls.candidate()
        surfaces = (
            "DeepSeek replaces V4 Pro with V4.1 Flash",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash",
            "V4 Pro was replaced by V4.1 Flash by DeepSeek",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash (by DeepSeek)",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash: by DeepSeek",
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

    def test_evidence_v2_positive_processed_snapshot_revokes_prior_p3b_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            mandatory_calls: list[dict] = []

            def fake_mandatory(**kwargs):
                mandatory_calls.append(kwargs)
                return controls.mandatory_success(
                    controls.direction_from_prompt(str(kwargs["prompt"]))
                )

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(coverage, "run_audit_request", side_effect=fake_mandatory),
                mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
            ):
                plan = coverage._P3A_EXECUTE_AUDIT_PLAN(
                    api_key="offline",
                    model=MODEL,
                    template=TEMPLATE,
                    publication_date=DATE,
                    search_window=copy.deepcopy(WINDOW),
                    missing_total=7,
                    maximum_web_search_calls=7,
                    existing_candidates=[],
                    archive={"items": []},
                )

            self.assertEqual(len(mandatory_calls), 6)
            self.assertEqual(plan["search_budget"]["maximum_calls"], 7)
            self.assertEqual(plan["search_budget"]["completed_calls"], 6)
            self.assertEqual(plan["search_budget"]["remaining_calls"], 1)

            helper = controls.AstraP3bRuntimeRegressions()
            reservation = helper._reservation(state, plan)
            saved = copy.deepcopy(plan)
            stale_candidate = controls.candidate()
            stale_candidate["audit_direction"] = "weak_source_exact_binding"
            stale_candidate["resolution_signal_ids"] = [str(SIGNAL.get("signal_id") or "")]
            stale_candidate["p3b_exact_binding_version"] = coverage.P3B_EXACT_BINDING_VERSION
            stale_candidate["p3b_authoritative_page_proof"] = (
                "current-event surface + deterministic Source/Event Freshness"
            )
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
            # Model the complete historical seven-pass result: six mandatory
            # operations plus the already-consumed optional P3b slot.
            coverage._impl._v2._v1._p3b_force_consumed(saved)
            saved_budget = saved["search_budget"]
            self.assertEqual(saved_budget["maximum_calls"], 7)
            self.assertGreaterEqual(
                max(
                    int(saved_budget.get("completed_calls", 0) or 0),
                    int(saved_budget.get("effective_consumed_calls", 0) or 0),
                ),
                7,
            )
            self.assertEqual(saved_budget["remaining_calls"], 0)

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
                prior_plan=copy.deepcopy(saved),
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
            self.assertFalse(
                any(
                    isinstance(item, dict)
                    and item.get("audit_direction") == "weak_source_exact_binding"
                    for item in result.get("candidates") or []
                )
            )
            self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
            self.assertEqual(result["weak_source_exact_binding"]["candidate_count"], 0)
            self.assertIn("predates", result["weak_source_exact_binding"]["reason"])
            result_budget = result["search_budget"]
            self.assertGreaterEqual(
                max(
                    int(result_budget.get("completed_calls", 0) or 0),
                    int(result_budget.get("effective_consumed_calls", 0) or 0),
                ),
                7,
            )
            self.assertEqual(result_budget["remaining_calls"], 0)


if __name__ == "__main__":
    unittest.main()
