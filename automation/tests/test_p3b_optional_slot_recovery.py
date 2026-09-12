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
FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "weak-source-signal-retention-2026-09-11.json"
sys.path.insert(0, str(SCRIPTS))

import ensure_story_coverage as coverage
import primary_recall_search as primary

DATE = "2026-09-11"
MODEL = "gpt-5.6-terra"
WINDOW = {
    "start_at": "2026-09-09T00:00:00+00:00",
    "end_at": "2026-09-11T00:00:00+00:00",
}

_fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
SIGNAL = primary.collect_unresolved_signals([
    {
        "direction_id": _fixture["positive_control"]["direction_id"],
        "model_rejections": [_fixture["positive_control"]["rejection"]],
    }
])[0]


class P3bOptionalSlotRecoveryTests(unittest.TestCase):
    def _plan(self, remaining_calls: int) -> dict:
        attempts = [
            {
                "direction_id": direction,
                "attempt": 1,
                "status": "checked_with_gaps",
                "api": {"status": "completed", "web_search_calls_completed": 1, "web_search_call_items_total": 1},
            }
            for direction in coverage._pre.AUDIT_DIRECTION_IDS
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
            "retrieval_quality": {"version": coverage._pre.RETRIEVAL_QUALITY_CONTRACT_VERSION, "status": "complete"},
        }

    def _reservation(self, state_dir: Path, plan: dict):
        query = coverage.build_p3b_query(SIGNAL)
        prompt = coverage.build_p3b_prompt(
            search_window=WINDOW,
            signal=SIGNAL,
            archive=coverage._runtime._compact_recent_archive({"items": []}),
        )
        contract = coverage._request_contract_v2(
            model=MODEL, query=query, prompt=prompt, signal=SIGNAL
        )
        return coverage.prepare_slot(
            state_dir=state_dir,
            publication_date=DATE,
            owner=coverage.P3B_SLOT_OWNER,
            search_window=WINDOW,
            request_contract=contract,
            bundle_identity=coverage._bundle_identity(plan),
        )

    def _execute(self, state_dir: Path, plan: dict):
        with (
            mock.patch.object(coverage, "STATE_DIR", state_dir),
            mock.patch.object(coverage, "_P3A_EXECUTE_AUDIT_PLAN", return_value=copy.deepcopy(plan)),
            mock.patch.object(coverage._pre, "_required_signals", return_value=[]),
            mock.patch.object(coverage, "_p3b_signals", return_value=[copy.deepcopy(SIGNAL)]),
            mock.patch.object(
                coverage,
                "protected_policy_audit_request",
                side_effect=AssertionError("recovery path must not start a new provider request"),
            ) as provider,
        ):
            result = coverage.execute_audit_plan(
                publication_date=DATE,
                api_key="unused",
                model=MODEL,
                search_window=copy.deepcopy(WINDOW),
                archive={"items": []},
                maximum_web_search_calls=7,
            )
        return result, provider.call_count

    def test_request_started_is_ambiguous_and_never_retried(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            plan = self._plan(1)
            reservation = self._reservation(state, plan)
            reservation.mark_request_started()
            result, calls = self._execute(state, plan)
            self.assertEqual(calls, 0)
            self.assertEqual(result["weak_source_exact_binding"]["status"], "indeterminate")
            self.assertEqual(result["weak_source_exact_binding"]["slot_state"], "request_started")
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)
            self.assertEqual(coverage.journal_state(state, DATE), "request_started")

    def test_response_saved_replays_offline_without_provider_or_page_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            plan = self._plan(1)
            reservation = self._reservation(state, plan)
            reservation.mark_request_started()
            reservation.save_raw_response({"id": "resp-p3b-saved", "status": "completed"})
            query = coverage.build_p3b_query(SIGNAL)
            reservation.save_result_snapshot({
                "payload": {
                    "status": "complete_with_gaps",
                    "candidates": [],
                    "rejections": [],
                },
                "metadata": {
                    "response_id": "resp-p3b-saved",
                    "status": "completed",
                    "actual_queries": [query],
                    "consulted_sources": [],
                    "web_search_calls": 1,
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                },
                "output_text": "{}",
                "validation_error": None,
            })
            with mock.patch.object(
                coverage._source_freshness,
                "fetch_source_html",
                side_effect=AssertionError("offline replay must not refetch mutable authoritative page"),
            ):
                result, calls = self._execute(state, plan)
            self.assertEqual(calls, 0)
            self.assertEqual(coverage.journal_state(state, DATE), "processed")
            self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_processed_v2_snapshot_is_reused_at_zero_runtime_budget(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            reservation_plan = self._plan(1)
            reservation = self._reservation(state, reservation_plan)
            reservation.mark_request_started()
            reservation.save_raw_response({"id": "resp-p3b-processed", "status": "completed"})
            saved = self._plan(0)
            saved["weak_source_exact_binding"] = {
                "version": 2,
                "mode": coverage.P3B_MODE,
                "status": "unresolved",
                "reason": "saved hardened result",
            }
            reservation.mark_processed(copy.deepcopy(saved))
            result, calls = self._execute(state, self._plan(0))
            self.assertEqual(calls, 0)
            self.assertEqual(result["weak_source_exact_binding"]["reason"], "saved hardened result")
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_zero_budget_without_journal_cannot_start_new_search(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            result, calls = self._execute(Path(raw), self._plan(0))
            self.assertEqual(calls, 0)
            self.assertEqual(result["weak_source_exact_binding"]["status"], "deferred")
            self.assertIn("optional slot is unavailable", result["weak_source_exact_binding"]["reason"])

    def test_reserved_journal_does_not_override_zero_runtime_budget(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            reservation_plan = self._plan(1)
            self._reservation(state, reservation_plan)
            result, calls = self._execute(state, self._plan(0))
            self.assertEqual(calls, 0)
            self.assertEqual(coverage.journal_state(state, DATE), "reserved")
            self.assertEqual(result["weak_source_exact_binding"]["status"], "deferred")
            self.assertEqual(result["search_budget"]["remaining_calls"], 0)


if __name__ == "__main__":
    unittest.main()
