from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ensure_story_coverage imports story_coverage by module name.
story_coverage = load_module("story_coverage", SCRIPTS / "story_coverage.py")
recovery = load_module("resilient_recovery", SCRIPTS / "recover_digest_artifact.py")
audit = load_module("resilient_coverage", SCRIPTS / "ensure_story_coverage.py")
wrapper = load_module("resilient_digest_wrapper", SCRIPTS / "run_digest_preview.py")


class AgentWordingRegressionTests(unittest.TestCase):
    def test_meta_ai_adjective_is_not_ai_agent(self) -> None:
        self.assertFalse(
            wrapper.actual_prohibited_agent_form(
                "Meta AI агентные функции и подключение к календарю"
            )
        )

    def test_actual_forbidden_agent_forms_are_detected(self) -> None:
        self.assertTrue(wrapper.actual_prohibited_agent_form("Новый AI-агент работает в IDE"))
        self.assertTrue(wrapper.actual_prohibited_agent_form("An AI agent runs the task"))
        self.assertTrue(wrapper.actual_prohibited_agent_form("Доступны AI агенты для кода"))


class PartialRecoveryTests(unittest.TestCase):
    def _write_partial(self, directory: Path, publication_date: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "run-info.json").write_text(
            json.dumps(
                {
                    "publication_date": publication_date,
                    "finished_at": f"{publication_date}T04:36:00+00:00",
                    "research": {"status": "ok"},
                    "editorial": {
                        "status": "error",
                        "response": {"response_status": "completed"},
                    },
                }
            ),
            encoding="utf-8",
        )
        candidates = {
            "status": "ok",
            "publication_date": publication_date,
            "search_window": {
                "start_at": "2026-07-24T06:00:00+03:00",
                "end_at": "2026-07-25T06:00:00+03:00",
                "start_date": "2026-07-24",
                "end_date": "2026-07-25",
            },
            "candidates": [
                {"id": "cand-001", "geography": "world"},
                {"id": "cand-002", "geography": "russia"},
            ],
        }
        (directory / "candidates.json").write_text(
            json.dumps(candidates), encoding="utf-8"
        )
        (directory / "research-output-raw.json").write_text(
            json.dumps(candidates), encoding="utf-8"
        )
        editorial = {"selected_candidate_ids": ["cand-001", "cand-002"]}
        (directory / "editorial-output.json").write_text(
            json.dumps(editorial), encoding="utf-8"
        )
        (directory / "editorial-output-raw.json").write_text(
            json.dumps(editorial), encoding="utf-8"
        )

    def test_partial_editorial_artifact_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "download" / "2026-07-25"
            self._write_partial(source, "2026-07-25")
            target = root / "target"
            report = recovery.recover(
                root / "download",
                target,
                "2026-07-25",
                root / "report.json",
            )
            self.assertEqual(report["recovery_mode"], "partial_editorial")
            self.assertTrue((target / "candidates.json").is_file())
            self.assertFalse((target / "stories.json").exists())

    def test_partial_selected_geography_is_derived_without_stories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_partial(root, "2026-07-25")
            research = json.loads((root / "candidates.json").read_text())
            stories, mode = audit.load_initial_stories(root, research)
            self.assertEqual(mode, "partial_editorial")
            self.assertEqual(
                [item["geography"] for item in stories],
                ["world", "russia"],
            )


    def test_merged_coverage_research_is_restored_without_new_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "download" / "2026-07-25"
            self._write_partial(source, "2026-07-25")
            merged = json.loads((source / "candidates.json").read_text())
            merged["candidates"].append(
                {"id": "cand-003", "geography": "russia"}
            )
            merged_path = (
                root
                / "download"
                / "production-daily"
                / "coverage-audit-merged-candidates-2026-07-25.json"
            )
            merged_path.parent.mkdir(parents=True)
            merged_path.write_text(json.dumps(merged), encoding="utf-8")
            target = root / "target"
            report = recovery.recover(
                root / "download",
                target,
                "2026-07-25",
                root / "report.json",
            )
            self.assertIsNotNone(report["merged_coverage_research"])
            restored = json.loads((target / "candidates.json").read_text())
            self.assertEqual(len(restored["candidates"]), 3)

    def test_research_only_artifact_is_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "download" / "2026-07-25"
            self._write_partial(source, "2026-07-25")
            (source / "editorial-output.json").unlink()
            (source / "editorial-output-raw.json").unlink()
            report = recovery.recover(
                root / "download",
                root / "target",
                "2026-07-25",
                root / "report.json",
            )
            self.assertEqual(report["recovery_mode"], "research_only")


