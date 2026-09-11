from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import editorial_repair_journal as repair
import recover_digest_artifact as recovery
import usage_observer as observer

DATE = "2026-09-11"
MODEL = "gpt-5.6-terra"


class _FakeResponses:
    def __init__(self, client):
        self._client = client

    def create(self, **kwargs):
        return self._client._create(**kwargs)


class _FakeClient:
    def __init__(self, calls, *, max_retries=2, output=None, error=None):
        self.calls = calls
        self.max_retries = max_retries
        self.output = output or {"selected_candidate_ids": ["candidate-1"]}
        self.error = error
        self.responses = _FakeResponses(self)

    def with_options(self, *, max_retries):
        return _FakeClient(
            self.calls,
            max_retries=max_retries,
            output=self.output,
            error=self.error,
        )

    def _create(self, **kwargs):
        self.calls.append({"max_retries": self.max_retries, "kwargs": kwargs})
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            id="resp-repair-1",
            model=kwargs["model"],
            status="completed",
            service_tier="default",
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            error=None,
            output_text=json.dumps(self.output),
            output=[],
            _transport={"openai_request_id": "req-repair-1"},
        )


class EditorialRepairRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.research = (
            self.root
            / "automation/fixtures/research/.runtime"
            / f".coverage-audit-{DATE}.json"
        )
        self.research.parent.mkdir(parents=True, exist_ok=True)
        self.research_payload = {
            "publication_date": DATE,
            "candidates": [{"id": "candidate-1", "title": "Coverage candidate"}],
        }
        self.research.write_text(
            json.dumps(self.research_payload), encoding="utf-8"
        )
        self.state_dir = self.root / "automation/preview/production-daily"
        self.usage_dir = self.state_dir / "usage-events"
        self.argv = [
            "generate_digest_preview.py",
            "--publication-date",
            DATE,
            "--research-input",
            str(self.research),
        ]
        self.kwargs = {
            "model": MODEL,
            "input": "PRIVATE_EDITORIAL_PROMPT",
            "store": False,
        }

    def context(self, *, state_dir=None):
        usage_dir = (state_dir or self.state_dir) / "usage-events"
        context = repair.repair_context_from_argv(
            "editorial",
            self.kwargs,
            argv=self.argv,
            usage_dir=str(usage_dir),
            cwd=self.root,
        )
        self.assertIsNotNone(context)
        return context

    def call_repair(self, client):
        with patch.object(sys, "argv", self.argv), patch.dict(
            os.environ,
            {
                "AI_DIGEST_USAGE_DIR": str(self.usage_dir),
                "AI_DIGEST_PUBLICATION_DATE": DATE,
            },
            clear=False,
        ):
            return observer.call_with_usage(
                "editorial", client.responses.create, **self.kwargs
            )

    def test_repair_disables_sdk_retries_and_replays_without_second_call(self):
        calls = []
        client = _FakeClient(calls)
        first = self.call_repair(client)
        second = self.call_repair(client)
        self.assertEqual(first.status, "completed")
        self.assertEqual(second.status, "completed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["max_retries"], 0)
        journal = repair._load_journal(self.context())
        self.assertEqual(journal["state"], "response_saved")

    def test_request_started_without_response_fails_closed_without_transport(self):
        context = self.context()
        binding = repair.request_binding_sha256(self.kwargs)
        self.assertIsNone(
            repair.prepare_and_check_replay(context, binding_sha256=binding)
        )
        repair.begin_request(context, binding_sha256=binding)
        calls = []
        client = _FakeClient(calls)
        with self.assertRaises(repair.EditorialRepairJournalError):
            self.call_repair(client)
        self.assertEqual(calls, [])

    def test_saved_response_survives_crash_before_journal_transition(self):
        context = self.context()
        binding = repair.request_binding_sha256(self.kwargs)
        repair.prepare_and_check_replay(context, binding_sha256=binding)
        repair.begin_request(context, binding_sha256=binding)
        response = _FakeClient([])._create(**self.kwargs)
        repair._write_response(
            context, binding_sha256=binding, response=response
        )
        replay = repair.prepare_and_check_replay(
            context, binding_sha256=binding
        )
        self.assertEqual(replay.output_text, response.output_text)
        self.assertEqual(repair._load_journal(context)["state"], "response_saved")

    def test_transport_exception_is_terminal_and_not_retried(self):
        calls = []
        client = _FakeClient(calls, error=RuntimeError("provider outcome unknown"))
        with self.assertRaises(RuntimeError):
            self.call_repair(client)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["max_retries"], 0)
        self.assertEqual(repair._load_journal(self.context())["state"], "failed_terminal")
        with self.assertRaises(repair.EditorialRepairJournalError):
            self.call_repair(client)
        self.assertEqual(len(calls), 1)

    def test_sep11_legacy_failure_blocks_old_digest_publication(self):
        artifact = self.root / "automation/preview" / DATE
        artifact.mkdir(parents=True)
        (artifact / "candidates.json").write_text(
            json.dumps(self.research_payload), encoding="utf-8"
        )
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "coverage-audit.json").write_text(
            json.dumps(
                {
                    "publication_date": DATE,
                    "status": "ok",
                    "mode": "existing_digest_after_editorial_repair_error",
                    "audit_added_candidates": 1,
                    "editorial_rerun_required": True,
                    "editorial_rerun_performed": False,
                    "editorial_repair_error": "ModuleNotFoundError: No module named 'openai'",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(repair.EditorialRepairJournalError):
            repair.assert_publication_safe(artifact, state_dir=self.state_dir)

    def test_saved_response_is_applied_only_after_exact_artifact_match(self):
        output = {"selected_candidate_ids": ["candidate-1"]}
        calls = []
        self.call_repair(_FakeClient(calls, output=output))
        artifact = self.root / "automation/preview" / DATE
        artifact.mkdir(parents=True)
        (artifact / "candidates.json").write_text(
            json.dumps(self.research_payload), encoding="utf-8"
        )
        (artifact / "editorial-output-raw.json").write_text(
            json.dumps(output), encoding="utf-8"
        )
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "coverage-audit.json").write_text(
            json.dumps(
                {
                    "publication_date": DATE,
                    "status": "ok",
                    "editorial_rerun_required": True,
                    "editorial_rerun_performed": True,
                    "editorial_completion_required": False,
                    "editorial_completion_performed": False,
                }
            ),
            encoding="utf-8",
        )
        repair.assert_publication_safe(artifact, state_dir=self.state_dir)
        self.assertEqual(repair._load_journal(self.context())["state"], "applied")

    def test_pending_repair_forces_partial_editorial_recovery(self):
        recovery_root = self.root / "recovery"
        source = recovery_root / "automation/preview" / DATE
        source.mkdir(parents=True)
        evidence_root = source.parent
        production = evidence_root / "production-daily"
        production.mkdir(parents=True)
        (production / "coverage-audit.json").write_text(
            json.dumps(
                {
                    "publication_date": DATE,
                    "editorial_rerun_required": True,
                    "editorial_rerun_performed": False,
                }
            ),
            encoding="utf-8",
        )
        with patch.object(
            recovery,
            "_PRE_CHOOSE_SOURCE",
            return_value=(source, "full", []),
        ), patch.object(recovery._pre, "_modern_primary_artifact", return_value=False):
            chosen, mode, diagnostics = recovery.choose_source(recovery_root, DATE)
        self.assertEqual(chosen, source)
        self.assertEqual(mode, "partial_editorial")
        self.assertTrue(
            any(row.get("status") == "editorial-repair-pending" for row in diagnostics)
        )

    def test_recovery_restorers_are_bound_to_selected_bundle(self):
        recovery_root = self.root / "recovery"
        selected = recovery_root / "run-a/automation/preview" / DATE
        selected.mkdir(parents=True)
        captured = []

        def fake_restore(root, *_args):
            captured.append(root.resolve())
            return None

        with patch.object(
            recovery,
            "_PRE_CHOOSE_SOURCE",
            return_value=(selected, "full", []),
        ), patch.object(recovery._pre, "_modern_primary_artifact", return_value=False), patch.object(
            recovery, "_PRE_RESTORE_MERGED", side_effect=fake_restore
        ):
            recovery.choose_source(recovery_root, DATE)
            recovery._restore_merged_same_bundle(
                recovery_root, self.root / "target", DATE
            )
        self.assertEqual(captured, [selected.parent.resolve()])

    def test_foreign_same_date_journal_is_rejected_before_new_call(self):
        recovery_root = self.root / "recovery"
        selected = recovery_root / "run-a/automation/preview" / DATE
        selected.mkdir(parents=True)
        foreign_state = recovery_root / "run-b/automation/preview/production-daily"
        foreign_context = self.context(state_dir=foreign_state)
        binding = repair.request_binding_sha256(self.kwargs)
        repair.prepare_and_check_replay(foreign_context, binding_sha256=binding)

        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "recovery.json").write_text(
            json.dumps(
                {
                    "selected_source": str(selected),
                    "recovery_root": str(recovery_root),
                    "merged_coverage_research": None,
                    "prior_coverage_audit": None,
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(repair.EditorialRepairJournalError):
            repair.prepare_and_check_replay(
                self.context(), binding_sha256=binding
            )


if __name__ == "__main__":
    unittest.main()
