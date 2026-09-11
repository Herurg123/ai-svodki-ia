from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import editorial_repair_guard as repair
import ensure_story_coverage as coverage
import recover_digest_artifact as recovery

DATE = "2026-09-11"
MODEL = "gpt-5.6-terra"


class _FakeResponses:
    def __init__(self, client):
        self._client = client

    def create(self, **kwargs):
        self._client.calls.append(
            {"max_retries": self._client.max_retries, "kwargs": kwargs}
        )
        if self._client.error is not None:
            raise self._client.error
        return SimpleNamespace(
            id="resp-repair-1",
            model=kwargs.get("model", MODEL),
            status="completed",
            service_tier="default",
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            error=None,
            output_text=json.dumps(self._client.output),
            output=[],
            _transport={"openai_request_id": "req-repair-1"},
        )


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


class EditorialRepairRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "automation/preview/production-daily"
        self.artifact = self.root / "automation/preview" / DATE
        self.persisted = self.state / f"coverage-audit-merged-candidates-{DATE}.json"
        self.runtime = (
            self.root
            / "automation/fixtures/research"
            / f".coverage-audit-{DATE}.json"
        )
        self.archive = self.root / "automation/archive/index.json"
        self.artifact.mkdir(parents=True)
        self.state.mkdir(parents=True)
        self.runtime.parent.mkdir(parents=True)
        self.archive.parent.mkdir(parents=True)
        self.research = {
            "publication_date": DATE,
            "search_window": {
                "start_at": "2026-09-10T01:04:18+00:00",
                "end_at": "2026-09-11T01:05:09+00:00",
            },
            "candidates": [
                {
                    "id": "candidate-1",
                    "title": "Coverage candidate",
                    "recommendation": "include",
                }
            ],
        }
        self.write_json(self.persisted, self.research)
        self.write_json(self.runtime, self.research)
        self.write_json(self.archive, {"items": []})
        self.write_json(self.artifact / "candidates.json", self.research)
        self.write_json(self.artifact / "stories.json", [{"candidate_id": "old"}])

    @staticmethod
    def write_json(path: Path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def prepare(self, *, legacy: dict | None = None):
        legacy_path = None
        if legacy is not None:
            legacy_path = self.state / "coverage-audit.json"
            self.write_json(legacy_path, legacy)
        return repair.prepare_required(
            publication_date=DATE,
            state_dir=self.state,
            persisted_research_path=self.persisted,
            archive_path=self.archive,
            artifact_dir=self.artifact,
            model=MODEL,
            legacy_report_path=legacy_path,
        )

    def bind(self, context):
        repair.bind_post_freshness_pool(context, self.runtime)

    def request(self):
        return {
            "model": MODEL,
            "input": "PRIVATE_EDITORIAL_PROMPT",
            "reasoning": {"effort": "medium"},
            "text": {"format": {"type": "json_schema", "name": "digest"}},
            "store": False,
        }

    def response(self, output=None):
        return _FakeClient([], output=output).responses.create(model=MODEL)

    def journal(self):
        path = self.state / f"editorial-repair-{DATE}.json"
        return repair._load_raw_journal(path)

    def test_no_pending_obligation_does_not_create_state_or_block_publication(self):
        self.write_json(
            self.state / "coverage-audit.json",
            {
                "publication_date": DATE,
                "editorial_rerun_required": False,
                "editorial_rerun_performed": False,
            },
        )
        repair.publication_safe(self.artifact, self.state)
        self.assertIsNone(repair.journal_state(self.state, DATE))

    def test_obligation_is_durable_before_child_or_provider(self):
        context = self.prepare()
        self.assertEqual(repair.journal_state(self.state, DATE), "required")
        journal = self.journal()
        self.assertEqual(journal["research_sha256"], context.research_sha256)
        self.assertEqual(journal["candidate_pool_sha256"], context.candidate_pool_sha256)
        self.assertEqual(journal["archive_sha256"], context.archive_sha256)
        self.assertIsNone(journal["request_sha256"])
        self.assertIsNone(journal["post_freshness_candidate_pool_sha256"])

    def test_post_freshness_pool_is_bound_before_request_and_cannot_change(self):
        context = self.prepare()
        self.bind(context)
        first = self.journal()["post_freshness_candidate_pool_sha256"]
        changed = json.loads(json.dumps(self.research))
        changed["candidates"].append(
            {"id": "candidate-2", "title": "changed", "recommendation": "include"}
        )
        self.write_json(self.runtime, changed)
        with self.assertRaises(repair.EditorialRepairError):
            repair.bind_post_freshness_pool(context, self.runtime)
        self.assertEqual(self.journal()["post_freshness_candidate_pool_sha256"], first)

    def test_request_contract_includes_prompt_schema_and_cannot_change(self):
        context = self.prepare()
        self.bind(context)
        first = repair.request_sha256(self.request())
        self.assertIsNone(repair.prepare_request(context, first))
        changed = dict(self.request(), input="DIFFERENT_PROMPT")
        with self.assertRaises(repair.EditorialRepairError):
            repair.prepare_request(context, repair.request_sha256(changed))

    def test_protected_sdk_callback_uses_zero_retries(self):
        calls = []
        strict = repair.clone_no_retry_callback(_FakeClient(calls).responses.create)
        strict(model=MODEL, input="x")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["max_retries"], 0)

    def test_request_started_without_response_becomes_unknown_and_never_retries(self):
        context = self.prepare()
        self.bind(context)
        binding = repair.request_sha256(self.request())
        repair.prepare_request(context, binding)
        repair.begin_request(context, binding)
        with self.assertRaises(repair.EditorialRepairError):
            repair.prepare_request(context, binding)
        self.assertEqual(repair.journal_state(self.state, DATE), "unknown_after_request")
        with self.assertRaises(repair.EditorialRepairError):
            repair.prepare_request(context, binding)

    def test_response_fsynced_before_journal_transition_is_replayed_offline(self):
        context = self.prepare()
        self.bind(context)
        binding = repair.request_sha256(self.request())
        repair.prepare_request(context, binding)
        repair.begin_request(context, binding)
        response = self.response()
        repair._write_response(context, binding, response)
        replay = repair.prepare_request(context, binding)
        self.assertEqual(replay.output_text, response.output_text)
        self.assertEqual(repair.journal_state(self.state, DATE), "response_saved")

    def test_response_saved_validation_failure_replays_without_new_transport(self):
        context = self.prepare()
        self.bind(context)
        binding = repair.request_sha256(self.request())
        repair.prepare_request(context, binding)
        repair.begin_request(context, binding)
        response = self.response({"selected_candidate_ids": ["candidate-1"]})
        repair.save_response(context, binding, response)
        self.write_json(
            self.artifact / "editorial-output-raw.json",
            {"selected_candidate_ids": ["different"]},
        )
        with self.assertRaises(repair.EditorialRepairError):
            repair.mark_validated(context)
        replay = repair.prepare_request(context, binding)
        self.assertEqual(replay.output_text, response.output_text)
        self.assertEqual(repair.journal_state(self.state, DATE), "response_saved")

    def test_failed_before_request_is_retryable(self):
        context = self.prepare()
        self.bind(context)
        binding = repair.request_sha256(self.request())
        repair.prepare_request(context, binding)
        repair.mark_failed_before_request(context, "ModuleNotFoundError")
        self.assertEqual(repair.journal_state(self.state, DATE), "failed_before_request")
        self.assertIsNone(repair.prepare_request(context, binding))
        self.assertEqual(repair.journal_state(self.state, DATE), "prepared")

    def test_validated_response_must_exactly_match_final_raw_editorial(self):
        output = {"selected_candidate_ids": ["candidate-1"]}
        context = self.prepare()
        self.bind(context)
        binding = repair.request_sha256(self.request())
        repair.prepare_request(context, binding)
        repair.begin_request(context, binding)
        repair.save_response(context, binding, self.response(output))
        self.write_json(self.artifact / "editorial-output-raw.json", output)
        repair.mark_validated(context)
        self.write_json(
            self.state / "coverage-audit.json",
            {
                "publication_date": DATE,
                "editorial_rerun_required": True,
                "editorial_rerun_performed": True,
            },
        )
        repair.publication_safe(self.artifact, self.state)
        self.assertEqual(repair.journal_state(self.state, DATE), "validated")
        self.write_json(
            self.artifact / "editorial-output-raw.json",
            {"selected_candidate_ids": ["tampered"]},
        )
        with self.assertRaises(repair.EditorialRepairError):
            repair.publication_safe(self.artifact, self.state)

    def test_artifact_mutation_after_response_does_not_destroy_replay_identity(self):
        context = self.prepare()
        self.bind(context)
        binding = repair.request_sha256(self.request())
        repair.prepare_request(context, binding)
        repair.begin_request(context, binding)
        repair.save_response(context, binding, self.response())
        self.write_json(self.artifact / "digest.json", {"changed_after_response": True})
        reloaded = repair.load_required(
            publication_date=DATE,
            state_dir=self.state,
            persisted_research_path=self.persisted,
            archive_path=self.archive,
            artifact_dir=self.artifact,
            model=MODEL,
        )
        replay = repair.prepare_request(reloaded, binding)
        self.assertEqual(replay.status, "completed")

    def test_changed_persisted_pool_blocks_second_intent(self):
        self.prepare()
        changed = json.loads(json.dumps(self.research))
        changed["candidates"].append(
            {"id": "candidate-2", "title": "changed", "recommendation": "include"}
        )
        self.write_json(self.persisted, changed)
        with self.assertRaises(repair.EditorialRepairError):
            repair.load_required(
                publication_date=DATE,
                state_dir=self.state,
                persisted_research_path=self.persisted,
                archive_path=self.archive,
                artifact_dir=self.artifact,
                model=MODEL,
            )

    def test_sep11_legacy_missing_sdk_is_safe_to_admit_once(self):
        context = self.prepare(
            legacy={
                "publication_date": DATE,
                "editorial_rerun_required": True,
                "editorial_rerun_performed": False,
                "editorial_repair_error": "ModuleNotFoundError: No module named 'openai'",
            }
        )
        self.assertTrue(self.journal()["legacy_retry_authorized"])
        self.assertEqual(context.publication_date, DATE)

    def test_ambiguous_legacy_pending_repair_blocks_auto_retry(self):
        with self.assertRaises(repair.EditorialRepairError):
            self.prepare(
                legacy={
                    "publication_date": DATE,
                    "editorial_rerun_required": True,
                    "editorial_rerun_performed": False,
                    "editorial_repair_error": "connection reset after request",
                }
            )

    def test_old_seven_story_digest_with_pending_legacy_repair_is_not_publishable(self):
        self.write_json(
            self.artifact / "stories.json",
            [{"candidate_id": str(index)} for index in range(7)],
        )
        self.write_json(
            self.state / "coverage-audit.json",
            {
                "publication_date": DATE,
                "status": "ok",
                "mode": "existing_digest_after_editorial_repair_error",
                "editorial_rerun_required": True,
                "editorial_rerun_performed": False,
            },
        )
        with self.assertRaises(repair.EditorialRepairError):
            repair.publication_safe(self.artifact, self.state)

    def test_incomplete_coverage_full_recovery_forces_text_runtime(self):
        recovery_root = self.root / "recovery"
        source = recovery_root / DATE
        source.mkdir(parents=True)
        production = recovery_root / "production-daily"
        production.mkdir(parents=True)
        self.write_json(
            production / "coverage-audit.json",
            {
                "publication_date": DATE,
                "audit_status": "complete_with_gaps",
                "retrieval_quality_contract_version": 1,
                "retrieval_quality": {"status": "degraded"},
            },
        )
        with patch.object(
            recovery, "_PRE_CHOOSE_SOURCE", return_value=(source, "full", [])
        ), patch.object(recovery._pre, "_modern_primary_artifact", return_value=False):
            _chosen, mode, diagnostics = recovery.choose_source(recovery_root, DATE)
        self.assertEqual(mode, "partial_editorial")
        self.assertTrue(
            any(row.get("status") == "editorial-runtime-required" for row in diagnostics)
        )

    def test_completed_current_coverage_does_not_force_runtime_by_itself(self):
        recovery_root = self.root / "recovery-complete"
        source = recovery_root / DATE
        source.mkdir(parents=True)
        production = recovery_root / "production-daily"
        production.mkdir(parents=True)
        self.write_json(
            production / "coverage-audit.json",
            {
                "publication_date": DATE,
                "audit_status": "complete",
                "retrieval_quality_contract_version": 1,
                "retrieval_quality": {"status": "complete"},
                "editorial_rerun_required": False,
                "editorial_completion_required": False,
            },
        )
        with patch.object(
            recovery, "_PRE_CHOOSE_SOURCE", return_value=(source, "full", [])
        ), patch.object(recovery._pre, "_modern_primary_artifact", return_value=False):
            _chosen, mode, diagnostics = recovery.choose_source(recovery_root, DATE)
        self.assertEqual(mode, "full")
        self.assertFalse(
            any(row.get("status") == "editorial-runtime-required" for row in diagnostics)
        )

    def test_recovery_restorers_use_only_selected_bundle(self):
        recovery_root = self.root / "recovery-bundles"
        selected = recovery_root / "run-a" / DATE
        selected.mkdir(parents=True)
        captured = []

        def fake_restore(root, *_args):
            captured.append(root.resolve())
            return None

        with patch.object(
            recovery, "_PRE_CHOOSE_SOURCE", return_value=(selected, "full", [])
        ), patch.object(recovery._pre, "_modern_primary_artifact", return_value=False), patch.object(
            recovery, "_PRE_RESTORE_MERGED", side_effect=fake_restore
        ):
            recovery.choose_source(recovery_root, DATE)
            recovery._restore_merged_same_bundle(
                recovery_root, self.root / "target", DATE
            )
        self.assertEqual(captured, [selected.parent.resolve()])

    def test_deduped_second_recovery_cannot_erase_pending_obligation(self):
        calls = []
        with patch.object(coverage._pre, "main", return_value=0), patch.object(
            coverage, "_arg", side_effect=lambda name, default=None: DATE if name == "--publication-date" else default
        ), patch.object(coverage, "_report_path", return_value=None), patch.object(
            coverage, "journal_state", side_effect=["response_saved", "validated", "validated"]
        ), patch.object(
            coverage, "_resume_pending", side_effect=lambda date: calls.append(date)
        ), patch.object(coverage, "_finalize_report"), patch.object(
            coverage, "publication_safe"
        ):
            result = coverage.main()
        self.assertEqual(result, 0)
        self.assertEqual(calls, [DATE])


if __name__ == "__main__":
    unittest.main()
