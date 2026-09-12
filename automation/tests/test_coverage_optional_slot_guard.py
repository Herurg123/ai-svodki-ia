from __future__ import annotations

import copy
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coverage = load("coverage_optional_slot_test", "ensure_story_coverage.py")
slot_guard = sys.modules["coverage_slot_guard"]


SIGNAL = {
    "signal_id": "sig-business_investment_partnerships-02",
    "status": "unresolved",
    "title": "Rillet Lands $100M to Scale AI ERP",
    "origin_direction": "business_investment_partnerships",
    "reason_code": "unverified",
    "evidence_reason": "Fresh high-signal evidence could not be directly verified.",
    "likely_significance_score": 4,
    "entities": ["Rillet", "Lands", "Scale", "ERP"],
    "anchors": ["$100M"],
    "resolution_required": True,
}

OUTSIDE_WINDOW = {
    "title": "Rillet Raises $100M Series C at $1B Valuation",
    "url": "https://example.com/rillet",
    "reason_code": "outside_window",
    "reason": "The event predates the saved window.",
}

WINDOW = {
    "start_at": "2026-08-23T09:07:30+03:00",
    "end_at": "2026-08-25T04:43:30+03:00",
}


def mandatory_attempts() -> list[dict]:
    return [
        {
            "direction_id": direction,
            "attempt": 1,
            "status": "checked",
            "api": {
                "status": "completed",
                "response_id": f"resp-{direction}",
                "web_search_calls_completed": 1,
                "web_search_call_items_total": 1,
            },
        }
        for direction in coverage.AUDIT_DIRECTION_IDS
    ]


def base_plan() -> dict:
    return {
        "publication_date": "2026-08-25",
        "audit_status": "complete",
        "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
        "attempts": mandatory_attempts(),
        "candidates": [],
        "search_budget": {
            "maximum_calls": 7,
            "completed_calls": 6,
            "remaining_calls": 1,
        },
    }


class FakeResponses:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **_kwargs):
        self.owner.calls += 1
        raise RuntimeError("simulated connection loss after admission")


