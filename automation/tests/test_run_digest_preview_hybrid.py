from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import run_digest_preview as runner


class RunDigestPreviewHybridTests(unittest.TestCase):
    def test_research_input_is_detected_for_paid_rerun_guard(self):
        argv = [
            "run_digest_preview.py",
            "--publication-date",
            "2026-08-09",
            "--research-input",
            "automation/preview/production-daily/merged.json",
        ]
        self.assertEqual(
            runner.research_input_from_argv(argv),
            "automation/preview/production-daily/merged.json",
        )

    def test_fresh_primary_has_no_research_input_guard(self):
        argv = [
            "run_digest_preview.py",
            "--publication-date",
            "2026-08-09",
        ]
        self.assertIsNone(runner.research_input_from_argv(argv))

    def test_hybrid_rollback_code_preserves_merged_candidates_for_coverage(self):
        source = (SCRIPT_DIR / "run_digest_preview.py").read_text(encoding="utf-8")
        self.assertIn('coverage_handoff_preserved', source)
        self.assertIn('_write_json(output_dir / "candidates.json", merged_payload)', source)
        self.assertIn('merged candidates preserved for coverage', source)

    def test_agency_rescue_survives_hybrid_failure_and_forces_editorial_rerun(self):
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp)
            merged_path = output_dir / "agency-rescue-merged.json"
            merged_path.write_text("{}\n", encoding="utf-8")
            rescue = {
                "version": 1,
                "search_strategy": "agency_discovery_rescue",
                "publication_date": "2026-08-23",
                "added_count": 1,
                "accepted_candidates": [{"title": "Recovered agency event"}],
                "merged_research_path": str(merged_path),
            }
            (output_dir / "agency-discovery-rescue.json").write_text(
                json.dumps(rescue), encoding="utf-8"
            )
            with mock.patch.object(
                runner, "_trusted_runtime_research_path", return_value=merged_path
            ):
                report = runner._agency_rescue_survival_report(
                    output_dir=output_dir,
                    publication_date="2026-08-23",
                    hybrid_error=RuntimeError("hybrid transport failed"),
                )
            self.assertIsNotNone(report)
            assert report is not None
            self.assertTrue(report["editorial_rerun_needed"])
            self.assertEqual(report["merged_research_path"], str(merged_path))
            self.assertEqual(report["pipeline_search_budget"]["maximum_total"], 24)
            self.assertIn("hybrid transport failed", report["hybrid_error"])

    def test_hybrid_failure_without_added_rescue_keeps_old_fail_open_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp)
            (output_dir / "agency-discovery-rescue.json").write_text(
                json.dumps({"added_count": 0}), encoding="utf-8"
            )
            report = runner._agency_rescue_survival_report(
                output_dir=output_dir,
                publication_date="2026-08-23",
                hybrid_error=RuntimeError("hybrid transport failed"),
            )
            self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()
