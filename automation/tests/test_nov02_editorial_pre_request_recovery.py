"""Offline incident regression for saved 2026-11-02 Coverage recovery.

The two report shapes are grounded in original GitHub Actions artifacts:
41375795360 attempt 1 and 41375795360 attempt 2. None of these tests call
the OpenAI API. An unknown provider-admission state must remain fail closed.
"""
from __future__ import annotations

import copy
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


def saved_pre_request_report(*, guard_block: bool = False) -> dict:
    result = {
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
        result["accepted_candidates"] = [
            {
                "title": (
                    "OpenAI начала тестировать объединение ChatGPT Work "
                    "с обычным Chat и общий лимит с Codex"
                ),
                "published_date": "2026-11-01",
                "time_precision": "date",
            }
        ]
    return result


class November2PreRequestEvidenceTests(unittest.TestCase):
    def test_exact_original_zero_pool_is_pre_request(self):
        report = saved_pre_request_report()
        self.assertTrue(guard._legacy_pending(report))
        self.assertEqual(
            guard._legacy_pre_request_reason(report),
            "proven_pre_request_zero_eligible_pool_2026_11_02",
        )

    def test_exact_second_attempt_guard_is_pre_admission(self):
        report = saved_pre_request_report(guard_block=True)
        self.assertEqual(
            guard._legacy_pre_request_reason(report),
            "proven_pre_admission_legacy_guard_2026_11_02",
        )

    def test_unknown_or_incomplete_provider_attempt_stays_blocked(self):
        for field, value in (
            ("error", "OpenAI connection dropped after sending request"),
            ("audit_status", "partial"),
            ("api", {"status": "failed"}),
            ("web_search_performed", False),
            ("editorial_completion_performed", None),
            ("editorial_rerun_performed", None),
            ("initial_artifact_mode", "complete"),
            ("checked_directions", REQUIRED[:-1]),
            ("publication_date", "2026-11-03"),
            ("editorial_repair_guard", {"state": "request_started"}),
            ("audit_error", "provider refused request"),
            ("candidate_pool_before", {"total": 2}),
        ):
            with self.subTest(field=field):
                report = saved_pre_request_report(guard_block=True)
                report[field] = value
                self.assertIsNone(guard._legacy_pre_request_reason(report))

    def test_guard_error_requires_exact_identity_of_accepted_story(self):
        for field, value in (
            ("title", "Northflank reported compromised keys"),
            ("time_precision", "datetime"),
            ("published_date", "2026-10-30"),
        ):
            with self.subTest(field=field):
                report = saved_pre_request_report(guard_block=True)
                report["accepted_candidates"][0][field] = value
                self.assertIsNone(guard._legacy_pre_request_reason(report))

    def test_zero_pool_evidence_cannot_justify_unknown_sent_request(self):
        report = saved_pre_request_report()
        report["editorial_rerun_required"] = True
        self.assertIsNone(guard._legacy_pre_request_reason(report))

    def test_prepare_required_persists_explicit_reason_before_paid_api(self):
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
                    "search_window": {"start_at": "2026-10-31T05:06:28+03:00"},
                }),
                encoding="utf-8",
            )
            archive.write_text('{"items": []}', encoding="utf-8")
            report_path = state / "coverage-audit.json"
            report_path.write_text(
                json.dumps(saved_pre_request_report(guard_block=True)),
                encoding="utf-8",
            )
            context = guard.prepare_required(
                publication_date=DATE,
                state_dir=state,
                persisted_research_path=persisted,
                archive_path=archive,
                artifact_dir=artifact,
                model="gpt-5.6-terra",
                legacy_report_path=report_path,
            )
            journal = json.loads(context.journal_path.read_text(encoding="utf-8"))
            self.assertEqual(journal["state"], "required")
            self.assertTrue(journal["legacy_retry_authorized"])
            self.assertEqual(
                journal["legacy_retry_reason"],
                "proven_pre_admission_legacy_guard_2026_11_02",
            )
            self.assertIsNone(journal["request_sha256"])

    def test_prepare_required_refuses_ambiguous_call_without_journal(self):
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
                    "search_window": {"start_at": "2026-10-31T05:06:28+03:00"},
                }),
                encoding="utf-8",
            )
            archive.write_text('{"items": []}', encoding="utf-8")
            report_path = state / "coverage-audit.json"
            report = saved_pre_request_report(guard_block=True)
            report["error"] = "connection reset after provider request"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaises(guard.EditorialRepairError):
                guard.prepare_required(
                    publication_date=DATE,
                    state_dir=state,
                    persisted_research_path=persisted,
                    archive_path=archive,
                    artifact_dir=artifact,
                    model="gpt-5.6-terra",
                    legacy_report_path=report_path,
                )
            self.assertFalse((state / f"editorial-repair-{DATE}.json").exists())


if __name__ == "__main__":
    unittest.main()
