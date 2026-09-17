from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from coverage_slot_guard import prepare_slot
import ensure_story_coverage_p3b_v7 as v7

DATE = "2026-09-17"
SIGNAL_ID = "weak-source-signal-persisted"
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


def _stale() -> dict:
    return {
        "id": "stale-persisted",
        "title": "Stale persisted P3b candidate",
        "audit_direction": "weak_source_exact_binding",
        "resolution_signal_ids": [SIGNAL_ID],
        "p3b_exact_binding_version": v7.P3B_EXACT_BINDING_VERSION,
        "p3b_authoritative_page_url": "https://example.com/stale-persisted",
        "p3b_authoritative_page_proof": "obsolete exact binding proof",
        "primary_source": {
            "title": "Stale persisted P3b candidate",
            "publisher": "Example",
            "url": "https://example.com/stale-persisted",
        },
    }


def _independent() -> dict:
    return {
        "id": "independent-persisted",
        "title": "Independent persisted candidate",
        "audit_direction": "official_company_sources",
        "primary_source": {
            "title": "Independent persisted candidate",
            "publisher": "Example",
            "url": "https://example.com/independent-persisted",
        },
    }


def _plan(candidates: list[dict]) -> dict:
    return {
        "publication_date": DATE,
        "search_window": copy.deepcopy(SEARCH_WINDOW),
        "checked_directions": list(v7.AUDIT_DIRECTION_IDS),
        "attempts": [],
        "candidates": copy.deepcopy(candidates),
        "search_budget": {
            "maximum_calls": 7,
            "completed_calls": 7,
            "remaining_calls": 0,
        },
    }


class P3bV7DurableRecoveryInputsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "production-daily"
        self.artifact = self.root / DATE
        self.report = self.state / "coverage-audit.json"
        self.persisted = (
            self.state / f"coverage-audit-merged-candidates-{DATE}.json"
        )
        self.journal = self.state / f"coverage-optional-slot-{DATE}.json"
        self.marker = self.state / f"coverage-p3b-v7-revocation-{DATE}.json"
        self.state.mkdir(parents=True)
        self.artifact.mkdir(parents=True)
        self.seed_journal()

    def seed_journal(self) -> None:
        stale = _stale()
        independent = _independent()
        plan = _plan([stale, independent])
        reservation = prepare_slot(
            state_dir=self.state,
            publication_date=DATE,
            owner=v7.P3B_SLOT_OWNER,
            search_window=SEARCH_WINDOW,
            request_contract={
                "version": v7.P3B_EXACT_BINDING_VERSION,
                "strategy": v7.P3B_SLOT_OWNER,
                "model": "gpt-test",
                "query": "persisted exact query",
                "prompt_sha256": "fixture-prompt",
                "signal_ids": [SIGNAL_ID],
                "maximum_web_search_calls": 1,
                "allowed_domains": [],
            },
            bundle_identity=v7._v6._P3A._bundle_identity(plan),
        )
        reservation.mark_request_started()
        reservation.save_raw_response({"id": "persisted-response", "output": []})
        reservation.mark_processed(
            {
                "candidates": [stale, independent],
                "weak_source_exact_binding": {
                    "version": v7.P3B_EXACT_BINDING_VERSION,
                    "mode": v7.P3B_MODE,
                    "signal_id": SIGNAL_ID,
                    "binder_evidence_version": 5,
                    "status": "bound_candidate",
                    "disposition": "positive_exact_binding",
                    "candidate_count": 1,
                },
                "search_budget": {
                    "maximum_calls": 7,
                    "completed_calls": 7,
                    "remaining_calls": 0,
                },
            }
        )

    def test_persisted_research_only_is_sanitized_without_invalidating_clean_digest(self) -> None:
        independent = _independent()
        _write(self.artifact / "candidates.json", _plan([independent]))
        _write(
            self.artifact / "stories.json",
            [{"candidate_id": independent["id"], "headline": independent["title"]}],
        )
        _write(self.persisted, {"candidates": [_stale(), independent]})
        original_stories = (self.artifact / "stories.json").read_bytes()

        context = v7.recovery_preflight(
            publication_date=DATE,
            artifact_dir=self.artifact,
            report_path=self.report,
            state_dir=self.state,
        )

        self.assertIsNone(context)
        self.assertEqual(
            (self.artifact / "stories.json").read_bytes(), original_stories
        )
        persisted = json.loads(self.persisted.read_text(encoding="utf-8"))
        self.assertEqual(
            [row["id"] for row in persisted["candidates"]],
            ["independent-persisted"],
        )
        marker = json.loads(self.marker.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "completed")
        self.assertFalse(marker["publication_snapshot_invalidated"])
        self.assertEqual(marker["persisted_research_revocations"], 1)
        self.assertTrue(
            self.state.joinpath(
                f"coverage-p3b-v7-revocation-{DATE}.merged-research.original.json"
            ).is_file()
        )

    def test_publication_quarantine_sanitizes_persisted_research_and_postflight_checks_it(self) -> None:
        stale = _stale()
        independent = _independent()
        _write(
            self.artifact / "candidates.json",
            _plan([stale, independent]),
        )
        _write(
            self.artifact / "stories.json",
            [{"candidate_id": stale["id"], "headline": stale["title"]}],
        )
        _write(self.persisted, {"candidates": [stale, independent]})

        context = v7.recovery_preflight(
            publication_date=DATE,
            artifact_dir=self.artifact,
            report_path=self.report,
            state_dir=self.state,
        )
        self.assertIsInstance(context, dict)
        persisted = json.loads(self.persisted.read_text(encoding="utf-8"))
        self.assertEqual(
            [row["id"] for row in persisted["candidates"]],
            ["independent-persisted"],
        )

        # A later recovery source must not be allowed to reintroduce the stale row
        # while the child reports success.
        _write(self.persisted, {"candidates": [stale, independent]})
        _write(
            self.artifact / "stories.json",
            [{"candidate_id": independent["id"], "headline": independent["title"]}],
        )
        code = v7._postflight(
            context,
            child_code=0,
            artifact_dir=self.artifact,
            report_path=self.report,
        )

        self.assertEqual(code, 1)
        marker = json.loads(self.marker.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "blocked")
        self.assertTrue(
            any("persisted merged research" in item for item in marker["postflight_errors"])
        )


if __name__ == "__main__":
    unittest.main()
