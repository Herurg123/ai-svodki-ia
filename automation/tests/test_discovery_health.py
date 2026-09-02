from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from discovery_health import DEGRADED, HEALTHY, INDETERMINATE, evaluate_discovery_health


def primary(*, zero_raw: bool = False) -> dict:
    return {
        "status": "complete",
        "search_budget": {"maximum_calls": 12, "completed_calls": 12},
        "directions": [
            {
                "direction_id": "major_agencies",
                "status": "complete",
                "raw_candidates": [] if zero_raw else [{"title": "x"}],
            }
        ],
    }


def pulse(*, degraded: bool = False) -> dict:
    summary = {
        "configured_sources": 13,
        "sources_ok": 10 if degraded else 13,
        "sources_unavailable": 3 if degraded else 0,
        "sources_parse_error": 0,
        "lead_count": 3,
        "degraded_source_ids": ["baidu_ir", "tass_ai", "xpeng_ir"] if degraded else [],
        "source_health_status": "complete_with_gaps" if degraded else "complete",
    }
    return {
        "status": "complete_with_gaps" if degraded else "complete",
        "snapshot": {"summary": summary},
        "promotion": {"promoted_count": 1},
    }


def agency(*, metadata: bool | None = True) -> dict:
    return {
        "triggered": True,
        "trigger_reason": "major_agencies_raw_zero",
        "executed": True,
        "state": "completed_no_addition",
        "search_operation_count_contribution": 1,
        "source_metadata_available": metadata,
        "accepted_count": 0,
        "agency_health": {"status": "early_gap"},
    }


def hybrid(*, asia_gap: bool = False) -> dict:
    return {
        "status": "complete",
        "search_budget": {"completed_calls": 4},
        "retrieval_health": {
            "status": "complete_with_regional_gaps" if asia_gap else "complete",
            "regional_gaps": ["asia"] if asia_gap else [],
            "unresolved_regional_gaps": ["asia"] if asia_gap else [],
            "hybrid_conditional_paid_extension_used": False,
        },
    }


def coverage() -> dict:
    required = ["a", "b", "c", "d", "e", "f"]
    return {
        "status": "ok",
        "audit_status": "complete_with_gaps",
        "audit_state": "completed_usable",
        "required_directions": required,
        "checked_directions": required,
        "partial_directions": [],
        "unchecked_directions": [],
        "search_budget": {"completed_calls": 7},
        "retrieval_quality": {"status": "complete"},
    }


class DiscoveryHealthTests(unittest.TestCase):
    def test_sep2_full_volume_shape_is_still_degraded(self):
        report = evaluate_discovery_health(
            primary=primary(zero_raw=True),
            pulse=pulse(degraded=True),
            agency=agency(metadata=False),
            hybrid=hybrid(asia_gap=True),
            coverage=coverage(),
        )
        self.assertEqual(report["status"], DEGRADED)
        self.assertTrue(report["story_volume_independent"])
        self.assertEqual(report["paid_api_calls"], 0)
        self.assertEqual(report["web_search_operations"], 0)
        self.assertEqual(report["lanes"]["primary"]["status"], HEALTHY)
        self.assertEqual(report["lanes"]["source_pulse"]["status"], DEGRADED)
        self.assertEqual(report["lanes"]["major_agencies"]["status"], INDETERMINATE)
        self.assertEqual(report["lanes"]["hybrid"]["status"], DEGRADED)
        self.assertEqual(report["lanes"]["coverage"]["status"], HEALTHY)

    def test_zero_raw_primary_direction_alone_does_not_degrade(self):
        report = evaluate_discovery_health(
            primary=primary(zero_raw=True),
            pulse=pulse(),
            agency={
                "triggered": False,
                "executed": False,
                "state": "not_triggered",
                "search_operation_count_contribution": 0,
                "source_metadata_available": None,
                "accepted_count": 1,
                "agency_health": {"status": "viable_primary_agency_survivor"},
            },
            hybrid=hybrid(),
            coverage=coverage(),
        )
        self.assertEqual(report["status"], HEALTHY)
        self.assertEqual(report["lanes"]["primary"]["status"], HEALTHY)
        self.assertEqual(
            report["lanes"]["primary"]["details"]["zero_raw_directions"],
            ["major_agencies"],
        )

    def test_missing_required_lane_is_indeterminate(self):
        report = evaluate_discovery_health(
            primary=primary(), pulse=None, agency=agency(), hybrid=hybrid(), coverage=coverage()
        )
        self.assertEqual(report["status"], INDETERMINATE)
        self.assertEqual(report["indeterminate_lanes"], ["source_pulse"])

    def test_explicit_degradation_wins_over_indeterminate(self):
        report = evaluate_discovery_health(
            primary=primary(), pulse=pulse(degraded=True), agency=None, hybrid=hybrid(), coverage=coverage()
        )
        self.assertEqual(report["status"], DEGRADED)
        self.assertIn("source_pulse", report["degraded_lanes"])
        self.assertIn("major_agencies", report["indeterminate_lanes"])

    def test_coverage_bounded_complete_with_gaps_can_still_be_healthy(self):
        report = evaluate_discovery_health(
            primary=primary(), pulse=pulse(), agency=agency(), hybrid=hybrid(), coverage=coverage()
        )
        lane = report["lanes"]["coverage"]
        self.assertEqual(lane["status"], HEALTHY)
        self.assertTrue(lane["details"]["bounded_gaps_usable"])


if __name__ == "__main__":
    unittest.main()
