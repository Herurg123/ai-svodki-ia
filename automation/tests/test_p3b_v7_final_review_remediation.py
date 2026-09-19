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

from coverage_slot_guard import CoverageSlotError, prepare_slot, sha256_value
import ensure_story_coverage_p3b_v7 as v7

DATE = "2026-09-17"
SIGNAL_ID = "historical-p3b-signal"
SEARCH_WINDOW = {
    "start_at": "2026-09-16T03:00:00+00:00",
    "end_at": "2026-09-17T03:00:00+00:00",
}


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _v1_candidate(candidate_id: str = "historical-v1") -> dict:
    return {
        "id": candidate_id,
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


def _v2_candidate(candidate_id: str = "historical-v2") -> dict:
    return {
        "id": candidate_id,
        "title": "Historical P3b v2 candidate",
        "audit_direction": "weak_source_exact_binding",
        "resolution_signal_ids": [SIGNAL_ID],
        "p3b_exact_binding_version": v7.P3B_EXACT_BINDING_VERSION,
        "p3b_authoritative_page_url": "https://example.com/historical-v2",
        "p3b_authoritative_page_proof": "current-event surface + deterministic Source/Event Freshness",
        "primary_source": {
            "title": "Historical P3b v2 candidate",
            "publisher": "Example",
            "url": "https://example.com/historical-v2",
        },
    }


def _same_looking_unrelated() -> dict:
    return {
        "id": "same-looking-unrelated",
        "title": "Historical P3b v1 candidate",
        "audit_direction": "weak_source_exact_binding",
        "p3b_exact_binding_version": 1,
        "primary_source": {
            "title": "Historical P3b v1 candidate",
            "publisher": "Example",
            "url": "https://example.com/lookalike",
        },
    }


def _independent() -> dict:
    return {
        "id": "independent",
        "title": "Independent mandatory Coverage candidate",
        "audit_direction": "official_company_sources",
        "primary_source": {
            "title": "Independent mandatory Coverage candidate",
            "publisher": "Example",
            "url": "https://example.com/independent",
        },
    }


def _raw_response(*, response_id: str = "saved-response", query: str = "historical exact query") -> dict:
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


class P3bV7FinalReviewRemediationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "production-daily"
        self.artifact = self.root / DATE
        self.report = self.state / "coverage-audit.json"
        self.persisted = self.state / f"coverage-audit-merged-candidates-{DATE}.json"
        self.journal = self.state / f"coverage-optional-slot-{DATE}.json"
        self.marker = self.state / f"coverage-p3b-v7-revocation-{DATE}.json"
        self.state.mkdir(parents=True)
        self.artifact.mkdir(parents=True)

    def _plan(self, candidates: list[dict]) -> dict:
        return {
            "publication_date": DATE,
            "search_window": dict(SEARCH_WINDOW),
            "checked_directions": list(v7.AUDIT_DIRECTION_IDS),
            "attempts": [],
            "candidates": copy.deepcopy(candidates),
            "search_budget": {
                "maximum_calls": 7,
                "completed_calls": 7,
                "remaining_calls": 0,
            },
        }

    def _seed_processed_journal(self, snapshot: dict) -> bytes:
        plan = self._plan(list(snapshot.get("candidates") or []))
        contract = {
            "version": 1,
            "strategy": v7.P3B_SLOT_OWNER,
            "model": "gpt-test",
            "query": "historical exact query",
            "prompt_sha256": sha256_value("historical prompt"),
            "signal_ids": [SIGNAL_ID],
            "maximum_web_search_calls": 1,
            "allowed_domains": [],
        }
        reservation = prepare_slot(
            state_dir=self.state,
            publication_date=DATE,
            owner=v7.P3B_SLOT_OWNER,
            search_window=SEARCH_WINDOW,
            request_contract=contract,
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
        production_snapshot = copy.deepcopy(plan)
        production_snapshot.update(copy.deepcopy(snapshot))
        reservation.mark_processed(production_snapshot)
        return self.journal.read_bytes()

    def _stale_snapshot(self, candidate: dict) -> dict:
        return {
            "candidates": [candidate, _independent()],
            "weak_source_exact_binding": {
                "version": int(candidate.get("p3b_exact_binding_version", 1) or 1),
                "mode": v7.P3B_MODE,
                "signal_id": SIGNAL_ID,
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

    def _call(self):
        return v7.recovery_preflight(
            publication_date=DATE,
            artifact_dir=self.artifact,
            report_path=self.report,
            state_dir=self.state,
        )

    def _zero_external_io(self):
        return (
            mock.patch.object(v7._v6, "run_audit_request", side_effect=AssertionError("provider call")),
            mock.patch.object(v7._v6, "protected_policy_audit_request", side_effect=AssertionError("retry/protected call")),
            mock.patch.object(v7._v6._source_freshness, "fetch_source_html", side_effect=AssertionError("page fetch")),
        )

    def test_p1_genuine_v1_candidate_is_revoked_but_lookalikes_survive(self) -> None:
        stale = _v1_candidate()
        lookalike = _same_looking_unrelated()
        independent = _independent()
        original_journal = self._seed_processed_journal(self._stale_snapshot(stale))
        plan = self._plan([stale, lookalike, independent])
        _write(self.artifact / "candidates.json", plan)
        _write(self.persisted, {"candidates": [stale, lookalike, independent]})
        _write(self.report, {"directions": [{"candidates": [stale, lookalike, independent]}]})
        _write(self.artifact / "stories.json", [{"candidate_id": stale["id"]}])

        ordinary, protected, pages = self._zero_external_io()
        with ordinary as p1, protected as p2, pages as p3:
            context = self._call()

        self.assertIsInstance(context, dict)
        self.assertEqual((p1.call_count, p2.call_count, p3.call_count), (0, 0, 0))
        self.assertEqual(self.journal.read_bytes(), original_journal)
        current = json.loads((self.artifact / "candidates.json").read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in current["candidates"]], ["same-looking-unrelated", "independent"])
        persisted = json.loads(self.persisted.read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in persisted["candidates"]], ["same-looking-unrelated", "independent"])
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in report["directions"][0]["candidates"]], ["same-looking-unrelated", "independent"])
        self.assertFalse((self.artifact / "stories.json").exists())

    def test_p1_adjacent_v2_shape_remains_revocable(self) -> None:
        stale = _v2_candidate()
        self._seed_processed_journal(self._stale_snapshot(stale))
        _write(self.artifact / "candidates.json", self._plan([stale, _independent()]))
        _write(self.artifact / "stories.json", [{"candidate_id": stale["id"]}])
        context = self._call()
        self.assertIsInstance(context, dict)
        current = json.loads((self.artifact / "candidates.json").read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in current["candidates"]], ["independent"])

    def test_p2_missing_journal_is_distinct_from_invalid_journal(self) -> None:
        self.assertIsNone(self._call())
        cases = {
            "malformed": "{not-json",
            "non_object": json.dumps(["journal"]),
            "unsupported_version": json.dumps({"version": 999, "publication_date": DATE}),
            "wrong_publication_date": json.dumps({"version": 1, "publication_date": "2026-09-16"}),
        }
        for name, raw in cases.items():
            with self.subTest(name=name):
                self.journal.write_text(raw, encoding="utf-8")
                with self.assertRaises(CoverageSlotError):
                    self._call()
                self.journal.unlink(missing_ok=True)

    def test_p2_corrupt_or_missing_saved_response_fails_closed(self) -> None:
        stale = _v2_candidate()
        self._seed_processed_journal(self._stale_snapshot(stale))
        journal = json.loads(self.journal.read_text(encoding="utf-8"))
        response = self.state / f"coverage-optional-slot-{DATE}.response.json"

        response.unlink()
        with self.assertRaises(CoverageSlotError):
            self._call()

        _write(response, {"tampered": True})
        with self.assertRaises(CoverageSlotError):
            self._call()

        journal["response_sha256"] = "0" * 64
        _write(self.journal, journal)
        with self.assertRaises(CoverageSlotError):
            self._call()

    def test_p2_search_window_and_bundle_identity_drift_fail_closed(self) -> None:
        stale = _v2_candidate()
        self._seed_processed_journal(self._stale_snapshot(stale))
        _write(self.artifact / "candidates.json", self._plan([stale, _independent()]))
        journal = json.loads(self.journal.read_text(encoding="utf-8"))

        for key in ("search_window_sha256", "bundle_identity_sha256"):
            with self.subTest(key=key):
                changed = copy.deepcopy(journal)
                changed[key] = "f" * 64
                _write(self.journal, changed)
                with self.assertRaises(CoverageSlotError):
                    self._call()
        _write(self.journal, journal)

    def test_p3_restart_finalizes_pending_after_mutations_completed(self) -> None:
        stale = _v2_candidate()
        self._seed_processed_journal(self._stale_snapshot(stale))
        _write(self.artifact / "candidates.json", self._plan([_independent()]))
        _write(self.artifact / "stories.json", [{"candidate_id": "independent"}])
        _write(self.persisted, {"candidates": [stale, _independent()]})
        _write(self.report, {"directions": [{"candidates": [stale, _independent()]}]})

        original_atomic = v7._atomic_write_json
        crashed = False

        def crash_before_completed(path: Path, value) -> None:
            nonlocal crashed
            if path == self.marker and isinstance(value, dict) and value.get("state") == "completed" and not crashed:
                crashed = True
                raise RuntimeError("fault injection before completed marker")
            original_atomic(path, value)

        with mock.patch.object(v7, "_atomic_write_json", side_effect=crash_before_completed):
            with self.assertRaises(RuntimeError):
                self._call()

        pending = json.loads(self.marker.read_text(encoding="utf-8"))
        self.assertEqual(pending["state"], "pending")
        self.assertFalse(pending["publication_snapshot_invalidated"])
        self.assertEqual(
            [row["id"] for row in json.loads(self.persisted.read_text(encoding="utf-8"))["candidates"]],
            ["independent"],
        )

        self.assertIsNone(self._call())
        completed = json.loads(self.marker.read_text(encoding="utf-8"))
        self.assertEqual(completed["state"], "completed")
        self.assertTrue((self.artifact / "stories.json").is_file())


if __name__ == "__main__":
    unittest.main()
