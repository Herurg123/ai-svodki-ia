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

from coverage_slot_guard import CoverageSlotError, load_journal, prepare_slot, sha256_value
import ensure_story_coverage_p3b_v7 as v7

DATE = "2026-09-19"
SEARCH_WINDOW = {
    "start_at": "2026-09-18T03:00:00+00:00",
    "end_at": "2026-09-19T03:00:00+00:00",
}


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _coverage_plan() -> dict:
    attempts = []
    for index, direction_id in enumerate(v7.AUDIT_DIRECTION_IDS, start=1):
        attempts.append(
            {
                "direction_id": direction_id,
                "attempt": 1,
                "status": "checked",
                "api": {"response_id": f"mandatory-{index}"},
            }
        )
    return {
        "checked_directions": list(v7.AUDIT_DIRECTION_IDS),
        "attempts": attempts,
        "candidates": [],
        "search_budget": {
            "maximum_calls": 7,
            "completed_calls": 6,
            "remaining_calls": 1,
        },
    }


def _processed_plan(base: dict) -> dict:
    result = copy.deepcopy(base)
    result["attempts"].append(
        {
            "direction_id": "general_coverage_gaps",
            "attempt": 2,
            "status": "checked_with_gaps",
            "search_strategy": v7.P3B_SLOT_OWNER,
            "resolution_mode": v7.P3B_MODE,
            "api": {"response_id": "optional-response"},
        }
    )
    result["search_budget"] = {
        "maximum_calls": 7,
        "completed_calls": 7,
        "remaining_calls": 0,
    }
    result["weak_source_exact_binding"] = {
        "version": v7.P3B_EXACT_BINDING_VERSION,
        "mode": v7.P3B_MODE,
        "signal_id": "sig-runtime",
        "status": "unresolved",
        "disposition": "unresolved_deferred",
        "candidate_count": 0,
        "binder_evidence_version": v7.P3B_BINDER_EVIDENCE_VERSION,
    }
    return result


def _research_artifact() -> dict:
    return {
        "publication_date": DATE,
        "search_window": copy.deepcopy(SEARCH_WINDOW),
        "coverage": [],
        "candidates": [],
        "unresolved_signals": [],
        "regional_health": {},
    }


def _saved_result_snapshot() -> dict:
    return {
        "payload": {
            "status": "complete_with_gaps",
            "direction_id": "general_coverage_gaps",
            "candidates": [],
            "rejections": [],
        },
        "metadata": {
            "response_id": "optional-response",
            "status": "completed",
            "actual_queries": ["runtime exact query"],
            "web_search_calls_completed": 1,
        },
        "output_text": "{}",
        "validation_error": None,
    }


