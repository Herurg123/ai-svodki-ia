from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coverage = load_module("editorial_stop_coverage", SCRIPTS / "ensure_story_coverage.py")
summary = load_module("editorial_stop_summary", SCRIPTS / "summarize_production_status.py")


def complete_zero_report() -> dict[str, object]:
    return {
        "status": "error",
        "error": "RuntimeError: После основного и дополнительного поиска не осталось ни одного достойного сюжета",
        "audit_state": "completed_usable",
        "audit_error": None,
        "validation_error": None,
        "web_search_performed": True,
        "api": {"status": "completed"},
        "audit_status": "complete_with_gaps",
        "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
        "temporal_anchor_version": coverage.TEMPORAL_ANCHOR_VERSION,
        "recall_sentinel": {
            "status": "complete_with_gaps",
            "version": coverage.RECALL_SENTINEL_VERSION,
            "search_strategy": coverage.RECALL_SENTINEL_STRATEGY,
        },
        "candidate_pool_after": {"total": 0, "world": 0, "russia": 0},
        "audit_needed": True,
        "search_budget": {"completed_calls": 7, "maximum_calls": 7},
        "required_directions": list(coverage.AUDIT_DIRECTION_IDS),
        "partial_directions": [],
        "unchecked_directions": [],
        "audit_added_candidates": 0,
    }


class EditorialStopRuntimeTests(unittest.TestCase):
    def test_complete_zero_pool_becomes_healthy_editorial_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "coverage-audit.json"
            report.write_text(json.dumps(complete_zero_report()), encoding="utf-8")
            self.assertTrue(coverage._promote_completed_zero_pool_editorial_stop(report))
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "editorial_stop")
            self.assertTrue(payload["editorial_stop"])
            self.assertEqual(payload["publication_mode"], "none")
            self.assertEqual(payload["mode"], "completed_zero_pool_editorial_stop")
            self.assertIsNone(payload["error"])

    def test_incomplete_audit_is_never_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "coverage-audit.json"
            payload = complete_zero_report()
            payload["audit_state"] = "completed_unusable"
            payload["audit_status"] = "partial"
            report.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(coverage._promote_completed_zero_pool_editorial_stop(report))
            unchanged = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(unchanged["status"], "error")

    def test_current_sentinel_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "coverage-audit.json"
            payload = complete_zero_report()
            payload["recall_sentinel"]["version"] = coverage.RECALL_SENTINEL_VERSION - 1
            report.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(coverage._promote_completed_zero_pool_editorial_stop(report))


class EditorialStopSummaryTests(unittest.TestCase):
    def test_successful_editorial_stop_has_non_error_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_root = Path(temp_dir) / "production-daily"
            report_root.mkdir(parents=True)
            payload = complete_zero_report()
            payload.update({"status": "editorial_stop", "editorial_stop": True, "error": None})
            (report_root / "coverage-audit.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            with mock.patch.object(summary, "REPORT_ROOT", report_root):
                markdown, annotation = summary.build_summary(
                    job_status="success",
                    publication_date="2026-08-09",
                    publish="true",
                    recovery_run_id="31299732706",
                    run_url="https://example.test/run",
                    commit_sha="",
                )
            self.assertIn("редакционная остановка", markdown)
            self.assertIn("штатный успешный no-publish", markdown)
            self.assertIn("Commit:** не создавался", markdown)
            self.assertIsNone(annotation)


class EditorialStopWorkflowContractTests(unittest.TestCase):
    def test_workflow_skips_post_coverage_publication_stages(self) -> None:
        workflow = (ROOT / ".github/workflows/daily-production.yml").read_text(encoding="utf-8")
        self.assertIn("id: coverage", workflow)
        self.assertIn("editorial_stop: ${{ steps.coverage.outputs.editorial_stop }}", workflow)
        self.assertIn(
            'data.get("status") in {"error", "editorial_stop"}', workflow
        )
        guard = "steps.coverage.outputs.editorial_stop != 'true'"
        self.assertGreaterEqual(workflow.count(guard), 9)
        for stage in (
            "Normalize and validate digest artifact",
            "Generate one production cover",
            "Build and validate candidate site",
            "Dry-run or promote candidate",
            "Commit production release",
        ):
            index = workflow.index(f"- name: {stage}")
            block = workflow[index : index + 500]
            self.assertIn(guard, block, stage)

    def test_docs_define_green_no_publish_contract(self) -> None:
        docs = "\n".join(
            [
                (ROOT / "README.md").read_text(encoding="utf-8"),
                (ROOT / "automation/README.md").read_text(encoding="utf-8"),
                (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
            ]
        )
        self.assertIn("normal successful `no-publish`", docs)
        self.assertIn("Technical partial/error audits remain", docs)
        self.assertIn("`high_signal_recall_sentinel` версии 8", docs)


if __name__ == "__main__":
    unittest.main()
