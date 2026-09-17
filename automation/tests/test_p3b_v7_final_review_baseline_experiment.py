from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
BASELINE = SCRIPTS / "ensure_story_coverage_p3b_v7_base.py"
PROPOSED = SCRIPTS / "ensure_story_coverage_p3b_v7.py"

_RUNNER = r'''
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

module_path = Path(sys.argv[1])
case = sys.argv[2]
spec = importlib.util.spec_from_file_location("p3b_experiment_target", module_path)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
from coverage_slot_guard import prepare_slot

DATE = "2026-09-17"
SIGNAL = "experiment-signal"
WINDOW = {
    "start_at": "2026-09-16T03:00:00+00:00",
    "end_at": "2026-09-17T03:00:00+00:00",
}


def candidate_v1():
    return {
        "id": "v1",
        "audit_direction": "weak_source_exact_binding",
        "resolution_signal_ids": [SIGNAL],
        "p3b_exact_binding_version": 1,
        "primary_source": {"url": "https://example.com/v1"},
    }


def candidate_v2():
    return {
        "id": "v2",
        "audit_direction": "weak_source_exact_binding",
        "resolution_signal_ids": [SIGNAL],
        "p3b_exact_binding_version": mod.P3B_EXACT_BINDING_VERSION,
        "p3b_authoritative_page_url": "https://example.com/v2",
        "p3b_authoritative_page_proof": "historical proof",
        "primary_source": {"url": "https://example.com/v2"},
    }


def unrelated():
    return {
        "id": "unrelated",
        "audit_direction": "weak_source_exact_binding",
        "p3b_exact_binding_version": 1,
        "primary_source": {"url": "https://example.com/unrelated"},
    }


def plan(candidates):
    return {
        "publication_date": DATE,
        "search_window": WINDOW,
        "checked_directions": list(mod.AUDIT_DIRECTION_IDS),
        "attempts": [],
        "candidates": candidates,
        "search_budget": {
            "maximum_calls": 7,
            "completed_calls": 7,
            "remaining_calls": 0,
        },
    }


if case in {"historical_v1", "historical_v2", "unrelated"}:
    row = candidate_v1() if case == "historical_v1" else candidate_v2() if case == "historical_v2" else unrelated()
    result = mod._without_stale_p3b_candidates(
        {"candidates": [row]}, {"signal_id": SIGNAL}
    )
    print(json.dumps({"candidate_ids": [x["id"] for x in result["candidates"]]}))
    raise SystemExit(0)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    state = root / "production-daily"
    artifact = root / DATE
    report = state / "coverage-audit.json"
    state.mkdir(parents=True)
    artifact.mkdir(parents=True)
    journal = state / f"coverage-optional-slot-{DATE}.json"
    marker = state / f"coverage-p3b-v7-revocation-{DATE}.json"

    if case == "invalid_journal":
        journal.write_text("{not-json", encoding="utf-8")
        try:
            result = mod.recovery_preflight(
                publication_date=DATE,
                artifact_dir=artifact,
                report_path=report,
                state_dir=state,
            )
        except Exception as exc:
            print(json.dumps({"outcome": "blocked", "error": type(exc).__name__}))
        else:
            print(json.dumps({"outcome": "continued", "context": result is not None}))
        raise SystemExit(0)

    if case == "pending_clean_recovery_inputs":
        marker.write_text(
            json.dumps(
                {
                    "version": 1,
                    "runtime_version": 7,
                    "publication_date": DATE,
                    "state": "pending",
                    "stale_signal_id": SIGNAL,
                    "publication_snapshot_invalidated": False,
                    "optional_slot_journal_mutated": False,
                }
            ) + "\n",
            encoding="utf-8",
        )
        report.write_text(json.dumps({"directions": [{"candidates": []}]}) + "\n", encoding="utf-8")
        mod.recovery_preflight(
            publication_date=DATE,
            artifact_dir=artifact,
            report_path=report,
            state_dir=state,
        )
        value = json.loads(marker.read_text(encoding="utf-8"))
        print(json.dumps({"marker_state": value.get("state")}))
        raise SystemExit(0)

    if case == "current_v6_positive":
        current = candidate_v2()
        current["id"] = "current-v6"
        research = plan([current])
        (artifact / "candidates.json").write_text(json.dumps(research) + "\n", encoding="utf-8")
        reservation = prepare_slot(
            state_dir=state,
            publication_date=DATE,
            owner=mod.P3B_SLOT_OWNER,
            search_window=WINDOW,
            request_contract={
                "version": mod.P3B_EXACT_BINDING_VERSION,
                "strategy": mod.P3B_SLOT_OWNER,
                "model": "experiment-model",
                "query": "experiment-query",
                "prompt_sha256": "experiment-prompt",
                "signal_ids": [SIGNAL],
                "maximum_web_search_calls": 1,
                "allowed_domains": [],
            },
            bundle_identity=mod._v6._P3A._bundle_identity(research),
        )
        reservation.mark_request_started()
        reservation.save_raw_response({"id": "experiment-response", "output": []})
        reservation.mark_processed(
            {
                "candidates": [current],
                "weak_source_exact_binding": {
                    "version": mod.P3B_EXACT_BINDING_VERSION,
                    "mode": mod.P3B_MODE,
                    "signal_id": SIGNAL,
                    "binder_evidence_version": mod.P3B_BINDER_EVIDENCE_VERSION,
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
        context = mod.recovery_preflight(
            publication_date=DATE,
            artifact_dir=artifact,
            report_path=report,
            state_dir=state,
        )
        after = json.loads((artifact / "candidates.json").read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "context": context is not None,
                    "candidate_ids": [x["id"] for x in after["candidates"]],
                    "marker_exists": marker.exists(),
                }
            )
        )
        raise SystemExit(0)

raise AssertionError(case)
'''


class P3bV7BaselineProposedExperimentTests(unittest.TestCase):
    maxDiff = None

    def run_case(self, module: Path, case: str) -> dict:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
        completed = subprocess.run(
            [sys.executable, "-c", _RUNNER, str(module), case],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def test_controlled_baseline_proposed_corpus(self) -> None:
        cases = {
            "historical_v1": (
                {"candidate_ids": ["v1"]},
                {"candidate_ids": []},
            ),
            "historical_v2": (
                {"candidate_ids": []},
                {"candidate_ids": []},
            ),
            "unrelated": (
                {"candidate_ids": ["unrelated"]},
                {"candidate_ids": ["unrelated"]},
            ),
            "invalid_journal": (
                {"outcome": "continued", "context": False},
                {"outcome": "blocked", "error": "CoverageSlotError"},
            ),
            "pending_clean_recovery_inputs": (
                {"marker_state": "pending"},
                {"marker_state": "completed"},
            ),
            "current_v6_positive": (
                {
                    "context": False,
                    "candidate_ids": ["current-v6"],
                    "marker_exists": False,
                },
                {
                    "context": False,
                    "candidate_ids": ["current-v6"],
                    "marker_exists": False,
                },
            ),
        }
        for case, (expected_baseline, expected_proposed) in cases.items():
            with self.subTest(case=case):
                self.assertEqual(self.run_case(BASELINE, case), expected_baseline)
                self.assertEqual(self.run_case(PROPOSED, case), expected_proposed)


if __name__ == "__main__":
    unittest.main()