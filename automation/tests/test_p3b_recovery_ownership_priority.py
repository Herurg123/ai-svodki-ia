from __future__ import annotations

import copy
import sys
import tempfile
import types
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

    def test_required_unverified_preempts_only_unstarted_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            plan = self._six_mandatory_plan(state)
            reservation = self._reservation(state, plan)
            self.assertEqual(reservation.state, "reserved")

            required = [{
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
            }]
            optional_prompts: list[str] = []

            def required_transport(runtime, slot, **kwargs):
                prompt = str(kwargs.get("prompt") or "")
                optional_prompts.append(prompt)
                slot.mark_request_started()
                raw_response = {"id": "offline-required-resolution", "status": "completed"}
                slot.save_raw_response(raw_response)
                payload = {
                    "status": "complete_with_gaps",
                    "direction_id": "general_coverage_gaps",
                    "candidates": [],
                    "rejections": [],
                    "notes": "offline required-priority control",
                }
                metadata = {
                    "response_id": "offline-required-resolution",
                    "status": "completed",
                    "actual_queries": ["Rillet $100M latest"],
                    "consulted_sources": [],
                    "web_search_calls": 1,
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                }
                slot.save_result_snapshot({
                    "payload": copy.deepcopy(payload),
                    "metadata": copy.deepcopy(metadata),
                    "output_text": "{}",
                    "validation_error": None,
                })
                return types.SimpleNamespace(payload=payload, metadata=metadata)

            p3a_module = coverage._impl._v2._v1._p3a
            with (
                mock.patch.object(coverage, "STATE_DIR", state),
                mock.patch.object(coverage._pre, "_required_signals", return_value=required),
                mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(SIGNAL)]),
                mock.patch.object(coverage, "protected_policy_audit_request", side_effect=required_transport),
                mock.patch.object(p3a_module, "protected_policy_audit_request", side_effect=required_transport),
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

            self.assertEqual(len(optional_prompts), 1)
            self.assertIn("Rillet", optional_prompts[0])
            self.assertNotIn("DeepSeek V4 Pro V4.1 Flash", optional_prompts[0])
            self.assertEqual(coverage.load_journal(state, DATE)["state"], "processed")
            self.assertEqual(result["search_budget"]["completed_calls"], 7)
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)
            self.assertEqual(result["weak_source_exact_binding"]["status"], "deferred")
            self.assertIn("slot priority", result["weak_source_exact_binding"]["reason"])


if __name__ == "__main__":
    unittest.main()
