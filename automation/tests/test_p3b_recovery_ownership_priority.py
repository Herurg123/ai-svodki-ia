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

import test_p3b_astra_regressions as controls

coverage = controls.coverage
DATE = controls.DATE
MODEL = controls.MODEL
WINDOW = controls.WINDOW
SIGNAL = controls.SIGNAL
TEMPLATE = controls.TEMPLATE


class P3bRecoveryOwnershipPriorityTests(unittest.TestCase):
    def _six_mandatory_plan(self, state: Path) -> dict:
        calls: list[dict] = []

        def mandatory_transport(**kwargs):
            calls.append(kwargs)
            return controls.mandatory_success(
                controls.direction_from_prompt(str(kwargs["prompt"]))
            )

        with (
            mock.patch.object(coverage, "STATE_DIR", state),
            mock.patch.object(coverage, "run_audit_request", side_effect=mandatory_transport),
            mock.patch.dict(
                coverage._runtime._BASE_EXECUTE_AUDIT_PLAN.__globals__,
                {"run_audit_request": mandatory_transport},
            ),
            mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
        ):
            plan = coverage._P3A_EXECUTE_AUDIT_PLAN(
                api_key="offline",
                model=MODEL,
                template=TEMPLATE,
                publication_date=DATE,
                search_window=copy.deepcopy(WINDOW),
                missing_total=7,
                maximum_web_search_calls=6,
                existing_candidates=[],
                archive={"items": []},
            )

        self.assertEqual(len(calls), 6)
        self.assertEqual(set(plan["checked_directions"]), set(coverage.AUDIT_DIRECTION_IDS))
        return plan

    def _reservation(self, state: Path, plan: dict):
        return controls.AstraP3bRuntimeRegressions()._reservation(state, plan)

    def _save_empty_p3b_response(self, reservation) -> None:
        query = coverage.build_p3b_query(SIGNAL)
        reservation.mark_request_started()
        reservation.save_raw_response({"id": "offline-owned-seventh", "status": "completed"})
        reservation.save_result_snapshot(
            {
                "payload": {"status": "complete_with_gaps", "candidates": [], "rejections": []},
                "metadata": {
                    "response_id": "offline-owned-seventh",
                    "status": "completed",
                    "actual_queries": [query],
                    "consulted_sources": [],
                    "web_search_calls": 1,
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                },
                "output_text": "{}",
                "validation_error": None,
            }
        )

    @staticmethod
    def _required_signal() -> dict:
        return {
            "signal_id": "required-rillet",
            "status": "unresolved",
            "title": "Rillet Lands $100M to Scale AI ERP",
            "origin_direction": "business_investment_partnerships",
            "reason_code": "unverified",
            "evidence_reason": "Unverified funding round",
            "likely_significance_score": 4,
            "entities": ["Rillet"],
            "anchors": ["$100M"],
            "resolution_required": True,
        }

    def test_existing_saved_slot_blocks_fresh_optional_search_across_context_mismatch(self) -> None:
        cases = {
            "changed_model": {
                "model": "other-model",
                "archive": {"items": []},
                "signals": [copy.deepcopy(SIGNAL)],
            },
            "missing_signal": {
                "model": MODEL,
                "archive": {"items": []},
                "signals": [],
            },
            "changed_archive": {
                "model": MODEL,
                "archive": {
                    "items": [{
                        "date": "2026-09-10",
                        "stories": [{
                            "headline": "Another published AI event",
                            "organization": "Other",
                            "event_type": "release",
                        }],
                        "source_urls": ["https://example.org/news"],
                    }]
                },
                "signals": [copy.deepcopy(SIGNAL)],
            },
        }

        for name, case in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as raw:
                state = Path(raw)
                plan = self._six_mandatory_plan(state)
                reservation = self._reservation(state, plan)
                self._save_empty_p3b_response(reservation)
                new_calls: list[str] = []

                def forbidden_optional(**kwargs):
                    new_calls.append(str(kwargs.get("prompt") or ""))
                    return controls.mandatory_success("general_coverage_gaps")

                with (
                    mock.patch.object(coverage, "STATE_DIR", state),
                    mock.patch.object(coverage, "run_audit_request", side_effect=forbidden_optional),
                    mock.patch.dict(
                        coverage._runtime._BASE_EXECUTE_AUDIT_PLAN.__globals__,
                        {"run_audit_request": forbidden_optional},
                    ),
                    mock.patch.object(
                        coverage,
                        "protected_policy_audit_request",
                        side_effect=AssertionError("saved optional slot must not trigger a fresh provider call"),
                    ),
                    mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
                    mock.patch.object(coverage, "_p3b_signals", return_value=case["signals"]),
                ):
                    result = coverage.execute_audit_plan(
                        api_key="offline",
                        model=case["model"],
                        template=TEMPLATE,
                        publication_date=DATE,
                        search_window=copy.deepcopy(WINDOW),
                        missing_total=7,
                        maximum_web_search_calls=7,
                        existing_candidates=[],
                        archive=copy.deepcopy(case["archive"]),
                        prior_plan=copy.deepcopy(plan),
                    )

                self.assertEqual(new_calls, [])
                self.assertEqual(coverage.load_journal(state, DATE)["state"], "response_saved")
                budget = result["search_budget"]
                self.assertEqual(budget["maximum_calls"], 7)
                self.assertEqual(budget["remaining_calls"], 0)
                self.assertEqual(budget["effective_consumed_calls"], 7)

    def test_required_unverified_preempts_proven_unstarted_p3b_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            plan = self._six_mandatory_plan(state)
            reservation = self._reservation(state, plan)
            self.assertEqual(reservation.state, "reserved")
            required = [self._required_signal()]
            delegated_calls: list[dict] = []
            handoff_calls: list[dict] = []
            active_v2 = coverage._impl._v2
            original_v2_sync = active_v2._sync_p3b_public_hooks

            def fake_p3a_execute(*args, **kwargs):
                delegated_calls.append(dict(kwargs))
                self.assertIsNone(coverage.load_journal(state, DATE))
                return copy.deepcopy(plan)

            def fake_handoff(
                current_plan,
                *,
                required_signals,
                kwargs,
                original_maximum,
                original_recalculate,
            ):
                handoff_calls.append({
                    "signals": copy.deepcopy(required_signals),
                    "original_maximum": original_maximum,
                })
                self.assertIsNone(coverage.load_journal(state, DATE))
                return copy.deepcopy(current_plan)

            def sync_then_install_required_probe() -> None:
                original_v2_sync()
                active_v2._v1._P3A_EXECUTE_AUDIT_PLAN = fake_p3a_execute

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(coverage._pre, "_required_signals", return_value=required),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(SIGNAL)]),
                mock.patch.object(
                    active_v2,
                    "_sync_p3b_public_hooks",
                    side_effect=sync_then_install_required_probe,
                ),
                mock.patch.object(
                    coverage._impl,
                    "_run_handed_off_required_legacy",
                    side_effect=fake_handoff,
                ),
                mock.patch.object(
                    coverage._impl,
                    "_V2_RUN_P3B_BINDING",
                    side_effect=AssertionError("P3b must not run ahead of required unverified resolution"),
                ),
            ):
                result = coverage.execute_audit_plan(
                    api_key="offline",
                    model=MODEL,
                    template=TEMPLATE,
                    publication_date=DATE,
                    search_window=copy.deepcopy(WINDOW),
                    missing_total=7,
                    maximum_web_search_calls=7,
                    existing_candidates=[],
                    archive={"items": []},
                    prior_plan=copy.deepcopy(plan),
                )

            self.assertEqual(len(delegated_calls), 1)
            self.assertEqual(delegated_calls[0]["maximum_web_search_calls"], 6)
            self.assertEqual(len(handoff_calls), 1)
            self.assertEqual(handoff_calls[0]["original_maximum"], 7)
            self.assertEqual(handoff_calls[0]["signals"], required)
            self.assertIsNone(coverage.load_journal(state, DATE))
            self.assertNotEqual(
                result.get("weak_source_exact_binding", {}).get("status"),
                "bound_candidate",
            )

    def test_required_does_not_delete_unidentified_reserved_intent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            plan = self._six_mandatory_plan(state)
            reservation = self._reservation(state, plan)
            original_journal = coverage.load_journal(state, DATE)
            self.assertIsNotNone(original_journal)
            delegated_maxima: list[int] = []

            def fail_closed_delegate(*args, **kwargs):
                delegated_maxima.append(int(kwargs.get("maximum_web_search_calls", 0) or 0))
                current = coverage.load_journal(state, DATE)
                self.assertEqual(current, original_journal)
                return copy.deepcopy(plan)

            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(
                    coverage._pre,
                    "_required_signals",
                    return_value=[self._required_signal()],
                ),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(SIGNAL)]),
                mock.patch.object(
                    coverage._impl._v3,
                    "execute_audit_plan",
                    side_effect=fail_closed_delegate,
                ),
            ):
                result = coverage.execute_audit_plan(
                    api_key="offline",
                    model="different-model-so-intent-cannot-be-proven",
                    template=TEMPLATE,
                    publication_date=DATE,
                    search_window=copy.deepcopy(WINDOW),
                    missing_total=7,
                    maximum_web_search_calls=7,
                    existing_candidates=[],
                    archive={"items": []},
                    prior_plan=copy.deepcopy(plan),
                )

            self.assertEqual(delegated_maxima, [6])
            self.assertEqual(coverage.load_journal(state, DATE), original_journal)
            self.assertEqual(result["search_budget"]["maximum_calls"], 7)
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)
            self.assertEqual(result["search_budget"]["effective_consumed_calls"], 7)


if __name__ == "__main__":
    unittest.main()