class P3bV7DurableLineageTests(unittest.TestCase):
    def _seed_processed(self, state: Path):
        plan = _coverage_plan()
        reservation = prepare_slot(
            state_dir=state,
            publication_date=DATE,
            owner=v7.P3B_SLOT_OWNER,
            search_window=SEARCH_WINDOW,
            request_contract={
                "version": v7.P3B_EXACT_BINDING_VERSION,
                "strategy": v7.P3B_SLOT_OWNER,
                "model": "gpt-test",
                "query": "runtime exact query",
                "prompt_sha256": "runtime-prompt",
                "signal_ids": ["sig-runtime"],
                "maximum_web_search_calls": 1,
                "allowed_domains": [],
            },
            bundle_identity=v7._v6._P3A._bundle_identity(plan),
        )
        reservation.mark_request_started()
        reservation.save_raw_response({"id": "optional-response", "output": []})
        reservation.save_result_snapshot(_saved_result_snapshot())
        processed = _processed_plan(plan)
        reservation.mark_processed(processed)
        return reservation, processed

    def _matching_raw_replay(self, runtime, raw_response, **_kwargs):
        self.assertEqual(raw_response["id"], "optional-response")
        snapshot = _saved_result_snapshot()
        result = runtime.AuditRequestResult(
            payload=copy.deepcopy(snapshot["payload"]),
            metadata=copy.deepcopy(snapshot["metadata"]),
            output_text=snapshot["output_text"],
            raw_response=copy.deepcopy(raw_response),
            validation_error=None,
        )
        return result, snapshot

    def test_writer_persists_result_and_processed_lineage_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            _reservation, processed = self._seed_processed(state)
            journal = load_journal(state, DATE)
            self.assertIsInstance(journal, dict)
            self.assertEqual(
                journal.get("result_snapshot_sha256"),
                sha256_value(journal.get("result_snapshot")),
            )
            self.assertEqual(
                journal.get("processed_snapshot_sha256"),
                sha256_value(processed),
            )
            result_provenance = journal.get("result_snapshot_provenance")
            processed_provenance = journal.get("processed_snapshot_provenance")
            self.assertIsInstance(result_provenance, dict)
            self.assertIsInstance(processed_provenance, dict)
            self.assertEqual(
                result_provenance.get("request_contract_sha256"),
                journal.get("request_contract_sha256"),
            )
            self.assertEqual(
                result_provenance.get("response_sha256"),
                journal.get("response_sha256"),
            )
            self.assertEqual(
                processed_provenance.get("request_contract_sha256"),
                journal.get("request_contract_sha256"),
            )
            self.assertEqual(
                processed_provenance.get("response_sha256"),
                journal.get("response_sha256"),
            )
            self.assertEqual(
                processed_provenance.get("result_snapshot_sha256"),
                journal.get("result_snapshot_sha256"),
            )

    def test_production_shaped_processed_recovery_does_not_reconstruct_bundle_from_research(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "production-daily"
            artifact = root / DATE
            report = state / "coverage-audit.json"
            state.mkdir(parents=True)
            artifact.mkdir(parents=True)
            self._seed_processed(state)
            _write(artifact / "candidates.json", _research_artifact())

            with (
                mock.patch.object(
                    v7._v6,
                    "run_audit_request",
                    side_effect=AssertionError("provider call"),
                ) as ordinary,
                mock.patch.object(
                    v7._v6,
                    "protected_policy_audit_request",
                    side_effect=AssertionError("protected call"),
                ) as protected,
                mock.patch.object(
                    v7._v6._source_freshness,
                    "fetch_source_html",
                    side_effect=AssertionError("page fetch"),
                ) as pages,
                mock.patch.object(
                    v7,
                    "replay_raw_response",
                    side_effect=self._matching_raw_replay,
                ),
            ):
                context = v7.recovery_preflight(
                    publication_date=DATE,
                    artifact_dir=artifact,
                    report_path=report,
                    state_dir=state,
                )

            self.assertIsNone(context)
            self.assertEqual(
                (ordinary.call_count, protected.call_count, pages.call_count),
                (0, 0, 0),
            )

    def test_processed_snapshot_tamper_fails_closed_without_external_io(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "production-daily"
            artifact = root / DATE
            report = state / "coverage-audit.json"
            state.mkdir(parents=True)
            artifact.mkdir(parents=True)
            self._seed_processed(state)
            _write(artifact / "candidates.json", _research_artifact())

            journal_path = state / f"coverage-optional-slot-{DATE}.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            journal["processed_snapshot"]["candidates"] = [
                {
                    "id": "foreign-candidate",
                    "title": "Foreign candidate",
                    "audit_direction": "weak_source_exact_binding",
                }
            ]
            _write(journal_path, journal)

            with (
                mock.patch.object(
                    v7._v6,
                    "run_audit_request",
                    side_effect=AssertionError("provider call"),
                ) as ordinary,
                mock.patch.object(
                    v7._v6,
                    "protected_policy_audit_request",
                    side_effect=AssertionError("protected call"),
                ) as protected,
                mock.patch.object(
                    v7._v6._source_freshness,
                    "fetch_source_html",
                    side_effect=AssertionError("page fetch"),
                ) as pages,
                mock.patch.object(
                    v7,
                    "replay_raw_response",
                    side_effect=self._matching_raw_replay,
                ),
            ):
                with self.assertRaisesRegex(
                    CoverageSlotError, "processed snapshot provenance|processed snapshot hash"
                ):
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

    def test_saved_result_must_match_deterministic_raw_replay(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "production-daily"
            artifact = root / DATE
            report = state / "coverage-audit.json"
            state.mkdir(parents=True)
            artifact.mkdir(parents=True)
            self._seed_processed(state)
            _write(artifact / "candidates.json", _research_artifact())

            foreign_snapshot = _saved_result_snapshot()
            foreign_snapshot["metadata"]["response_id"] = "foreign-parsed-b"

            def replay_foreign(runtime, raw_response, **_kwargs):
                result = runtime.AuditRequestResult(
                    payload=copy.deepcopy(foreign_snapshot["payload"]),
                    metadata=copy.deepcopy(foreign_snapshot["metadata"]),
                    output_text=foreign_snapshot["output_text"],
                    raw_response=copy.deepcopy(raw_response),
                    validation_error=None,
                )
                return result, copy.deepcopy(foreign_snapshot)

            with (
                mock.patch.object(
                    v7,
                    "replay_raw_response",
                    side_effect=replay_foreign,
                ),
                mock.patch.object(
                    v7._v6,
                    "run_audit_request",
                    side_effect=AssertionError("provider call"),
                ) as ordinary,
                mock.patch.object(
                    v7._v6,
                    "protected_policy_audit_request",
                    side_effect=AssertionError("protected call"),
                ) as protected,
                mock.patch.object(
                    v7._v6._source_freshness,
                    "fetch_source_html",
                    side_effect=AssertionError("page fetch"),
                ) as pages,
            ):
                with self.assertRaisesRegex(
                    CoverageSlotError,
                    "saved result snapshot does not match deterministic raw replay",
                ):
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


if __name__ == "__main__":
    unittest.main()
