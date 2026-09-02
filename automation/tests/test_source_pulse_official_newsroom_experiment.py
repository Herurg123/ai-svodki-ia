from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import source_freshness
import source_pulse_supplement_v13 as v13

FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "source-pulse-official-newsrooms-2026-09-02.json"
REGISTRY = ROOT / "automation" / "config" / "source-pulse-v1.json"


class OfficialNewsroomPulseExperimentTests(unittest.TestCase):
    def fixture(self) -> dict:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_experiment_does_not_enable_sources_in_production_registry(self):
        fixture = self.fixture()
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        configured = {str(row.get("id")) for row in registry.get("sources") or []}
        self.assertFalse(fixture["production_registry_mutation"])
        for case in fixture["cases"]:
            self.assertNotIn(case["id"], configured)
            self.assertEqual(case["decision"], "not_ready_for_registry")

    def test_bounded_article_cards_can_be_parsed_offline_for_all_three_hosts(self):
        for case in self.fixture()["cases"]:
            body = f"""
                <html><body>
                  <article class="news-card">
                    <a href="{case['article_url']}">{case['title']}</a>
                    <time>{case['published_date']}</time>
                  </article>
                </body></html>
            """
            rows = v13.parse_html_index_v13(body, case["index_url"])
            matches = [row for row in rows if row.url == case["article_url"]]
            self.assertEqual(len(matches), 1, case["id"])
            self.assertEqual(matches[0].published_date.isoformat(), case["published_date"])

    def test_visible_body_date_does_not_bypass_direct_page_freshness(self):
        body = "<html><body><h1>AI update</h1><p>August 31, 2026</p></body></html>"
        self.assertIsNone(source_freshness.extract_publication_evidence(body))

    def test_machine_readable_date_uses_existing_source_freshness_contract(self):
        body = (
            '<html><head><meta property="article:published_time" '
            'content="2026-08-31T12:00:00+00:00"></head><body></body></html>'
        )
        evidence = source_freshness.extract_publication_evidence(body)
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence.published_date.isoformat(), "2026-08-31")
        self.assertEqual(evidence.locator, "meta:article:published_time")

    def test_fixture_preserves_zero_paid_scope(self):
        fixture = self.fixture()
        self.assertEqual(fixture["paid_api_calls"], 0)
        self.assertEqual(fixture["web_search_operations_in_production"], 0)
        self.assertTrue(
            fixture["offline_contract"]["no_source_specific_repair_is_authorized_by_this_experiment"]
        )


if __name__ == "__main__":
    unittest.main()
