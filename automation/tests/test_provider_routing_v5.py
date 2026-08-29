from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agency_discovery_rescue_v5 as agency_v5
import hybrid_search_completeness as hybrid


class AgencyRescueV5Tests(unittest.TestCase):
    def test_regional_gap_is_diagnostic_only(self) -> None:
        primary = {
            "regional_health": {
                "asia": {"health_check_needed": False},
                "russia": {"health_check_needed": True},
            }
        }
        query, gaps = agency_v5.neutral_query(primary)
        self.assertEqual(gaps, ("russia",))
        self.assertEqual(query, agency_v5.AGENCY_DISCOVERY_RESCUE_QUERY)
        self.assertNotIn("Russia", query)
        self.assertIn("models", query)
        self.assertIn("research", query)
        self.assertEqual(agency_v5.MAXIMUM_SEARCH_OPERATIONS, 1)
        self.assertEqual(agency_v5.PIPELINE_MAXIMUM_SEARCH_OPERATIONS, 24)

    def test_missing_sources_field_is_metadata_unavailable(self) -> None:
        api = {
            "web_search_call_items": [
                {
                    "action_type": "search",
                    "action": {"type": "search", "query": "latest AI", "sources": None},
                }
            ]
        }
        state = agency_v5.source_metadata_state(api)
        self.assertFalse(state["source_metadata_available"])
        self.assertEqual(state["search_actions_missing_source_metadata"], 1)
        self.assertEqual(state["search_actions_with_source_metadata"], 0)

    def test_empty_but_present_sources_list_is_metadata_available(self) -> None:
        api = {
            "web_search_call_items": [
                {
                    "action_type": "search",
                    "action": {"type": "search", "query": "latest AI", "sources": []},
                }
            ]
        }
        state = agency_v5.source_metadata_state(api)
        self.assertTrue(state["source_metadata_available"])
        self.assertEqual(state["search_actions_with_source_metadata"], 1)
        self.assertEqual(state["search_actions_missing_source_metadata"], 0)


class HybridP3RoutingTests(unittest.TestCase):
    def test_stable_hybrid_routes_agency_rescue_through_v5(self) -> None:
        self.assertIs(hybrid.run_agency_discovery_rescue, agency_v5.run_agency_discovery_rescue)

    def test_asia_query_has_tencent_hunyuan_without_new_slot(self) -> None:
        query = hybrid.REGIONAL_QUERIES["asia"]
        self.assertIn("Tencent", query)
        self.assertIn("Hunyuan", query)
        self.assertEqual(hybrid.DEFAULT_MAXIMUM_SEARCH_CALLS, 4)
        self.assertEqual(hybrid.CONDITIONAL_DOUBLE_GAP_MAXIMUM_SEARCH_CALLS, 5)

    def test_russia_query_covers_product_and_copyright_training_data(self) -> None:
        query = hybrid.REGIONAL_QUERIES["russia"]
        for token in ("Яндекс", "Сбер", "авторское право", "данные", "обучение моделей"):
            self.assertIn(token, query)
        self.assertEqual(hybrid.PIPELINE_BASE_MAXIMUM_SEARCH_OPERATIONS, 24)
        self.assertEqual(hybrid.PIPELINE_DOUBLE_GAP_MAXIMUM_SEARCH_OPERATIONS, 25)


if __name__ == "__main__":
    unittest.main()
