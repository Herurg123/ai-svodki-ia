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
SIGNAL_ID = "crash-matrix-signal"
SEARCH_WINDOW = {
    "start_at": "2026-09-16T03:00:00+00:00",
    "end_at": "2026-09-17T03:00:00+00:00",
}


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _stale() -> dict:
    return {
        "id": "stale-crash",
        "title": "Stale crash candidate",
        "audit_direction": "weak_source_exact_binding",
        "resolution_signal_ids": [SIGNAL_ID],
        "p3b_exact_binding_version": v7.P3B_EXACT_BINDING_VERSION,
        "p3b_authoritative_page_url": "https://example.com/stale-crash",
        "p3b_authoritative_page_proof": "obsolete proof",
        "primary_source": {
            "title": "Stale crash candidate",
            "publisher": "Example",
            "url": "https://example.com/stale-crash",
        },
    }


def _independent() -> dict:
    return {
        "id": "independent-crash",
        "title": "Independent crash candidate",
        "audit_direction": "official_company_sources",
        "primary_source": {
            "title": "Independent crash candidate",
            "publisher": "Example",
            "url": "https://example.com/independent-crash",
        },
    }


def _plan(candidates: list[dict]) -> dict:
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


class P3bV7FinalReviewCrashMatrixTests(unittest.TestCase):
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
        self.archive = self.root / "archive.json"
        self.state.mkdir(parents=True)
        self.artifact.mkdir(parents=True)
        _write(self.archive, {"items": []})

    def _seed_journal(self, *, evidence_version: int, request_contract: dict | None = None) -> None:
        stale = _stale()
        independent = _independent()
        plan = _plan([stale, independent])
        reservation = prepare_slot(
            state_dir=self.state,
            publication_date=DATE,
            owner=v7.P3B_SLOT_OWNER,
            search_window=SEARCH_WINDOW,
            request_contract=request_contract
            or {
                "version": v7.P3B_EXACT_BINDING_VERSION,
                "strategy": v7.P3B_SLOT_OWNER,
                "model": "gpt-test",
                "query": "crash matrix query",
                "prompt_sha256": "crash-matrix-prompt",
                "signal_ids": [SIGNAL_ID],
                "maximum_web_search_calls": 1,
                "allowed_domains": [],
            },
            bundle_identity=v7._v6._P3A._bundle_identity(plan),
        )
        reservation.mark_request_started()
        reservation.save_raw_response({"id": "crash-matrix-response", "output": []})
        snapshot = copy.deepcopy(plan)
        snapshot["weak_source_exact_binding"] = {
            "version": v7.P3B_EXACT_BINDING_VERSION,
            "mode": v7.P3B_MODE,
            "signal_id": SIGNAL_ID,
            "binder_evidence_version": evidence_version,
            "status": "bound_candidate",
            "disposition": "positive_exact_binding",
            "candidate_count": 1,
        }
        reservation.mark_processed(snapshot)

    def _seed_recovery_input_only(self) -> None:
        self._seed_journal(evidence_version=5)
        independent = _independent()
        stale = _stale()
        _write(self.artifact / "candidates.json", _plan([independent]))
        _write(
            self.artifact / "stories.json",
            [{"candidate_id": independent["id"], "headline": independent["title"]}],
        )
        _write(self.persisted, {"candidates": [stale, independent]})
        _write(self.report, {"directions": [{"candidates": [stale, independent]}]})

    def _call(self):
        return v7.recovery_preflight(
            publication_date=DATE,
            artifact_dir=self.artifact,
            report_path=self.report,
            state_dir=self.state,
        )

    def _assert_restart_completes(self) -> None:
        self.assertIsNone(self._call())
        marker = json.loads(self.marker.read_text(encoding="utf-8"))
        self.assertEqual(marker["state"], "completed")
        self.assertFalse(marker["publication_snapshot_invalidated"])
        self.assertTrue((self.artifact / "stories.json").is_file())
        persisted = json.loads(self.persisted.read_text(encoding="utf-8"))
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in persisted["candidates"]], ["independent-crash"])
        self.assertEqual(
            [row["id"] for row in report["directions"][0]["candidates"]],
            ["independent-crash"],
        )

    def test_crash_after_pending_before_backup_restarts_idempotently(self) -> None:
        self._seed_recovery_input_only()
        original_backup = v7._backup_once
        crashed = False

        def fail_first_backup(source: Path, backup: Path) -> None:
            nonlocal crashed
            if not crashed:
                crashed = True
                raise RuntimeError("fault after pending before backup")
            original_backup(source, backup)

        with mock.patch.object(v7, "_backup_once", side_effect=fail_first_backup):
            with self.assertRaises(RuntimeError):
                self._call()
        self.assertEqual(json.loads(self.marker.read_text(encoding="utf-8"))["state"], "pending")
        self._assert_restart_completes()

    def test_crash_after_backup_before_first_mutation_restarts_idempotently(self) -> None:
        self._seed_recovery_input_only()
        original_atomic = v7._atomic_write_json
        crashed = False

        def fail_first_mutation(path: Path, value) -> None:
            nonlocal crashed
            if path == self.persisted and not crashed:
                crashed = True
                raise RuntimeError("fault after backup before mutation")
            original_atomic(path, value)

        with mock.patch.object(v7, "_atomic_write_json", side_effect=fail_first_mutation):
            with self.assertRaises(RuntimeError):
                self._call()
        self.assertEqual(json.loads(self.marker.read_text(encoding="utf-8"))["state"], "pending")
        self._assert_restart_completes()

    def test_crash_after_first_mutation_restarts_idempotently(self) -> None:
        self._seed_recovery_input_only()
        original_atomic = v7._atomic_write_json
        crashed = False

        def fail_second_mutation(path: Path, value) -> None:
            nonlocal crashed
            if path == self.report and not crashed:
                crashed = True
                raise RuntimeError("fault after first mutation")
            original_atomic(path, value)

        with mock.patch.object(v7, "_atomic_write_json", side_effect=fail_second_mutation):
            with self.assertRaises(RuntimeError):
                self._call()
        persisted = json.loads(self.persisted.read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in persisted["candidates"]], ["independent-crash"])
        self.assertEqual(json.loads(self.marker.read_text(encoding="utf-8"))["state"], "pending")
        self._assert_restart_completes()

    def test_crash_after_all_mutations_before_completed_restarts_idempotently(self) -> None:
        self._seed_recovery_input_only()
        original_atomic = v7._atomic_write_json
        crashed = False

        def fail_completed_marker(path: Path, value) -> None:
            nonlocal crashed
            if path == self.marker and isinstance(value, dict) and value.get("state") == "completed" and not crashed:
                crashed = True
                raise RuntimeError("fault after all mutations")
            original_atomic(path, value)

        with mock.patch.object(v7, "_atomic_write_json", side_effect=fail_completed_marker):
            with self.assertRaises(RuntimeError):
                self._call()
        self.assertEqual(json.loads(self.marker.read_text(encoding="utf-8"))["state"], "pending")
        self._assert_restart_completes()

    def test_crash_during_final_marker_atomic_write_restarts_idempotently(self) -> None:
        self._seed_recovery_input_only()
        original_replace = v7._base.os.replace
        crashed = False

        def fail_final_replace(source, destination) -> None:
            nonlocal crashed
            source_path = Path(source)
            destination_path = Path(destination)
            if (
                destination_path == self.marker
                and not crashed
                and source_path.is_file()
                and b'"state":"completed"' in source_path.read_bytes()
            ):
                crashed = True
                raise OSError("fault during final marker atomic replace")
            original_replace(source, destination)

        with mock.patch.object(v7._base.os, "replace", side_effect=fail_final_replace):
            with self.assertRaises(OSError):
                self._call()
        self.assertEqual(json.loads(self.marker.read_text(encoding="utf-8"))["state"], "pending")
        self.assertFalse(self.marker.with_name(self.marker.name + ".tmp").exists())
        self._assert_restart_completes()

    def test_restart_after_completed_is_noop(self) -> None:
        self._seed_recovery_input_only()
        self.assertIsNone(self._call())
        before = self.marker.read_bytes()
        self.assertIsNone(self._call())
        self.assertEqual(self.marker.read_bytes(), before)

    def test_current_v6_positive_rejects_model_and_request_identity_drift(self) -> None:
        signal = {"signal_id": SIGNAL_ID}
        query = "current exact query"
        prompt = "current exact prompt"
        contract = v7._base._v6._v2._request_contract_v2(
            model="model-a",
            query=query,
            prompt=prompt,
            signal=signal,
        )
        self._seed_journal(
            evidence_version=v7.P3B_BINDER_EVIDENCE_VERSION,
            request_contract=contract,
        )
        _write(self.artifact / "candidates.json", _plan([_stale(), _independent()]))

        base_argv = [
            "ensure_story_coverage.py",
            "--artifact-dir",
            str(self.artifact),
            "--publication-date",
            DATE,
            "--archive",
            str(self.archive),
            "--model",
            "model-a",
            "--report",
            str(self.report),
        ]
        with (
            mock.patch.object(v7, "_p3b_signals", return_value=[signal]),
            mock.patch.object(v7, "select_p3b_signal", return_value=signal),
            mock.patch.object(v7, "build_p3b_query", return_value=query),
            mock.patch.object(v7, "build_p3b_prompt", return_value=prompt),
            mock.patch.object(sys, "argv", base_argv),
        ):
            self.assertIsNone(self._call())

        drifted_argv = list(base_argv)
        drifted_argv[drifted_argv.index("model-a")] = "model-b"
        with (
            mock.patch.object(v7, "_p3b_signals", return_value=[signal]),
            mock.patch.object(v7, "select_p3b_signal", return_value=signal),
            mock.patch.object(v7, "build_p3b_query", return_value=query),
            mock.patch.object(v7, "build_p3b_prompt", return_value=prompt),
            mock.patch.object(sys, "argv", drifted_argv),
        ):
            with self.assertRaises(CoverageSlotError):
                self._call()

        journal = json.loads(self.journal.read_text(encoding="utf-8"))
        journal["request_contract_sha256"] = "a" * 64
        journal["request_contract"]["request_contract_sha256"] = "a" * 64
        _write(self.journal, journal)
        with (
            mock.patch.object(v7, "_p3b_signals", return_value=[signal]),
            mock.patch.object(v7, "select_p3b_signal", return_value=signal),
            mock.patch.object(v7, "build_p3b_query", return_value=query),
            mock.patch.object(v7, "build_p3b_prompt", return_value=prompt),
            mock.patch.object(sys, "argv", base_argv),
        ):
            with self.assertRaises(CoverageSlotError):
                self._call()


if __name__ == "__main__":
    unittest.main()
