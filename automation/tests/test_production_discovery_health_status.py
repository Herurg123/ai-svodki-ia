from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import summarize_production_status as status

DATE = "2026-09-02"


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class ProductionDiscoveryHealthStatusTests(unittest.TestCase):
    def test_pipeline_status_embeds_volume_independent_health(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_root = root / "automation" / "preview" / "production-daily"
            report_root.mkdir(parents=True)
            required = ["a", "b", "c", "d", "e", "f"]
            write(report_root / f"primary-recall-{DATE}.json", {
                "status": "complete",
                "search_budget": {"maximum_calls": 12, "completed_calls": 12},
                "directions": [{
                    "direction_id": "major_agencies",
                    "status": "complete",
                    "raw_candidates": [],
                }],
            })
            write(report_root / f"source-pulse-{DATE}.json", {
                "status": "complete_with_gaps",
                "snapshot": {"summary": {
                    "configured_sources": 13,
                    "sources_ok": 10,
                    "sources_unavailable": 3,
                    "sources_parse_error": 0,
                    "lead_count": 3,
                    "degraded_source_ids": ["baidu_ir", "tass_ai", "xpeng_ir"],
                    "source_health_status": "complete_with_gaps",
                }},
                "promotion": {"promoted_count": 1},
            })
            write(report_root / f"agency-discovery-rescue-{DATE}.json", {
                "triggered": True,
                "trigger_reason": "major_agencies_raw_zero",
                "executed": True,
                "state": "completed_no_addition",
                "search_operation_count_contribution": 1,
                "source_metadata_available": False,
                "accepted_count": 0,
                "agency_health": {"status": "early_gap"},
            })
            write(report_root / f"hybrid-completeness-{DATE}.json", {
                "status": "complete",
                "search_budget": {"completed_calls": 4},
                "retrieval_health": {
                    "status": "complete_with_regional_gaps",
                    "regional_gaps": ["asia"],
                    "unresolved_regional_gaps": ["asia"],
                    "hybrid_conditional_paid_extension_used": False,
                },
            })
            write(report_root / "coverage-audit.json", {
                "status": "ok",
                "audit_status": "complete_with_gaps",
                "audit_state": "completed_usable",
                "required_directions": required,
                "checked_directions": required,
                "partial_directions": [],
                "unchecked_directions": [],
                "search_budget": {"completed_calls": 7, "maximum_calls": 7},
                "retrieval_quality": {"status": "complete"},
                "audit_needed": True,
                "audit_added_candidates": 0,
                "editorial_rerun_performed": False,
            })
            output = report_root / "pipeline-status.json"
            summary = root / "summary.md"
            old_root = status.REPORT_ROOT
            try:
                status.REPORT_ROOT = report_root
                with patch.object(sys, "argv", [
                    "summarize_production_status.py",
                    "--job-status", "success",
                    "--publication-date", DATE,
                    "--publish", "false",
                    "--run-url", "https://example.invalid/run",
                    "--output", str(output),
                ]), patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
                    self.assertEqual(status.main(), 0)
            finally:
                status.REPORT_ROOT = old_root

            payload = json.loads(output.read_text(encoding="utf-8"))
            health = payload["discovery_health"]
            self.assertEqual(health["status"], "degraded")
            self.assertTrue(health["story_volume_independent"])
            self.assertEqual(health["web_search_operations"], 0)
            text = summary.read_text(encoding="utf-8")
            self.assertIn("### Discovery health", text)
            self.assertIn("Story volume", text)
            self.assertIn("source_pulse_status:complete_with_gaps", text)


if __name__ == "__main__":
    unittest.main()
