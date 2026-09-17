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
sys.path.insert(0, str(SCRIPTS))

from coverage_slot_guard import CoverageSlotError, prepare_slot
import ensure_story_coverage_p3b_v7 as v7

DATE = "2026-09-17"
FOREIGN_DATE = "2026-09-16"
SIGNAL_ID = "current-p3b-signal"
SEARCH_WINDOW = {
    "start_at": "2026-09-16T03:00:00+00:00",
    "end_at": "2026-09-17T03:00:00+00:00",
}


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _plan(publication_date: str, *, response_id: str) -> dict:
    return {
        "publication_date": publication_date,
        "search_window": copy.deepcopy(SEARCH_WINDOW),
        "checked_directions": list(v7.AUDIT_DIRECTION_IDS),
        "attempts": [
            {
                "direction_id": v7.AUDIT_DIRECTION_IDS[0],
                "actual_queries": ["bundle identity control query"],
                "candidate_count": 0,
                "filtered_quality": {},
                "api": {"response_id": response_id},
            }
        ],
        "candidates": [],
        "search_budget": {
            "maximum_calls": 7,
            "completed_calls": 7,
            "remaining_calls": 0,
        },
    }


def _current_snapshot(plan: dict, *, candidate_id: str) -> dict:
    snapshot = copy.deepcopy(plan)
    snapshot["candidates"] = [
        {
            "id": candidate_id,
            "title": "Foreign current-shape P3b candidate",
            "audit_direction": "weak_source_exact_binding",
            "resolution_signal_ids": [SIGNAL_ID],
            "p3b_exact_binding_version": v7.P3B_EXACT_BINDING_VERSION,
            "p3b_authoritative_page_url": "https://example.com/foreign-current-p3b",
            "p3b_authoritative_page_proof": (
                "current-event surface + deterministic Source/Event Freshness"
            ),
            "primary_source": {
                "title": "Foreign current-shape P3b candidate",
                "publisher": "Example",
                "url": "https://example.com/foreign-current-p3b",
            },
        }
    ]
    snapshot["weak_source_exact_binding"] = {
        "version": v7.P3B_EXACT_BINDING_VERSION,
        "mode": v7.P3B_MODE,
        "signal_id": SIGNAL_ID,
        "status": "bound_candidate",
        "disposition": "positive_exact_binding",
        "candidate_count": 1,
        "binder_evidence_version": v7.P3B_BINDER_EVIDENCE_VERSION,
        "binder_implementation": "weak_source_exact_binding_v4",
    }
    return snapshot


class P3bV7ProcessedSnapshotIdentityTests(unittest.TestCase):
    def _assert_foreign_snapshot_rejected(
        self, *, current_plan: dict, foreign_snapshot: dict
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "production-daily"
            artifact = root / DATE
            report = state / "coverage-audit.json"
            journal_path = state / f"coverage-optional-slot-{DATE}.json"
            state.mkdir(parents=True)
            artifact.mkdir(parents=True)

            _write(artifact / "candidates.json", current_plan)
            reservation = prepare_slot(
                state_dir=state,
                publication_date=DATE,
                owner=v7.P3B_SLOT_OWNER,
                search_window=SEARCH_WINDOW,
                request_contract={
                    "version": v7.P3B_EXACT_BINDING_VERSION,
                    "strategy": v7.P3B_SLOT_OWNER,
                    "model": "gpt-test",
                    "query": "current exact query",
                    "prompt_sha256": "fixture-prompt",
                    "signal_ids": [SIGNAL_ID],
                    "maximum_web_search_calls": 1,
                    "allowed_domains": [],
                },
                bundle_identity=v7._v6._P3A._bundle_identity(current_plan),
            )
            reservation.mark_request_started()
            reservation.save_raw_response({"id": "saved-response", "output": []})
            reservation.mark_processed(foreign_snapshot)
            before = journal_path.read_bytes()

            with (
                mock.patch.object(
                    v7._v6,
                    "run_audit_request",
                    side_effect=AssertionError("provider call"),
                ) as ordinary,
                mock.patch.object(
                    v7._v6,
                    "protected_policy_audit_request",
                    side_effect=AssertionError("retry/protected call"),
                ) as protected,
                mock.patch.object(
                    v7._v6._source_freshness,
                    "fetch_source_html",
                    side_effect=AssertionError("page fetch"),
                ) as pages,
            ):
                with self.assertRaises(CoverageSlotError):
                    v7.recovery_preflight(
                        publication_date=DATE,
                        artifact_dir=artifact,
                        report_path=report,
                        state_dir=state,
                    )

            self.assertEqual(
                (ordinary.call_count, protected.call_count, pages.call_count),
                (0, 0, 0),
            )
            self.assertEqual(journal_path.read_bytes(), before)

    def test_foreign_date_processed_snapshot_fails_closed_without_io_or_mutation(self) -> None:
        current_plan = _plan(DATE, response_id="bundle-a")
        foreign_plan = _plan(FOREIGN_DATE, response_id="bundle-a")
        self._assert_foreign_snapshot_rejected(
            current_plan=current_plan,
            foreign_snapshot=_current_snapshot(
                foreign_plan, candidate_id="foreign-date-current-p3b"
            ),
        )

    def test_same_date_foreign_bundle_snapshot_fails_closed_without_io_or_mutation(self) -> None:
        current_plan = _plan(DATE, response_id="bundle-a")
        foreign_plan = _plan(DATE, response_id="bundle-b")
        self.assertNotEqual(
            v7._v6._P3A._bundle_identity(current_plan),
            v7._v6._P3A._bundle_identity(foreign_plan),
        )
        self._assert_foreign_snapshot_rejected(
            current_plan=current_plan,
            foreign_snapshot=_current_snapshot(
                foreign_plan, candidate_id="same-date-foreign-bundle-current-p3b"
            ),
        )


if __name__ == "__main__":
    unittest.main()
