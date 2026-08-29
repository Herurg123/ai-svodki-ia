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

import hybrid_search_completeness as hybrid
import regional_health_viability as viability
from story_coverage import read_json, write_json

FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "regional-health-viability-2026-08-29.json"


class RegionalHealthViabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def _refresh(self, research=None, primary=None):
        return viability.refresh_regional_health(
            primary_report=copy.deepcopy(primary or self.fixture["primary_report"]),
            current_research=copy.deepcopy(research or self.fixture["current_research"]),
        )

    def test_production_case_reopens_asia_after_stale_and_editorial_exclude(self) -> None:
        updated, report = self._refresh()
        self.assertEqual(report["status"], "complete")
        self.assertTrue(report["changed"])
        self.assertTrue(updated["regional_health"]["asia"]["health_check_needed"])
        self.assertEqual(updated["regional_health"]["asia"]["viable_candidates"], 0)
        self.assertTrue(updated["regional_health"]["asia"]["reopened_after_filtering"])
        self.assertTrue(updated["regional_health"]["russia"]["health_check_needed"])
        self.assertEqual(hybrid._regional_gaps(updated), ("asia", "russia"))

    def test_viable_consider_candidate_keeps_healthy_region_closed(self) -> None:
        research = copy.deepcopy(self.fixture["current_research"])
        research["candidates"][1]["recommendation"] = "consider"
        research["candidates"][1]["verification_status"] = "verified"
        updated, report = self._refresh(research=research)
        self.assertFalse(updated["regional_health"]["asia"]["health_check_needed"])
        self.assertEqual(updated["regional_health"]["asia"]["viable_candidates"], 1)
        self.assertEqual(report["regions"]["asia"]["status"], "viable")

    def test_same_title_different_source_cannot_impersonate_primary_candidate(self) -> None:
        research = copy.deepcopy(self.fixture["current_research"])
        qwen = research["candidates"][1]
        qwen["recommendation"] = "consider"
        qwen["verification_status"] = "verified"
        qwen["primary_source"] = {"url": "https://pulse.example.test/qwen-copy"}
        updated, report = self._refresh(research=research)
        self.assertFalse(updated["regional_health"]["asia"]["health_check_needed"])
        self.assertEqual(
            updated["regional_health"]["asia"]["viability_status"],
            "identity_incomplete_preserved",
        )
        self.assertEqual(report["regions"]["asia"]["unmatched"], 1)
        self.assertEqual(updated["regional_health"]["asia"]["viable_candidates"], 0)

    def test_existing_search_gap_never_closes_from_later_candidate(self) -> None:
        research = copy.deepcopy(self.fixture["current_research"])
        research["candidates"].append({
            "title": "Поздний Source Pulse кандидат из России",
            "recommendation": "include",
            "event_freshness_status": "fresh",
            "freshness_status": "new_event",
            "primary_source": {"url": "https://example.test/russia"},
            "supporting_sources": [],
        })
        updated, report = self._refresh(research=research)
        self.assertTrue(updated["regional_health"]["russia"]["health_check_needed"])
        self.assertEqual(report["regions"]["russia"]["status"], "already_open")

    def test_identity_ambiguity_preserves_prior_health_instead_of_spending_search(self) -> None:
        research = copy.deepcopy(self.fixture["current_research"])
        research["candidates"] = []
        updated, report = self._refresh(research=research)
        self.assertFalse(updated["regional_health"]["asia"]["health_check_needed"])
        self.assertEqual(
            updated["regional_health"]["asia"]["viability_status"],
            "identity_incomplete_preserved",
        )
        self.assertFalse(report["regions"]["asia"]["changed"])

    def test_primary_final_cap_drop_reopens_early_false_healthy_region(self) -> None:
        primary = copy.deepcopy(self.fixture["primary_report"])
        primary["final_candidates"] = []
        updated, report = self._refresh(primary=primary)
        self.assertTrue(updated["regional_health"]["asia"]["health_check_needed"])
        self.assertEqual(
            updated["regional_health"]["asia"]["viability_status"],
            "reopened_after_primary_final_cap",
        )
        self.assertTrue(report["regions"]["asia"]["changed"])

    def test_unknown_event_origin_does_not_make_an_eligible_candidate_nonviable(self) -> None:
        candidate = {
            "recommendation": "include",
            "event_freshness_status": "unknown",
            "freshness_status": "new_event",
        }
        self.assertTrue(viability.candidate_viable(candidate))

    def test_no_paid_or_coverage_budget_is_added(self) -> None:
        _, report = self._refresh()
        self.assertEqual(report["paid_api_calls"], 0)
        self.assertEqual(report["web_search_operations"], 0)
        self.assertEqual(hybrid.DEFAULT_MAXIMUM_SEARCH_CALLS, 4)
        self.assertEqual(hybrid.CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS, 5)
        self.assertEqual(hybrid.PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS, 24)
        self.assertEqual(hybrid.PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS, 25)

    def test_stable_hybrid_refreshes_saved_candidates_before_v3_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            write_json(artifact_dir / "primary-recall.json", self.fixture["primary_report"])
            write_json(artifact_dir / "candidates.json", self.fixture["current_research"])
            observed = {}

            def fake_v3(*args, **kwargs):
                current = read_json(artifact_dir / "candidates.json")
                observed["gaps"] = hybrid._regional_gaps(current)
                return {
                    "regional_health": {
                        "gaps": list(observed["gaps"]),
                        "checked": False,
                        "checks": {},
                    },
                    "conditional_paid_extension": {"used": False},
                }

            with mock.patch.object(hybrid._v3, "run_hybrid_completeness", side_effect=fake_v3), mock.patch.object(
                hybrid, "persist_report", return_value=None
            ):
                report = hybrid.run_hybrid_completeness(
                    artifact_dir=artifact_dir,
                    archive_path=artifact_dir / "archive.json",
                    publication_date="2026-08-29",
                    api_key="offline",
                    model="offline",
                    request_fn=lambda **kwargs: ({}, {}),
                )

            self.assertEqual(observed["gaps"], ("asia", "russia"))
            self.assertTrue(report["regional_health_viability"]["changed"])
            saved = read_json(artifact_dir / "candidates.json")
            self.assertTrue(saved["regional_health"]["asia"]["health_check_needed"])


if __name__ == "__main__":
    unittest.main()