class FakeOpenAI:
    instances: list["FakeOpenAI"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = 0
        self.responses = FakeResponses(self)
        self.__class__.instances.append(self)


class CoverageOptionalSlotGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeOpenAI.instances.clear()

    def _run(self, state_dir: Path, *, plan: dict | None = None):
        original_state = coverage.STATE_DIR
        original_call_with_usage = coverage._runtime.call_with_usage
        try:
            coverage.STATE_DIR = state_dir
            coverage._runtime.call_with_usage = lambda _stage, fn, **kwargs: fn(**kwargs)
            with mock.patch.dict(sys.modules, {"openai": types.SimpleNamespace(OpenAI=FakeOpenAI)}):
                return coverage._run_resolution(
                    plan=copy.deepcopy(plan or base_plan()),
                    signals=[dict(SIGNAL)],
                    api_key="unused-test-key",
                    model="gpt-5.6-terra",
                    search_window=dict(WINDOW),
                    archive={"items": []},
                    maximum_web_search_calls=7,
                )
        finally:
            coverage.STATE_DIR = original_state
            coverage._runtime.call_with_usage = original_call_with_usage

    def test_reservation_write_failure_prevents_transport(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw)
            with mock.patch.object(
                slot_guard, "_atomic_write_json", side_effect=OSError("disk full")
            ):
                result = self._run(state_dir)
            self.assertEqual(FakeOpenAI.instances, [])
            self.assertEqual(result["audit_status"], "partial")
            self.assertIn("reservation failure", result["retrieval_quality"]["reason"])
            self.assertFalse(slot_guard.journal_path(state_dir, "2026-08-25").exists())

    def test_request_started_is_not_retried_and_consumes_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw)
            first = self._run(state_dir)
            self.assertEqual(len(FakeOpenAI.instances), 1)
            self.assertEqual(FakeOpenAI.instances[0].kwargs["max_retries"], 0)
            self.assertEqual(FakeOpenAI.instances[0].calls, 1)
            self.assertEqual(
                slot_guard.journal_state(state_dir, "2026-08-25"),
                "request_started",
            )
            self.assertEqual(first["search_budget"]["remaining_calls"], 0)
            self.assertEqual(first["search_budget"]["effective_consumed_calls"], 7)
            self.assertEqual(
                first["attempts"][-1]["search_operation_count_contribution"], 1
            )

            second = self._run(state_dir)
            self.assertEqual(len(FakeOpenAI.instances), 1, "second wire call is forbidden")
            self.assertEqual(second["search_budget"]["remaining_calls"], 0)
            self.assertIn("automatic retry forbidden", second["retrieval_quality"]["reason"])

    def test_saved_response_replays_offline_after_interruption(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw)
            original_state = coverage.STATE_DIR
            original_transport = coverage.protected_policy_audit_request
            calls = {"transport": 0}

            def save_then_interrupt(runtime, reservation, **_kwargs):
                calls["transport"] += 1
                reservation.mark_request_started()
                reservation.save_raw_response({"id": "resp-saved"})
                snapshot = {
                    "payload": {
                        "status": "complete_with_gaps",
                        "direction_id": "general_coverage_gaps",
                        "candidates": [],
                        "rejections": [dict(OUTSIDE_WINDOW)],
                        "notes": "saved before interruption",
                    },
                    "metadata": {
                        "response_id": "resp-saved",
                        "status": "completed",
                        "actual_queries": ["Rillet Lands Scale ERP latest"],
                        "consulted_sources": [],
                        "web_search_calls": 1,
                        "web_search_calls_completed": 1,
                        "web_search_call_items_total": 1,
                    },
                    "output_text": "{}",
                    "validation_error": None,
                }
                reservation.save_result_snapshot(snapshot)
                raise KeyboardInterrupt("crash after durable response")

            try:
                coverage.STATE_DIR = state_dir
                coverage.protected_policy_audit_request = save_then_interrupt
                with self.assertRaises(KeyboardInterrupt):
                    coverage._run_resolution(
                        plan=base_plan(),
                        signals=[dict(SIGNAL)],
                        api_key="unused-test-key",
                        model="gpt-5.6-terra",
                        search_window=dict(WINDOW),
                        archive={"items": []},
                        maximum_web_search_calls=7,
                    )
                self.assertEqual(
                    slot_guard.journal_state(state_dir, "2026-08-25"),
                    "response_saved",
                )

                coverage.protected_policy_audit_request = lambda *_a, **_k: self.fail(
                    "offline replay must not call transport"
                )
                replayed = coverage._run_resolution(
                    plan=base_plan(),
                    signals=[dict(SIGNAL)],
                    api_key="unused-test-key",
                    model="gpt-5.6-terra",
                    search_window=dict(WINDOW),
                    archive={"items": []},
                    maximum_web_search_calls=7,
                )
            finally:
                coverage.STATE_DIR = original_state
                coverage.protected_policy_audit_request = original_transport

            self.assertEqual(calls["transport"], 1)
            self.assertEqual(
                slot_guard.journal_state(state_dir, "2026-08-25"),
                "processed",
            )
            self.assertEqual(replayed["search_budget"]["remaining_calls"], 0)
            self.assertEqual(replayed["retrieval_quality"]["status"], "complete")

    def test_legacy_spent_resolution_attempt_is_not_refunded_to_six(self) -> None:
        attempts = mandatory_attempts()
        attempts.append(
            {
                "direction_id": "general_coverage_gaps",
                "attempt": 2,
                "status": "checked_with_gaps",
                "search_strategy": coverage.UNRESOLVED_RESOLUTION_STRATEGY,
                "unresolved_resolution_version": 1,
                "signal_ids": [SIGNAL["signal_id"]],
                "candidates": [],
                "rejections": [],
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
            "retrieval_quality": {"status": "degraded", "required_signal_count": 1},
        }
        prepared = coverage._prepare_prior_for_quality(prior, None)
        self.assertIsNotNone(prepared)
        self.assertEqual(len(prepared["attempts"]), 7)
        self.assertEqual(prepared["search_budget"]["remaining_calls"], 0)
        self.assertEqual(prepared["search_budget"]["effective_consumed_calls"], 7)
        self.assertEqual(
            prepared["attempts"][-1]["search_operation_count_contribution"], 1
        )


if __name__ == "__main__":
    unittest.main()