class CoverageRepairFlowTests(unittest.TestCase):
    def _candidate(self, candidate_id: str, geography: str) -> dict[str, object]:
        return {
            "id": candidate_id,
            "title": f"Story {candidate_id}",
            "organization": f"Org {candidate_id}",
            "published_date": "2026-07-25",
            "published_at": None,
            "time_precision": "date",
            "topic": "other",
            "event_type": "release",
            "keywords": ["ИИ"],
            "geography": geography,
            "category": "russia" if geography == "russia" else "other",
            "source_type": "official",
            "primary_source": {
                "title": f"Source {candidate_id}",
                "publisher": f"Publisher {candidate_id}",
                "url": f"https://example.com/{candidate_id}",
            },
            "supporting_sources": [],
            "event_summary": "Summary",
            "verified_facts": ["Fact one", "Fact two"],
            "significance": "Significant",
            "significance_score": 4,
            "limitations": "",
            "archive_status": "none",
            "archive_reason": "",
            "recommendation": "include",
        }

    def test_partial_recovery_runs_bounded_audit_then_editorial(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            artifact.mkdir()
            candidates = [
                self._candidate(f"cand-{index:03d}", "world")
                for index in range(1, 6)
            ] + [self._candidate("cand-006", "russia")]
            research = {
                "status": "ok",
                "error_message": None,
                "publication_date": "2026-07-25",
                "search_window": {
                    "start_at": "2026-07-24T06:00:00+03:00",
                    "end_at": "2026-07-25T06:00:00+03:00",
                    "latest_archive_at": None,
                    "start_date": "2026-07-24",
                    "end_date": "2026-07-25",
                    "latest_archive_date": None,
                },
                "coverage": [
                    {"area": f"area-{index}", "status": "covered", "notes": "ok"}
                    for index in range(1, 10)
                ],
                "candidates": candidates,
                "rejected_as_duplicates": [],
                "research_notes": "Initial research",
            }
            (artifact / "candidates.json").write_text(
                json.dumps(research), encoding="utf-8"
            )
            (artifact / "editorial-output.json").write_text(
                json.dumps(
                    {
                        "selected_candidate_ids": [
                            "cand-001", "cand-002", "cand-003",
                            "cand-004", "cand-005", "cand-006",
                        ]
                    }
                ),
                encoding="utf-8",
            )
            archive = root / "archive.json"
            archive.write_text(json.dumps({"items": []}), encoding="utf-8")
            report = root / "report.json"
            runtime_root = root / "fixtures"
            persisted_root = root / "preview"

            added = self._candidate("temporary", "world")
            added.pop("id")

            def fake_rerun_editorial(**kwargs):
                runtime_path = kwargs["merged_research_path"]
                self.assertTrue(runtime_path.is_file())
                merged = json.loads(runtime_path.read_text(encoding="utf-8"))
                self.assertEqual(len(merged["candidates"]), 7)
                stories = [
                    {"geography": "world"} for _ in range(6)
                ] + [{"geography": "russia"}]
                (artifact / "stories.json").write_text(
                    json.dumps(stories), encoding="utf-8"
                )

            argv = [
                "ensure_story_coverage.py",
                "--artifact-dir", str(artifact),
                "--archive", str(archive),
                "--publication-date", "2026-07-25",
                "--model", "gpt-5.6-terra",
                "--usual-total", "7",
                "--minimum-publishable", "1",
                "--maximum-audit-web-search-calls", "7",
                "--report", str(report),
            ]

            def fake_audit_request(**kwargs):
                prompt = str(kwargs["prompt"])
                direction_id = next(
                    item
                    for item in audit.AUDIT_DIRECTION_IDS
                    if f"Идентификатор направления: {item}" in prompt
                )
                return (
                    {
                        "status": "complete_with_gaps",
                        "error_message": None,
                        "direction_id": direction_id,
                        "candidates": (
                            [added]
                            if direction_id == "general_coverage_gaps"
                            else []
                        ),
                        "rejections": [],
                        "notes": "one candidate" if direction_id == "general_coverage_gaps" else "checked",
                    },
                    {
                        "status": "completed",
                        "web_search_calls": 1,
                        "web_search_calls_completed": 1,
                        "web_search_call_items_total": 1,
                        "actual_queries": [f"query for {direction_id}"],
                        "consulted_sources": [],
                    },
                )

            with (
                mock.patch.object(audit, "RUNTIME_RESEARCH_ROOT", runtime_root),
                mock.patch.object(audit, "PERSISTED_RESEARCH_ROOT", persisted_root),
                mock.patch.object(
                    audit,
                    "run_audit_request",
                    side_effect=fake_audit_request,
                ),
                mock.patch.object(audit, "rerun_editorial", side_effect=fake_rerun_editorial),
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
            ):
                result = audit.main()

            self.assertEqual(result, 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["mode"], "targeted_web_search_and_editorial_rerun")
            self.assertTrue(
                (persisted_root / "coverage-audit-merged-candidates-2026-07-25.json").is_file()
            )
            self.assertFalse((runtime_root / ".coverage-audit-2026-07-25.json").exists())



class WorkflowIntegrationTests(unittest.TestCase):
    def test_workflow_uses_wrapper_and_repairs_recovery(self) -> None:
        workflow = (ROOT / ".github/workflows/daily-production.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("run_digest_preview.py", workflow)
        self.assertIn("--allow-provisional-editorial", workflow)
        start = workflow.index("- name: Supplement a short digest when possible")
        end = workflow.index("- name:", start + 10)
        coverage_step = workflow[start:end]
        self.assertNotIn("if: inputs.recovery_run_id == ''", coverage_step)
        self.assertIn("Runs for both fresh and recovered artifacts", coverage_step)

    def test_runtime_research_uses_allowed_fixture_and_persists_recovery_copy(self) -> None:
        self.assertIn("automation/fixtures/research", str(audit.RUNTIME_RESEARCH_ROOT))
        self.assertIn("automation/preview/production-daily", str(audit.PERSISTED_RESEARCH_ROOT))


if __name__ == "__main__":
    unittest.main()
