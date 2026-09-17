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
SIGNAL_ID = "historical-p3b-signal"
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


def _v1_candidate() -> dict:
    return {
        "id": "historical-v1",
        "title": "Historical P3b v1 candidate",
        "audit_direction": "weak_source_exact_binding",
        "resolution_signal_ids": [SIGNAL_ID],
        "p3b_exact_binding_version": 1,
        "primary_source": {
            "title": "Historical P3b v1 candidate",
            "publisher": "Example",
            "url": "https://example.com/historical-v1",
        },
    }


def _plan() -> dict:
    return {
        "publication_date": DATE,
        "search_window": copy.deepcopy(SEARCH_WINDOW),
        "checked_directions": list(v7.AUDIT_DIRECTION_IDS),
        "attempts": [],
        "candidates": [],
        "search_budget": {
            "maximum_calls": 7,
            "completed_calls": 7,
            "remaining_calls": 0,
        },
    }


class P3bV7ExternalReviewRegressions(unittest.TestCase):
    def test_nested_baseline_sync_cannot_restore_old_v6_revocation_predicate(self) -> None:
        stale = _v1_candidate()

        def preserved_v6_child(*_args, **_kwargs):
            return v7._base._v6._without_stale_p3b_candidates(
                {"candidates": [stale]},
                {"signal_id": SIGNAL_ID},
            )

        with mock.patch.object(
            v7._base._v6,
            "execute_audit_plan",
            side_effect=preserved_v6_child,
        ):
            result = v7.execute_audit_plan()

        self.assertEqual(result["candidates"], [])
        self.assertIs(
            v7._base._v6._without_stale_p3b_candidates,
            v7._without_stale_p3b_candidates,
        )

    def test_processed_journal_requires_deterministic_processed_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "production-daily"
            artifact = root / DATE
            report = state / "coverage-audit.json"
            journal_path = state / f"coverage-optional-slot-{DATE}.json"
            state.mkdir(parents=True)
            artifact.mkdir(parents=True)

            plan = _plan()
            _write(artifact / "candidates.json", plan)
            reservation = prepare_slot(
                state_dir=state,
                publication_date=DATE,
                owner=v7.P3B_SLOT_OWNER,
                search_window=SEARCH_WINDOW,
                request_contract={
                    "version": 1,
                    "strategy": v7.P3B_SLOT_OWNER,
                    "model": "gpt-test",
                    "query": "historical exact query",
                    "prompt_sha256": "fixture-prompt",
                    "signal_ids": [SIGNAL_ID],
                    "maximum_web_search_calls": 1,
                    "allowed_domains": [],
                },
                bundle_identity=v7._v6._P3A._bundle_identity(plan),
            )
            reservation.mark_request_started()
            reservation.save_raw_response({"id": "saved-response", "output": []})
            reservation.mark_processed(
                {
                    "candidates": [],
                    "weak_source_exact_binding": {
                        "version": 1,
                        "mode": v7.P3B_MODE,
                        "signal_id": SIGNAL_ID,
                        "status": "unresolved",
                        "disposition": "unresolved_deferred",
                        "candidate_count": 0,
                    },
                    "search_budget": {
                        "maximum_calls": 7,
                        "completed_calls": 7,
                        "remaining_calls": 0,
                    },
                }
            )
            valid = json.loads(journal_path.read_text(encoding="utf-8"))

            cases = {
                "missing": object(),
                "list": [],
                "scalar": "broken",
                "empty_object": {},
            }
            for name, replacement in cases.items():
                with self.subTest(name=name):
                    journal = copy.deepcopy(valid)
                    if name == "missing":
                        journal.pop("processed_snapshot", None)
                    else:
                        journal["processed_snapshot"] = replacement
                    _write(journal_path, journal)
                    with self.assertRaises(CoverageSlotError):
                        v7.recovery_preflight(
                            publication_date=DATE,
                            artifact_dir=artifact,
                            report_path=report,
                            state_dir=state,
                        )


if __name__ == "__main__":
    unittest.main()
