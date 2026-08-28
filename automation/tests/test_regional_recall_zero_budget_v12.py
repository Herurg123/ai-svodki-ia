from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agency_discovery_rescue_v4 as agency_v4
import hybrid_search_completeness as hybrid
from story_coverage import write_json


def research(*, asia: bool, russia: bool) -> dict:
    return {
        "status": "ok",
        "publication_date": "2026-08-28",
        "search_window": {
            "start_at": "2026-08-26T06:55:27+03:00",
            "end_at": "2026-08-28T04:43:51+03:00",
            "start_date": "2026-08-26",
            "end_date": "2026-08-28",
            "latest_archive_at": "2026-08-27T06:55:27+03:00",
            "latest_archive_date": "2026-08-27",
        },
        "coverage": [],
        "candidates": [],
        "regional_health": {
            "asia": {"health_check_needed": asia},
            "russia": {"health_check_needed": russia},
        },
        "research_notes": "test",
    }


def metadata(query: str) -> dict:
    return {
        "status": "completed",
        "web_search_calls_completed": 1,
        "web_search_call_items_total": 1,
        "web_search_navigation_items_total": 0,
        "actual_queries": [query],
        "consulted_sources": [],
    }


class RegionalHybridV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.artifact = root / "artifact"
        self.output = root / "output"
        self.archive = root / "archive.json"
        self.artifact.mkdir()
        write_json(self.archive, {"items": []})
        self.old_rescue = hybrid.run_agency_discovery_rescue
        self.old_pulse = hybrid.run_source_pulse_shadow
        hybrid.run_agency_discovery_rescue = lambda **kwargs: {
            "version": 4,
            "search_strategy": "agency_discovery_rescue",
            "publication_date": "2026-08-28",
            "triggered": False,
            "executed": False,
            "state": "not_triggered",
            "status": "complete",
            "search_operation_count_contribution": 0,
            "added_count": 0,
            "accepted_count": 0,
        }
        hybrid.run_source_pulse_shadow = lambda **kwargs: {
            "version": 1,
            "strategy": "source_pulse_shadow",
            "publication_date": "2026-08-28",
            "state": "reused_snapshot",
            "status": "complete_with_gaps",
            "fusion": {"summary": {"pulse_only_count": 0, "both_count": 0}},
            "promotion": {"promoted_count": 0},
            "paid_api_calls": 0,
            "web_search_operations": 0,
        }

    def tearDown(self):
        hybrid.run_agency_discovery_rescue = self.old_rescue
        hybrid.run_source_pulse_shadow = self.old_pulse
        self.temp.cleanup()

    def _run(self, *, asia: bool, russia: bool, maximum_search_calls: int = 4):
        write_json(
            self.artifact / "candidates.json",
            research(asia=asia, russia=russia),
        )
        seen: list[tuple[str, str, str]] = []

        def request_fn(**kwargs):
            prompt = kwargs["prompt"]
            if hybrid.REGIONAL_QUERIES["asia"] in prompt:
                query = hybrid.REGIONAL_QUERIES["asia"]
            elif hybrid.REGIONAL_QUERIES["russia"] in prompt:
                query = hybrid.REGIONAL_QUERIES["russia"]
            else:
                query = kwargs["direction_id"]
            seen.append((kwargs["direction_id"], query, prompt))
            return ({
                "status": "complete_with_gaps",
                "error_message": None,
                "direction_id": kwargs["direction_id"],
                "candidates": [],
                "rejections": [],
                "notes": "No additional event.",
            }, metadata(query))

        report = hybrid.run_hybrid_completeness(
            artifact_dir=self.artifact,
            archive_path=self.archive,
            publication_date="2026-08-28",
            api_key="test-key",
            model="test-model",
            maximum_search_calls=maximum_search_calls,
            request_fn=request_fn,
            output_root=self.output,
        )
        return report, seen

    def test_both_regional_gaps_preserve_three_fixed_and_add_one_fifth_call(self):
        report, seen = self._run(asia=True, russia=True)
        self.assertEqual(len(seen), 5)
        self.assertEqual(
            [row[0] for row in seen[:3]],
            [item["id"] for item in hybrid.COMPLETENESS_DIRECTIONS],
        )
        self.assertEqual(seen[3][1], hybrid.REGIONAL_QUERIES["asia"])
        self.assertEqual(seen[4][1], hybrid.REGIONAL_QUERIES["russia"])
        self.assertEqual(
            report["strategy"],
            "primary_plus_three_fixed_plus_split_russia_asia_paid_extension",
        )
        self.assertEqual(report["search_budget"]["base_maximum_calls"], 4)
        self.assertEqual(report["search_budget"]["maximum_calls"], 5)
        self.assertEqual(report["search_budget"]["completed_calls"], 5)
        self.assertTrue(report["conditional_paid_extension"]["used"])
        self.assertEqual(report["pipeline_search_budget"]["base_maximum_total"], 24)
        self.assertEqual(report["pipeline_search_budget"]["maximum_total"], 25)
        self.assertEqual(report["regional_health"]["gaps"], ["asia", "russia"])
        self.assertTrue(report["regional_health"]["split_when_both"])
        self.assertFalse(report["regional_health"]["publication_quota"])
        self.assertEqual(report["retrieval_health"]["additional_paid_searches"], 1)
        self.assertEqual(report["retrieval_health"]["coverage_additional_paid_searches"], 0)

    def test_one_regional_gap_keeps_three_fixed_plus_one_regional(self):
        report, seen = self._run(asia=False, russia=True)
        self.assertEqual(len(seen), 4)
        self.assertEqual(
            [row[0] for row in seen[:3]],
            [item["id"] for item in hybrid.COMPLETENESS_DIRECTIONS],
        )
        self.assertEqual(seen[-1][1], hybrid.REGIONAL_QUERIES["russia"])
        self.assertEqual(report["search_budget"]["completed_calls"], 4)
        self.assertEqual(report["pipeline_search_budget"]["maximum_total"], 24)
        self.assertFalse(report["conditional_paid_extension"]["used"])
        self.assertEqual(report["regional_health"]["gaps"], ["russia"])
        self.assertEqual(report["retrieval_health"]["additional_paid_searches"], 0)

    def test_no_regional_gap_preserves_normal_three_call_hybrid(self):
        report, seen = self._run(asia=False, russia=False)
        self.assertEqual(len(seen), 3)
        self.assertEqual(report["search_budget"]["completed_calls"], 3)
        self.assertFalse(report["adaptive_needed"])
        self.assertFalse(report["conditional_paid_extension"]["used"])
        self.assertEqual(report["pipeline_search_budget"]["maximum_total"], 24)

    def test_lowered_baseline_cap_cannot_activate_paid_extension(self):
        report, seen = self._run(
            asia=True,
            russia=True,
            maximum_search_calls=3,
        )
        self.assertEqual(len(seen), 3)
        self.assertFalse(report["conditional_paid_extension"]["used"])
        self.assertLessEqual(report["search_budget"]["completed_calls"], 3)
        self.assertEqual(report["pipeline_search_budget"]["maximum_total"], 24)

    def test_oversized_config_is_clamped_to_five_only_on_double_gap(self):
        report, seen = self._run(
            asia=True,
            russia=True,
            maximum_search_calls=99,
        )
        self.assertEqual(len(seen), 5)
        self.assertEqual(report["search_budget"]["maximum_calls"], 5)
        self.assertEqual(report["pipeline_search_budget"]["maximum_total"], 25)

        report_single, seen_single = self._run(
            asia=True,
            russia=False,
            maximum_search_calls=99,
        )
        self.assertEqual(len(seen_single), 4)
        self.assertFalse(report_single["conditional_paid_extension"]["used"])
        self.assertEqual(report_single["pipeline_search_budget"]["maximum_total"], 24)

    def test_lifecycle_dedupe_rule_separates_preview_identity_from_final_release(self):
        prompt = hybrid.build_prompt(
            publication_date="2026-08-28",
            search_window=research(asia=True, russia=True)["search_window"],
            direction_id="models_products_research",
            direction_label="Models",
            direction_guidance="Find model releases.",
            existing_candidates=[],
            archive={"items": []},
        )
        self.assertIn("раскрытие автора анонимного preview", prompt)
        self.assertIn("финальный именованный релиз", prompt)
        self.assertIn("публикация весов", prompt)


class AgencyRescueV4Tests(unittest.TestCase):
    def test_query_is_gap_aware_but_stays_one_source_neutral_phrase(self):
        payload = research(asia=True, russia=True)
        query, gaps = agency_v4.gap_aware_query(payload)
        self.assertEqual(gaps, ("asia", "russia"))
        self.assertIn("China", query)
        self.assertIn("Russia", query)
        self.assertNotIn("Reuters", query)
        self.assertEqual(agency_v4.MAXIMUM_SEARCH_OPERATIONS, 1)
        # Agency rescue's own baseline remains 24; Hybrid v3 alone owns the
        # conditional fifth-call extension to 25.
        self.assertEqual(agency_v4.PIPELINE_MAXIMUM_SEARCH_OPERATIONS, 24)

    def test_no_regional_gap_preserves_v3_query(self):
        query, gaps = agency_v4.gap_aware_query(research(asia=False, russia=False))
        self.assertEqual(gaps, ())
        self.assertEqual(query, agency_v4._BASE_QUERY)


if __name__ == "__main__":
    unittest.main()
