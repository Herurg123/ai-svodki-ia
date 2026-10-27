"""Offline guards for the single-use Terra 5.6 vs Terra 6.1 GitHub shadow."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))
import terra61_shadow_once as shadow


class Terra61OnceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(shadow, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.sha_patch = patch.object(shadow, "git_head", return_value="a" * 40)
        self.sha_patch.start()
        self.addCleanup(self.sha_patch.stop)
        for name in shadow.INPUT_PATHS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode("utf-8"))
        self.prod = self.root / "saved" / "production-daily"
        self.prod.mkdir(parents=True)
        self.evidence = self.root / "automation/preview/production-daily/terra61-comparison-reference.json"
        self.env_file = self.root / "env"
        self.window = {
            "start_at": "2026-10-26T04:12:00+03:00",
            "end_at": "2026-10-28T02:21:13+03:00",
            "latest_archive_at": "2026-10-27T06:00:00+03:00",
        }
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_RUN_ATTEMPT": "1"}):
            shadow.baseline(self.prod / shadow.BASELINE_NAME)
        shadow.write(self.prod / shadow.PRIMARY_NAME, {
            "status": "complete",
            "search_window": self.window,
            "search_budget": {"completed_calls": 12},
        })
        shadow.write(self.root / "saved" / shadow.DAY / "run-info.json", {
            "model_requested": shadow.PROD_MODEL,
            "research_cutoff_at": "2026-10-28T02:29:13+03:00",
        })

    def test_freezes_exact_inputs_models_and_two_separate_cutoffs(self) -> None:
        shadow.prepare(self.prod.parent, self.evidence, self.env_file, "a" * 40, "1234")
        report = shadow.read(self.evidence)
        self.assertEqual(report["source_sha"], "a" * 40)
        self.assertEqual(report["frozen_primary_search_window"], self.window)
        self.assertEqual(report["shadow_model"], "gpt-6.1-terra")
        env = self.env_file.read_text(encoding="utf-8")
        self.assertIn("AI_DIGEST_TERRA61_PRIMARY_CUTOFF=2026-10-28T02:21:13+03:00", env)
        self.assertIn("AI_DIGEST_TERRA61_EDITORIAL_CUTOFF=2026-10-28T02:29:13+03:00", env)

    def test_modified_archive_blocks_shadow_before_paid_request(self) -> None:
        (self.root / "automation/archive/index.json").write_bytes(b"mutated")
        with self.assertRaisesRegex(RuntimeError, "input hashes"):
            shadow.prepare(self.prod.parent, self.evidence, self.env_file, "a" * 40, "1234")
        self.assertFalse(self.env_file.exists())

    def test_wrong_checkout_sha_blocks_shadow(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "source SHA"):
            shadow.prepare(self.prod.parent, self.evidence, self.env_file, "b" * 40, "1234")

    def test_partial_primary_does_not_unlock_paid_comparison(self) -> None:
        p = self.prod / shadow.PRIMARY_NAME
        obj = shadow.read(p)
        obj["search_budget"]["completed_calls"] = 11
        shadow.write(p, obj)
        with self.assertRaisesRegex(RuntimeError, "twelve"):
            shadow.prepare(self.prod.parent, self.evidence, self.env_file, "a" * 40, "1234")

    def test_finished_manifest_requires_matching_model_and_coverage(self) -> None:
        shadow.prepare(self.prod.parent, self.evidence, self.env_file, "a" * 40, "1234")
        path = self.root / "automation/preview/production-daily" / shadow.PRIMARY_NAME
        shadow.write(path, {
            "search_window": self.window,
            "status": "complete",
        })
        shadow.write(self.root / "automation/preview" / shadow.DAY / "run-info.json", {
            "model_requested": shadow.SHADOW_MODEL,
            "research_cutoff_at": "2026-10-28T02:29:13+03:00",
        })
        shadow.write(self.root / "automation/preview/production-daily/coverage-audit.json", {
            "status": "complete",
        })
        manifest = self.root / "automation/preview/production-daily/terra61-shadow-manifest.json"
        shadow.finish(self.evidence, manifest)
        self.assertEqual(shadow.read(manifest)["status"], "complete")
        self.assertGreater(shadow.read(manifest)["saved_file_count"], 1)
        coverage_path = self.root / "automation/preview/production-daily/coverage-audit.json"
        coverage_path.unlink()
        with self.assertRaisesRegex(RuntimeError, "Coverage"):
            shadow.finish(self.evidence, manifest)
        self.assertEqual(shadow.read(manifest)["status"], "partial")

    def test_cannot_create_second_scheduled_baseline(self) -> None:
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule", "GITHUB_RUN_ATTEMPT": "2"}):
            with self.assertRaisesRegex(RuntimeError, "original scheduled"):
                shadow.baseline(self.root / "blocked.json")

    def test_workflow_is_one_day_only_and_never_pushes_from_shadow(self) -> None:
        wf = (ROOT / ".github/workflows/daily-production.yml").read_text(encoding="utf-8")
        block = wf.split("  terra61_shadow_once:", 1)[1].split("  final_status:", 1)[0]
        self.assertIn("github.run_attempt == 1", block)
        self.assertIn("github.event_name == 'schedule'", block)
        self.assertIn("needs.deploy.result == 'success'", block)
        self.assertIn("needs.gate.outputs.publication_date == '2026-10-28'", block)
        self.assertIn("contents: read", block)
        self.assertNotIn("contents: write", block)
        self.assertNotIn("push_protected_main.sh", block)
        self.assertNotIn("create_production_image_request.py", block)
        self.assertNotIn("generate_production_cover.py", block)
        self.assertNotIn("Commit production release", block)
        self.assertIn("terra61-shadow-2026-10-28", block)
        self.assertEqual(wf.count('cron: "17 23 * * *"'), 1)


if __name__ == "__main__":
    unittest.main()
