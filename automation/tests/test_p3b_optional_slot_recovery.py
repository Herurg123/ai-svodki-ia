from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ensure_story_coverage as coverage


DATE = "2026-09-11"


class P3bOptionalSlotRecoveryTests(unittest.TestCase):
    def _plan(self, remaining_calls: int) -> dict:
        attempts = [
            {
                "direction_id": direction_id,
                "attempt": 1,
                "status": "checked_with_gaps",
                "api": {
                    "status": "completed",
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                },
            }
            for direction_id in coverage._pre.AUDIT_DIRECTION_IDS
        ]
        completed = 7 - remaining_calls
        return {
            "status": "ok",
            "publication_date": DATE,
            "audit_status": "complete_with_gaps",
            "audit_state": "completed_usable",
            "checked_directions": list(coverage._pre.AUDIT_DIRECTION_IDS),
            "attempts": attempts,
            "directions": copy.deepcopy(attempts),
            "candidates": [],
            "search_budget": {
                "maximum_calls": 7,
                "minimum_required_calls": 6,
                "completed_calls": completed,
                "remaining_calls": remaining_calls,
                "exhausted": remaining_calls == 0,
                "search_budget_exhausted": remaining_calls == 0,
                "response_attempt_limit_exhausted": False,
                "provider_overrun": False,
            },
            "retrieval_quality_contract_version": coverage._pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
            "retrieval_quality": {
                "version": coverage._pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
                "status": "complete",
            },
        }

    @staticmethod
    def _signal() -> dict:
        return {
            "signal_id": "weak-source-product-deepseek-v4-1-flash",
            "likely_significance_score": 5,
        }

    def _execute(self, *, state: str | None, remaining_calls: int = 0):
        calls: list[str] = []
        journal = None if state is None else {
            "version": 1,
            "publication_date": DATE,
            "state": state,
            "slot_consumed_or_ambiguous": state in {
                "request_started",
                "response_saved",
                "processed",
            },
        }

        def fake_run(**kwargs):
            calls.append(state or "new")
            result = copy.deepcopy(kwargs["plan"])
            result["recovery_probe"] = state or "new"
            return result

        with mock.patch.object(
            coverage, "_P3A_EXECUTE_AUDIT_PLAN", return_value=self._plan(remaining_calls)
        ), mock.patch.object(
            coverage._pre, "_required_signals", return_value=[]
        ), mock.patch.object(
            coverage, "_p3b_signals", return_value=[self._signal()]
        ), mock.patch.object(
            coverage, "load_journal", return_value=journal
        ), mock.patch.object(
            coverage, "_run_p3b_binding", side_effect=fake_run
        ):
            result = coverage.execute_audit_plan(
                publication_date=DATE,
                api_key="unused",
                model="gpt-5.6-terra",
                search_window={},
                archive={},
            )
        return result, calls

    def test_response_saved_replays_even_when_restored_budget_reports_zero(self) -> None:
        result, calls = self._execute(state="response_saved", remaining_calls=0)
        self.assertEqual(calls, ["response_saved"])
        self.assertEqual(result["recovery_probe"], "response_saved")

    def test_processed_snapshot_reuses_even_when_restored_budget_reports_zero(self) -> None:
        result, calls = self._execute(state="processed", remaining_calls=0)
        self.assertEqual(calls, ["processed"])
        self.assertEqual(result["recovery_probe"], "processed")

    def test_request_started_is_resolved_by_durable_guard_before_budget_shortcut(self) -> None:
        result, calls = self._execute(state="request_started", remaining_calls=0)
        self.assertEqual(calls, ["request_started"])
        self.assertEqual(result["recovery_probe"], "request_started")

    def test_zero_budget_without_consumed_journal_cannot_start_new_search(self) -> None:
        result, calls = self._execute(state=None, remaining_calls=0)
        self.assertEqual(calls, [])
        self.assertEqual(result["weak_source_exact_binding"]["status"], "deferred")
        self.assertIn("optional slot is unavailable", result["weak_source_exact_binding"]["reason"])

    def test_reserved_but_unconsumed_slot_does_not_override_zero_runtime_budget(self) -> None:
        result, calls = self._execute(state="reserved", remaining_calls=0)
        self.assertEqual(calls, [])
        self.assertEqual(result["weak_source_exact_binding"]["status"], "deferred")


if __name__ == "__main__":
    unittest.main()
