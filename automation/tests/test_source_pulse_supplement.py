from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = AUTOMATION_ROOT / "scripts"
for module_name in ("source_pulse", "story_coverage", "source_freshness", "source_pulse_shadow"):
    if module_name not in sys.modules:
        path = SCRIPTS_ROOT / f"{module_name}.py"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

MODULE_PATH = SCRIPTS_ROOT / "source_pulse_supplement.py"
spec = importlib.util.spec_from_file_location("source_pulse_supplement", MODULE_PATH)
supplement = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = supplement
spec.loader.exec_module(supplement)
sp = sys.modules["source_pulse"]


def _window() -> dict:
    return {
        "start_at": "2026-08-25T02:00:00+03:00",
        "end_at": "2026-08-27T06:00:00+03:00",
        "start_date": "2026-08-25",
        "end_date": "2026-08-27",
        "latest_archive_at": "2026-08-25T02:00:00+03:00",
        "latest_archive_date": "2026-08-25",
    }


def _lead(*, tier: str = "A", role: str = "official", title: str = "MWS AI launches Cotype 3 agents", url: str = "https://mws.example/news/ai", region: str = "russia") -> dict:
    day = datetime.fromisoformat("2026-08-26").date()
    return {
        "source_id": "mws_news" if region == "russia" else "x",
        "tier": tier,
        "region": region,
        "role": role,
        "title": title,
        "url": url,
        "published_date": "2026-08-26",
        "published_at": None,
        "time_precision": "date",
        "cutoff_ambiguous": False,
        "source_item_id": url,
        "event_fingerprint": sp.event_fingerprint(title, day),
        "exact_fingerprint": sp.exact_fp(title, url, day),
        "archive_url_duplicate": False,
    }


def _snapshot(lead: dict) -> dict:
    return {
        "version": 1,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "summary": {
            "configured_sources": 1,
            "sources_ok": 1,
            "sources_unavailable": 0,
            "sources_parse_error": 0,
            "lead_count": 1,
            "eligible_new_lead_count": 1,
            "tier_a_leads": 1 if lead["tier"] == "A" else 0,
            "tier_b_leads": 1 if lead["tier"] == "B" else 0,
        },
        "sources": [],
        "leads": [lead],
        "snapshot_hash": "fixture-snapshot",
    }


def _fresh_page(title: str = "MWS AI launches Cotype 3 agents") -> tuple[str, str, int]:
    body = f'''<html><head>
<meta property="article:published_time" content="2026-08-26T10:00:00+03:00">
<meta name="description" content="{title}. The official release describes new AI agents and an expanded model platform for enterprise customers.">
</head><body><p>The company says the AI platform now includes multiple agent workflows for enterprise customers.</p></body></html>'''
    return body, "https://mws.example/news/ai", 200


class SourcePulseParserV11Tests(unittest.TestCase):
    def test_visible_sibling_russian_date_is_associated_with_link(self):
        body = '''<html><body><div class="news-item">
<a href="/news/ai">MWS AI revenue grows and Cotype 3 launches</a>
<span class="date">25 августа 2026 г.</span>
</div></body></html>'''
        items = supplement.parse_html_index_v11(body, "https://mws.example/news/")
        matching = [item for item in items if item.url == "https://mws.example/news/ai"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].published_date.isoformat(), "2026-08-25")
        self.assertEqual(matching[0].time_precision, "date")

    def test_visible_sibling_english_date_is_associated_with_link(self):
        body = '''<article><a href="/qwen">Alibaba Cloud launches QwenWork AI agents</a>
<div>August 26, 2026</div></article>'''
        items = supplement.parse_html_index_v11(body, "https://www.alibabacloud.com/blog")
        matching = [item for item in items if item.url.endswith("/qwen")]
        self.assertEqual(matching[0].published_date.isoformat(), "2026-08-26")


class SourcePulseSupplementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.research = root / "research.json"
        self.archive = root / "archive.json"
        self.registry = root / "registry.json"
        self.output = root / "diag"
        self.research.write_text(
            json.dumps({
                "status": "ok",
                "publication_date": "2026-08-27",
                "search_window": _window(),
                "coverage": [],
                "candidates": [],
                "regional_health": {
                    "asia": {"health_check_needed": True},
                    "russia": {"health_check_needed": True},
                },
            }) + "\n",
            encoding="utf-8",
        )
        self.archive.write_text('{"items": []}\n', encoding="utf-8")
        self.registry.write_text(
            json.dumps({
                "version": 1,
                "mode": "production_shadow",
                "production_integration": True,
                "candidate_influence": False,
                "supplemental_candidate_influence": True,
                "repoll_on_recovery": False,
                "sources": [{
                    "id": "mws_news",
                    "tier": "A",
                    "region": "russia",
                    "role": "official",
                    "publisher": "MWS",
                    "organization": "MWS",
                    "adapter": "html_index",
                    "url": "https://mws.example/news/",
                    "allowed_hosts": ["mws.example"],
                    "include_url_regex": "news|mws",
                    "max_items": 30,
                }],
            }) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_supplement(self, lead: dict, page=None, collector_calls=None):
        def collector(**kwargs):
            if collector_calls is not None:
                collector_calls.append(kwargs)
            return _snapshot(lead)
        if page is None:
            page = _fresh_page(lead["title"])
        def fetcher(url: str):
            return page
        return supplement.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-27",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=collector,
            page_fetcher=fetcher,
        )

    def test_tier_a_fresh_ai_lead_is_promoted_as_consider_without_paid_calls(self):
        report = self.run_supplement(_lead())
        research = json.loads(self.research.read_text(encoding="utf-8"))
        self.assertEqual(report["promotion"]["promoted_count"], 1)
        self.assertEqual(report["paid_api_calls"], 0)
        self.assertEqual(report["web_search_operations"], 0)
        self.assertEqual(len(research["candidates"]), 1)
        candidate = research["candidates"][0]
        self.assertEqual(candidate["recommendation"], "consider")
        self.assertEqual(candidate["audit_direction"], "source_pulse_v11")
        self.assertEqual(candidate["source_type"], "official")
        self.assertEqual(candidate["geography"], "russia")
        self.assertEqual(candidate["significance_score"], 3)
        self.assertTrue(candidate["verification_status"] == "verified")
        # Search-derived gap health is intentionally unchanged by Pulse.
        self.assertTrue(research["regional_health"]["russia"]["health_check_needed"])

    def test_tier_b_never_influences_candidate_pool(self):
        report = self.run_supplement(_lead(tier="B", role="lead_only"))
        research = json.loads(self.research.read_text(encoding="utf-8"))
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        self.assertEqual(research["candidates"], [])
        disposition = report["promotion"]["lead_dispositions"][0]
        self.assertEqual(disposition["reason"], "tier_b_or_nonofficial_lead_only")

    def test_stale_page_date_fails_closed(self):
        stale = '''<html><head><meta property="article:published_time" content="2026-08-20T10:00:00+03:00"><meta name="description" content="MWS AI launches a new enterprise agent platform with multiple workflows."></head></html>'''
        report = self.run_supplement(_lead(), page=(stale, "https://mws.example/news/ai", 200))
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        disposition = report["promotion"]["lead_dispositions"][0]
        self.assertEqual(disposition["reason"], "source_freshness_outside_window")

    def test_non_ai_official_release_is_diagnostic_only(self):
        lead = _lead(title="MWS opens a new office in Saint Petersburg")
        page = '''<html><head><meta property="article:published_time" content="2026-08-26T10:00:00+03:00"><meta name="description" content="The company opened a new office and expanded its local facilities for employees."></head></html>'''
        report = self.run_supplement(lead, page=(page, "https://mws.example/news/ai", 200))
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        self.assertEqual(report["promotion"]["lead_dispositions"][0]["reason"], "deterministic_ai_relevance_gate")

    def test_saved_snapshot_is_reused_without_second_poll(self):
        calls = []
        self.run_supplement(_lead(), collector_calls=calls)
        self.assertEqual(len(calls), 1)

        def exploding_collector(**kwargs):
            self.fail("saved mutable snapshot must be reused")

        second = supplement.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-27",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=exploding_collector,
            page_fetcher=lambda url: _fresh_page(),
        )
        self.assertTrue(second["reused_snapshot"])
        self.assertEqual(second["promotion"]["promoted_count"], 0)


class PrimaryIntegrationContractTests(unittest.TestCase):
    def test_source_pulse_supplement_runs_inside_primary_before_editorial_wrapper(self):
        text = (SCRIPTS_ROOT / "primary_recall_search.py").read_text(encoding="utf-8")
        self.assertIn("run_source_pulse_supplement", text)
        self.assertIn("_supplement_primary_research", text)
        self.assertIn("regional_health", text)
        self.assertIn("web_search_operations\": 0", text)


if __name__ == "__main__":
    unittest.main()
