from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import agency_discovery_rescue as rescue


class Aug24AgencyRecoveryContractTests(unittest.TestCase):
    def test_reuters_only_provider_routing_is_bounded(self):
        tool = rescue._web_search_tool()
        self.assertEqual(rescue.AGENCY_DISCOVERY_RESCUE_VERSION, 3)
        self.assertEqual(tool["filters"]["allowed_domains"], ["reuters.com"])
        self.assertEqual(tool["search_context_size"], "high")
        self.assertEqual(rescue.MAXIMUM_SEARCH_OPERATIONS, 1)
        self.assertEqual(rescue.PIPELINE_MAXIMUM_SEARCH_OPERATIONS, 24)

    def test_query_is_date_free_and_publisher_neutral(self):
        query = rescue.AGENCY_DISCOVERY_RESCUE_QUERY
        self.assertEqual(
            query,
            "latest AI chips infrastructure financing earnings business deals policy security",
        )
        self.assertNotIn("Reuters", query)
        self.assertNotRegex(query, r"\bAP\b")
        self.assertNotRegex(query, r"\b20\d{2}\b")
        self.assertNotRegex(query.casefold(), r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b")
        self.assertNotIn("after:", query.casefold())
        self.assertNotIn("before:", query.casefold())
        self.assertNotIn("site:", query.casefold())

    def test_report_persists_expected_routing_contract(self):
        report = rescue._base_report(
            publication_date="2026-08-24",
            trigger_reason="major_agencies_raw_zero",
            trigger_facts={
                "major_agencies_status": "complete_with_gaps",
                "major_agencies_raw_count": 0,
                "major_agencies_accepted_count": 0,
            },
            candidate_pool_count=0,
        )
        self.assertEqual(report["version"], 3)
        self.assertEqual(report["allowed_domains"], ["reuters.com"])
        self.assertEqual(report["required_direct_source_hosts"], ["reuters.com"])
        self.assertEqual(report["search_context_size"], "high")
        self.assertTrue(report["candidate_count_independent_trigger"])

    def test_direct_reuters_is_allowed_but_ap_and_syndication_are_not(self):
        def candidate(url: str) -> dict[str, object]:
            return {"primary_source": {"url": url}}

        self.assertTrue(
            rescue._direct_agency_source(
                candidate("https://www.reuters.com/technology/example-2026-08-23/")
            )
        )
        self.assertFalse(
            rescue._direct_agency_source(
                candidate("https://apnews.com/article/example")
            )
        )
        self.assertFalse(
            rescue._direct_agency_source(
                candidate("https://finance.yahoo.com/news/reuters-example.html")
            )
        )
        self.assertFalse(
            rescue._direct_agency_source(
                candidate("https://www.tradingview.com/news/reuters.com%2C2026%3Aexample/")
            )
        )
        self.assertFalse(
            rescue._direct_agency_source(
                candidate("https://www.marketscreener.com/news/reuters-example")
            )
        )

    def test_out_of_sample_fixture_keeps_all_positive_and_negative_controls(self):
        fixture = json.loads(
            (ROOT / "automation" / "fixtures" / "recall" / "2026-08-24-agency-recovery.json").read_text(
                encoding="utf-8"
            )
        )
        positives = {item["id"] for item in fixture["positive_controls"]}
        self.assertEqual(
            positives,
            {
                "google-marvell-custom-ai-chips",
                "broadcom-ai-chip-financing",
                "alibaba-ai-cloud-earnings",
                "nvidia-cloverleaf-infrastructure",
                "nvidia-ai-server-price-hikes",
                "alibaba-share-placement-ai",
            },
        )
        negatives = {item["id"] for item in fixture["negative_controls"]}
        self.assertEqual(
            negatives,
            {
                "stale-reuters",
                "analysis-opinion",
                "syndicated-copy",
                "duplicate-event",
                "after-cutoff",
                "quiet-window",
            },
        )
        self.assertEqual(fixture["production_run"]["completed_search_operations"], 24)
        self.assertFalse(fixture["experiment_evidence"]["high_vs_medium_isolated_ab_completed"])


if __name__ == "__main__":
    unittest.main()
