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

from coverage_slot_guard import prepare_slot
import ensure_story_coverage_p3b_v7 as v7

DATE = "2026-09-16"
SIGNAL_ID = "weak-source-signal-1"
SEARCH_WINDOW = {
    "start_at": "2026-09-15T03:00:00+00:00",
    "end_at": "2026-09-16T03:00:00+00:00",
}


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stale_candidate(*, candidate_id: str = "stale-1") -> dict:
    return {
        "id": candidate_id,
        "title": "Stale P3b candidate",
        "audit_direction": "weak_source_exact_binding",
        "resolution_signal_ids": [SIGNAL_ID],
        "p3b_exact_binding_version": v7.P3B_EXACT_BINDING_VERSION,
        "p3b_authoritative_page_url": "https://example.com/stale",
        "p3b_authoritative_page_proof": "old positive exact binding proof",
        "primary_source": {
            "title": "Stale P3b candidate",
            "publisher": "Example",
            "url": "https://example.com/stale",
        },
    }


def _independent_candidate() -> dict:
    return {
        "id": "independent-1",
        "title": "Independent candidate",
        "audit_direction": "official_company_sources",
        "primary_source": {
            "title": "Independent candidate",
            "publisher": "Example",
            "url": "https://example.com/independent",
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


def _snapshot(*, binder_evidence_version: int, candidates: list[dict]) -> dict:
    result = _plan(candidates)
    result["weak_source_exact_binding"] = {
        "version": v7.P3B_EXACT_BINDING_VERSION,
        "mode": v7.P3B_MODE,
        "signal_id": SIGNAL_ID,
        "binder_evidence_version": binder_evidence_version,
        "status": "bound_candidate",
        "disposition": "positive_exact_binding",
        "candidate_count": 1,
    }
    return result


def _raw_response(*, response_id: str = "fixture-response", query: str = "durable exact query") -> dict:
    payload = {
        "status": "complete_with_gaps",
        "direction_id": "general_coverage_gaps",
        "candidates": [],
        "rejections": [],
    }
    return {
        "id": response_id,
        "status": "completed",
        "model": "gpt-test",
        "output_text": json.dumps(payload, ensure_ascii=False),
        "output": [
            {
                "id": "search-1",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": query, "sources": []},
            }
        ],
    }


class P3bV7RecoveryPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "production-daily"
        self.artifact = self.root / DATE
        self.report = self.state / "coverage-audit.json"
        self.state.mkdir(parents=True)
        self.artifact.mkdir(parents=True)

    @property
    def journal_path(self) -> Path:
        return self.state / f"coverage-optional-slot-{DATE}.json"

    @property
    def marker_path(self) -> Path:
        return self.state / f"coverage-p3b-v7-revocation-{DATE}.json"

    def seed_journal(self, *, binder_evidence_version: int, candidates: list[dict]) -> bytes:
        plan = _plan(candidates)
        reservation = prepare_slot(
            state_dir=self.state,
            publication_date=DATE,
            owner=v7.P3B_SLOT_OWNER,
            search_window=SEARCH_WINDOW,
            request_contract={
                "version": v7.P3B_EXACT_BINDING_VERSION,
                "strategy": v7.P3B_SLOT_OWNER,
                "model": "gpt-test",
                "query": "durable exact query",
                "prompt_sha256": "fixture-prompt",
                "signal_ids": [SIGNAL_ID],
                "maximum_web_search_calls": 1,
                "allowed_domains": [],
            },
            bundle_identity=v7._v6._P3A._bundle_identity(plan),
        )
        reservation.mark_request_started()
        raw_response = _raw_response()
        reservation.save_raw_response(raw_response)
        _parsed, result_snapshot = v7.replay_raw_response(
            v7._base._v6._runtime,
            raw_response,
            maximum_web_search_calls=1,
        )
        reservation.save_result_snapshot(result_snapshot)
        reservation.mark_processed(
            _snapshot(
                binder_evidence_version=binder_evidence_version,
                candidates=candidates,
            )
        )
        return self.journal_path.read_bytes()

    def seed_stale(self) -> bytes:
        stale = _stale_candidate()
        independent = _independent_candidate()
        plan = _plan([stale, independent])
        original_journal = self.seed_journal(
            binder_evidence_version=5,
            candidates=[stale, independent],
        )
        _write(self.artifact / "candidates.json", plan)
        _write(
            self.artifact / "stories.json",
            [
                {
                    "candidate_id": stale["id"],
                    "headline": stale["title"],
                    "sources": [{"url": stale["primary_source"]["url"]}],
                },
                {
                    "candidate_id": independent["id"],
                    "headline": independent["title"],
                },
            ],
        )
        _write(
            self.report,
            {
                "publication_date": DATE,
                "audit_status": "complete",
                "web_search_performed": True,
                "directions": [
                    {
                        "direction_id": "weak_source_exact_binding",
                        "candidates": [copy.deepcopy(stale), copy.deepcopy(independent)],
                    }
                ],
            },
        )
        return original_journal

    def call_preflight(self):
        return v7.recovery_preflight(
            publication_date=DATE,
            artifact_dir=self.artifact,
            report_path=self.report,
            state_dir=self.state,
        )

    def test_stale_complete_artifact_and_reused_report_are_revoked_before_shortcuts(self) -> None:
        original_journal = self.seed_stale()
        with (
            mock.patch.object(
                v7._v6,
                "run_audit_request",
                side_effect=AssertionError("no search"),
            ) as ordinary,
            mock.patch.object(
                v7._v6,
                "protected_policy_audit_request",
                side_effect=AssertionError("no protected search"),
            ) as protected,
            mock.patch.object(
                v7._v6._source_freshness,
                "fetch_source_html",
                side_effect=AssertionError("no page refetch"),
            ) as pages,
        ):
            context = self.call_preflight()

        self.assertIsInstance(context, dict)
        self.assertEqual(
            (ordinary.call_count, protected.call_count, pages.call_count),
            (0, 0, 0),
        )
        self.assertEqual(self.journal_path.read_bytes(), original_journal)

        research = json.loads(
            (self.artifact / "candidates.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            [row["id"] for row in research["candidates"]],
            ["independent-1"],
        )
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(
            [row["id"] for row in report["directions"][0]["candidates"]],
            ["independent-1"],
        )
        self.assertFalse((self.artifact / "stories.json").exists())

        marker = json.loads(self.marker_path.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "pending")
        self.assertFalse(marker["optional_slot_journal_mutated"])
        self.assertEqual(marker["binder_evidence_version_required"], 6)
        self.assertTrue(
            self.state.joinpath(
                f"coverage-p3b-v7-revocation-{DATE}.stories.original.json"
            ).is_file()
        )

    def test_pending_marker_survives_missing_journal_and_keeps_complete_snapshot_quarantined(self) -> None:
        self.seed_stale()
        first = self.call_preflight()
        self.assertIsInstance(first, dict)
        original_hash = json.loads(
            self.marker_path.read_text(encoding="utf-8")
        )["original_stories_sha256"]
        self.journal_path.unlink()
        self.state.joinpath(f"coverage-optional-slot-{DATE}.response.json").unlink()

        second = self.call_preflight()
        self.assertIsInstance(second, dict)
        marker = json.loads(self.marker_path.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "pending")
        self.assertEqual(marker["original_stories_sha256"], original_hash)
        self.assertFalse((self.artifact / "stories.json").exists())

    def test_current_evidence_v6_does_not_trigger_preflight(self) -> None:
        stale = _stale_candidate()
        plan = _plan([stale])
        self.seed_journal(
            binder_evidence_version=v7.P3B_BINDER_EVIDENCE_VERSION,
            candidates=[stale],
        )
        _write(self.artifact / "candidates.json", plan)
        _write(
            self.artifact / "stories.json",
            [{"candidate_id": stale["id"]}],
        )
        before = (self.artifact / "stories.json").read_bytes()

        context = self.call_preflight()

        self.assertIsNone(context)
        self.assertEqual((self.artifact / "stories.json").read_bytes(), before)
        self.assertFalse(self.marker_path.exists())

    def test_report_only_stale_provenance_is_cleaned_without_invalidating_clean_digest(self) -> None:
        independent = _independent_candidate()
        stale = _stale_candidate()
        self.seed_journal(
            binder_evidence_version=5,
            candidates=[stale, independent],
        )
        _write(self.artifact / "candidates.json", _plan([independent]))
        _write(
            self.artifact / "stories.json",
            [{"candidate_id": independent["id"]}],
        )
        _write(
            self.report,
            {"directions": [{"candidates": [stale, independent]}]},
        )

        context = self.call_preflight()

        self.assertIsNone(context)
        self.assertTrue((self.artifact / "stories.json").is_file())
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(
            [row["id"] for row in report["directions"][0]["candidates"]],
            ["independent-1"],
        )
        marker = json.loads(self.marker_path.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "completed")
        self.assertEqual(
            marker["reason"],
            "stale_positive_p3b_recovery_inputs_sanitized",
        )

    def test_child_failure_leaves_pending_marker_and_no_publishable_stories(self) -> None:
        self.seed_stale()
        argv = [
            "ensure_story_coverage.py",
            "--artifact-dir",
            str(self.artifact),
            "--publication-date",
            DATE,
            "--report",
            str(self.report),
        ]
        with (
            mock.patch.object(v7, "STATE_DIR", self.state),
            mock.patch.object(v7._v6, "main", return_value=1),
            mock.patch.object(sys, "argv", argv),
        ):
            code = v7.main()

        self.assertEqual(code, 1)
        self.assertFalse((self.artifact / "stories.json").exists())
        marker = json.loads(self.marker_path.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "pending")

    def test_successful_clean_rebuild_completes_marker(self) -> None:
        self.seed_stale()
        argv = [
            "ensure_story_coverage.py",
            "--artifact-dir",
            str(self.artifact),
            "--publication-date",
            DATE,
            "--report",
            str(self.report),
        ]

        def fake_child() -> int:
            self.assertFalse((self.artifact / "stories.json").exists())
            _write(
                self.artifact / "stories.json",
                [
                    {
                        "candidate_id": "independent-1",
                        "headline": "Independent candidate",
                    }
                ],
            )
            return 0

        with (
            mock.patch.object(v7, "STATE_DIR", self.state),
            mock.patch.object(v7._v6, "main", side_effect=fake_child),
            mock.patch.object(sys, "argv", argv),
        ):
            code = v7.main()

        self.assertEqual(code, 0)
        marker = json.loads(self.marker_path.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "completed")
        self.assertTrue(marker.get("clean_candidates_sha256"))
        self.assertTrue(marker.get("clean_stories_sha256"))

    def test_false_success_that_reintroduces_stale_story_is_blocked(self) -> None:
        self.seed_stale()
        argv = [
            "ensure_story_coverage.py",
            "--artifact-dir",
            str(self.artifact),
            "--publication-date",
            DATE,
            "--report",
            str(self.report),
        ]

        def fake_child() -> int:
            _write(
                self.artifact / "stories.json",
                [
                    {
                        "candidate_id": "stale-1",
                        "headline": "Stale P3b candidate",
                    }
                ],
            )
            return 0

        with (
            mock.patch.object(v7, "STATE_DIR", self.state),
            mock.patch.object(v7._v6, "main", side_effect=fake_child),
            mock.patch.object(sys, "argv", argv),
        ):
            code = v7.main()

        self.assertEqual(code, 1)
        marker = json.loads(self.marker_path.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "blocked")
        self.assertTrue(marker["postflight_errors"])


if __name__ == "__main__":
    unittest.main()
