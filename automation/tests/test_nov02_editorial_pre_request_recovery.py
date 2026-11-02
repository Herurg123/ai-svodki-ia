"""Regressions: the closed 2026-11-02 repair exceptions are no longer active.

Historical error shapes remain as offline negative fixtures; never allow
automatic repeat-editorial admission for a legacy 'pending' record merely
because it resembles the incident. The generic proven missing-SDK
pre-request path and durable journal-bound recovery remain active.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import editorial_repair_guard as guard


DATE = "2026-11-02"
REQUIRED = [
    "security_world", "security_russia", "security_asia",
    "legal_copyright_scraping", "curiosity", "general_coverage_gaps",
]
ZERO_ERROR = (
    "RuntimeError: После основного и дополнительного поиска "
    "не осталось ни одного достойного сюжета"
)
GUARD_ERROR = (
    "EditorialRepairError: legacy repair is pending but provider "
    "admission is ambiguous; automatic retry forbidden"
)


def historical_pending_report(*, guard_block: bool = False) -> dict:
    report = {
        "publication_date": DATE,
        "status": "error",
        "error": GUARD_ERROR if guard_block else ZERO_ERROR,
        "initial_artifact_mode": "partial_editorial",
        "audit_status": "complete_with_gaps",
        "audit_state": "not_started" if guard_block else "completed_usable",
        "audit_error": None,
        "validation_error": None,
        "editorial_repair_guard": None,
        "editorial_completion_required": True,
        "editorial_completion_performed": False,
        "editorial_rerun_required": guard_block,
        "editorial_rerun_performed": False,
        "web_search_performed": True,
        "api": {"status": "completed", "web_search_calls": 6},
        "required_directions": REQUIRED[:],
        "checked_directions": REQUIRED[:],
        "candidate_pool_before": {"total": 0, "world": 0, "russia": 0},
        "candidate_pool_after": {"total": int(guard_block)},
        "accepted_candidates": [],
    }
    if guard_block:
        report["accepted_candidates"] = [{
            "title": "OpenAI готовит объединение ChatGPT Work с Chat",
            "published_date": "2026-11-01",
            "time_precision": "date",
        }]
    return report


class RetiredNovember2RecoveryTests(unittest.TestCase):
    def test_original_zero_pool_cannot_authorize_new_legacy_retry(self):
        report = historical_pending_report()
        self.assertTrue(guard._legacy_pending(report))
        self.assertIsNone(guard._legacy_pre_request_reason(report))
        self.assertFalse(guard._legacy_safe_pre_request_failure(report))

    def test_recovered_zero_pool_before_finalizer_cannot_authorize(self):
        report = historical_pending_report()
        report["audit_state"] = "not_started"
        self.assertIsNone(guard._legacy_pre_request_reason(report))

    def test_guard_rejection_with_exact_chat_work_identity_cannot_authorize(self):
        report = historical_pending_report(guard_block=True)
        self.assertTrue(guard._legacy_pending(report))
        self.assertIsNone(guard._legacy_pre_request_reason(report))
        self.assertFalse(guard._legacy_safe_pre_request_failure(report))

    def test_arbitrary_unknown_provider_outcome_remains_blocked(self):
        report = historical_pending_report(guard_block=True)
        for error in (
            GUARD_ERROR,
            ZERO_ERROR,
            "connection reset after sending provider request",
            "editorial response unknown",
        ):
            with self.subTest(error=error):
                report["error"] = error
                self.assertIsNone(guard._legacy_pre_request_reason(report))

    def test_proven_missing_sdk_remains_safe_before_request(self):
        report = historical_pending_report(guard_block=True)
        report["editorial_repair_error"] = "ModuleNotFoundError: No module named 'openai'"
        self.assertEqual(
            guard._legacy_pre_request_reason(report),
            "proven_pre_request_missing_openai_sdk",
        )
        self.assertTrue(guard._legacy_safe_pre_request_failure(report))

    def test_prepare_required_rejects_retired_incidents_before_journal(self):
        for guard_block, audit_state in (
            (False, "completed_usable"),
            (False, "not_started"),
            (True, "not_started"),
        ):
            with self.subTest(guard_block=guard_block, audit_state=audit_state):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    state, artifact = root / "state", root / "artifact"
                    state.mkdir()
                    artifact.mkdir()
                    persisted, archive = root / "merged.json", root / "archive.json"
                    persisted.write_text(
                        json.dumps({
                            "publication_date": DATE,
                            "candidates": [{"id": "cand-001"}],
                            "search_window": {
                                "start_at": "2026-10-31T05:06:28+03:00"
                            },
                        }),
                        encoding="utf-8",
                    )
                    archive.write_text('{"items": []}', encoding="utf-8")
                    report = historical_pending_report(guard_block=guard_block)
                    report["audit_state"] = audit_state
                    (state / "coverage-audit.json").write_text(
                        json.dumps(report), encoding="utf-8"
                    )
                    with self.assertRaisesRegex(
                        guard.EditorialRepairError,
                        "provider admission is ambiguous",
                    ):
                        guard.prepare_required(
                            publication_date=DATE,
                            state_dir=state,
                            persisted_research_path=persisted,
                            archive_path=archive,
                            artifact_dir=artifact,
                            model="gpt-5.6-terra",
                            legacy_report_path=state / "coverage-audit.json",
                        )
                    self.assertFalse(
                        (state / f"editorial-repair-{DATE}.json").exists()
                    )


if __name__ == "__main__":
    unittest.main()
