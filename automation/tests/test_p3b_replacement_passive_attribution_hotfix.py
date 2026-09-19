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

DATE = controls.DATE
MODEL = controls.MODEL
WINDOW = controls.WINDOW
TEMPLATE = controls.TEMPLATE
SIGNAL = controls.SIGNAL


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
        "model": MODEL,
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



class P3bReplacementPassiveAttributionHotfixTests(unittest.TestCase):
    def test_active_binder_evidence_version_is_6(self) -> None:
        self.assertIs(coverage._exact_binding, binder)
        self.assertEqual(binder.EVIDENCE_VERSION, 6)
        self.assertEqual(coverage.P3B_BINDER_EVIDENCE_VERSION, 6)
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
            "DeepSeek says V4 Pro was replaced by V4.1 Flash, (by OpenAI)",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash - by OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash – by OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash — by OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash ((by OpenAI))",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash: — by OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek's rival OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek rival OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek and OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek / OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek-owned OpenAI",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek's OpenAI team",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by DeepSeek, OpenAI and Anthropic",
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
                self.assertEqual(
                    result["weak_source_exact_binding"]["candidate_count"],
                    0,
                )
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
        result = second.process_candidate(
            signal=copy.deepcopy(SIGNAL),
            candidate=controls.candidate(),
            surface=surface,
        )
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["weak_source_exact_binding"]["candidate_count"], 0)
        self.assertNotEqual(
            result["weak_source_exact_binding"]["status"],
            "bound_candidate",
        )

    def test_current_claim_survives_historical_foreign_attribution_with_full_date(self) -> None:
        surface = (
            "DeepSeek replaces V4 Pro with V4.1 Flash. "
            "DeepSeek says V4 Pro was replaced by V4.1 Flash by OpenAI on September 1, 2025."
        )
        self.assertEqual(
            binder.exact_event_identity(surface, SIGNAL),
            (True, "exact_event_identity"),
        )
        result = second.process_candidate(
            signal=copy.deepcopy(SIGNAL),
            candidate=controls.candidate(),
            surface=surface,
        )
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(
            result["weak_source_exact_binding"]["status"],
            "bound_candidate",
        )

    def test_replacement_positive_controls_remain_positive(self) -> None:
        item = controls.candidate()
        surfaces = (
            "DeepSeek replaces V4 Pro with V4.1 Flash",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash",
            "V4 Pro was replaced by V4.1 Flash by DeepSeek",
            "V4 Pro was replaced by V4.1 Flash by deepseek",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash (by DeepSeek)",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash: by DeepSeek",
            "DeepSeek says V4 Pro was replaced by V4.1 Flash: availability starts today",
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
                    6,
                )

    def test_passive_launch_update_require_exact_agent_identity(self) -> None:
        launch_signal = second.launch_signal()
        launch_item = second.launch_candidate()

        update_signal = second.update_signal()
        update_item = second.launch_candidate()
        update_item["title"] = "DeepSeek updates V4.1 Flash from 32K to 64K context"
        update_item["event_type"] = "update"
        update_item["event_summary"] = update_item["title"]
        update_item["primary_source"] = {
            "title": update_item["title"],
            "publisher": "DeepSeek",
            "url": "https://www.deepseek.com/en/news/v4-context-64k/",
        }

        cases = (
            (
                launch_signal,
                launch_item,
                "V4.1 Flash was launched by DeepSeek",
                (
                    "V4.1 Flash was launched by DeepSeek's rival OpenAI",
                    "V4.1 Flash was launched by DeepSeek, OpenAI and Anthropic",
                ),
            ),
            (
                update_signal,
                update_item,
                "V4.1 Flash was updated by deepseek",
                (
                    "V4.1 Flash was updated by DeepSeek and OpenAI",
                    "V4.1 Flash was updated by DeepSeek, OpenAI and Anthropic",
                ),
            ),
        )
        for signal, item, positive_surface, negative_surfaces in cases:
            with self.subTest(signal=signal["title"], surface=positive_surface):
                self.assertEqual(
                    binder.exact_event_identity(positive_surface, signal),
                    (True, "exact_event_identity"),
                )
                positive = second.process_candidate(
                    signal=copy.deepcopy(signal),
                    candidate=copy.deepcopy(item),
                    surface=positive_surface,
                )
                self.assertEqual(len(positive["candidates"]), 1)
                self.assertEqual(
                    positive["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                )

            for negative_surface in negative_surfaces:
                with self.subTest(signal=signal["title"], surface=negative_surface):
                    self.assertEqual(
                        binder.exact_event_identity(negative_surface, signal),
                        (False, "organization_event_attribution_mismatch"),
                    )
                    negative = second.process_candidate(
                        signal=copy.deepcopy(signal),
                        candidate=copy.deepcopy(item),
                        surface=negative_surface,
                    )
                    self.assertEqual(negative["candidates"], [])
                    self.assertEqual(
                        negative["weak_source_exact_binding"]["candidate_count"],
                        0,
                    )
                    self.assertNotEqual(
                        negative["weak_source_exact_binding"]["status"],
                        "bound_candidate",
                    )

    def test_evidence_v2_positive_processed_snapshot_revokes_prior_p3b_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            helper = controls.AstraP3bRuntimeRegressions()
            plan, _ = helper._real_six_plan(state)

            # _real_six_plan deliberately seals its own direct-control budget at 6.
            # Reconstruct the historical P3b pre-call state without running the
            # legacy seventh-slot resolver: six mandatory calls are consumed and
            # exactly one already-existing optional Coverage slot is available.
            budget = plan["search_budget"]
            self.assertEqual(budget["completed_calls"], 6)
            budget["maximum_calls"] = 7
            budget["reserved_or_spent_calls"] = 0
            budget["effective_consumed_calls"] = 6
            budget["remaining_calls"] = 1
            budget["exhausted"] = False
            budget["search_budget_exhausted"] = False
            budget.pop("stop_reason", None)

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
            raw_response = _raw_response("evidence-v2")
            reservation.save_raw_response(raw_response)
            _parsed, result_snapshot = coverage.replay_raw_response(
                coverage._runtime,
                raw_response,
                maximum_web_search_calls=1,
            )
            reservation.save_result_snapshot(result_snapshot)
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
