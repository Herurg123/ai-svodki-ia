from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import source_pulse as sp
import source_pulse_supplement_v12 as v12


def window() -> dict:
    return {
        "start_at": "2026-08-26T06:55:27+03:00",
        "end_at": "2026-08-28T04:43:51+03:00",
        "start_date": "2026-08-26",
        "end_date": "2026-08-28",
        "latest_archive_at": "2026-08-27T06:55:27+03:00",
        "latest_archive_date": "2026-08-27",
    }


def lead(*, role: str = "trusted_news", tier: str = "A") -> dict:
    title = "ТАСС: российская компания запустила новую платформу ИИ-агентов"
    url = "https://tass.ru/ekonomika/123456"
    day = date(2026, 8, 27)
    return {
        "source_id": "tass_ai",
        "tier": tier,
        "region": "russia",
        "role": role,
        "title": title,
        "url": url,
        "published_date": day.isoformat(),
        "published_at": None,
        "time_precision": "date",
        "cutoff_ambiguous": False,
        "source_item_id": url,
        "event_fingerprint": sp.event_fingerprint(title, day),
        "exact_fingerprint": sp.exact_fp(title, url, day),
        "archive_url_duplicate": False,
    }


def snapshot(row: dict) -> dict:
    return {
        "version": 1,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "sources": [{
            "source_id": row["source_id"],
            "tier": row["tier"],
            "region": row["region"],
            "status": "ok",
            "parsed_items": 1,
            "window_items": 1,
            "accepted_leads": 1,
        }],
        "leads": [row],
        "summary": {
            "configured_sources": 1,
            "sources_ok": 1,
            "sources_unavailable": 0,
            "sources_parse_error": 0,
            "lead_count": 1,
            "eligible_new_lead_count": 1,
            "tier_a_leads": 1 if row["tier"] == "A" else 0,
            "tier_b_leads": 1 if row["tier"] == "B" else 0,
            "source_health_status": "complete",
            "degraded_source_ids": [],
        },
        "snapshot_hash": "fixture-v12",
    }


class SourcePulseParserV12Tests(unittest.TestCase):
    def test_cnews_sibling_numeric_date_is_recovered(self):
        body = '''<html><body><div class="news-card">
<a href="/news/line/2026-08-27_sber_ai">Сбер представил новую платформу ИИ-агентов</a>
<div class="date">27.08.2026 13:26</div></div></body></html>'''
        items = v12.parse_html_index_v12(body, "https://www.cnews.ru/news/")
        rows = [item for item in items if "2026-08-27_sber_ai" in item.url]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].published_date.isoformat(), "2026-08-27")

    def test_yandex_date_before_link_is_recovered(self):
        body = '''<html><body><div class="press-release-row">
<span>26 августа 2026 г.</span>
<a href="/press-releases?id=26-08-2026-01">Яндекс запускает федеральную программу по ИИ для учителей</a>
</div></body></html>'''
        items = v12.parse_html_index_v12(body, "https://ir.yandex.ru/")
        rows = [item for item in items if "26-08-2026-01" in item.url]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].published_date.isoformat(), "2026-08-26")

    def test_relative_russian_date_is_bounded_to_reference_day(self):
        v12._PARSER_REFERENCE_DATE = date(2026, 8, 28)
        try:
            parsed, _dt, precision = v12._parse_visible_date("Вчера 13:26")
        finally:
            v12._PARSER_REFERENCE_DATE = None
        self.assertEqual(parsed, date(2026, 8, 27))
        self.assertEqual(precision, "date")

    def test_yandex_cap_is_larger_but_unknown_hosts_keep_core_cap(self):
        self.assertGreater(v12._max_bytes("https://ir.yandex.ru/press-releases"), sp.MAX_BYTES)
        self.assertEqual(v12._max_bytes("https://example.com/news"), sp.MAX_BYTES)

    def test_http200_links_without_dates_are_reported_degraded(self):
        src = sp.SourceDefinition(
            "cnews_ai", "B", "russia", "lead_only", "html_index",
            "https://www.cnews.ru/news/", ("cnews.ru",), (), 30,
            "news|cnews", None,
        )
        body = '<html><body><a href="/news/line/fresh-ai">Свежая новость про ИИ без даты</a></body></html>'

        def fetcher(url, hosts):
            return sp.FetchOutcome(url, url, "ok", 200, body, None, 1)

        report = v12.run_source_pulse_v12(
            registry=[src],
            start_at=datetime.fromisoformat("2026-08-26T06:55:27+03:00"),
            end_at=datetime.fromisoformat("2026-08-28T04:43:51+03:00"),
            archive={"items": []},
            fetcher=fetcher,
        )
        self.assertEqual(report["summary"]["source_health_status"], "complete_with_gaps")
        self.assertIn("cnews_ai", report["summary"]["degraded_source_ids"])


class SourcePulseTrustedNewsV12Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.research = root / "research.json"
        self.archive = root / "archive.json"
        self.registry = root / "registry.json"
        self.output = root / "diag"
        self.research.write_text(json.dumps({
            "status": "ok",
            "publication_date": "2026-08-28",
            "search_window": window(),
            "coverage": [],
            "candidates": [],
            "regional_health": {"russia": {"health_check_needed": True}},
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        self.archive.write_text('{"items": []}\n', encoding="utf-8")
        self.registry.write_text(json.dumps({
            "version": 1,
            "mode": "production_shadow",
            "production_integration": True,
            "candidate_influence": False,
            "supplemental_candidate_influence": True,
            "repoll_on_recovery": False,
            "sources": [{
                "id": "tass_ai",
                "tier": "A",
                "region": "russia",
                "role": "trusted_news",
                "publisher": "ТАСС",
                "organization": "ТАСС",
                "adapter": "html_index",
                "url": "https://tass.ru/tag/iskusstvennyi-intellekt",
                "allowed_hosts": ["tass.ru"],
                "include_url_regex": "tass|ai|intellekt",
                "max_items": 30,
            }],
        }, ensure_ascii=False) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_tass_tier_a_trusted_news_can_only_promote_as_consider(self):
        row = lead()

        def collector(**kwargs):
            return snapshot(row)

        body = '''<html><head>
<meta property="article:published_time" content="2026-08-27T13:26:00+03:00">
<meta name="description" content="Новая российская платформа ИИ-агентов для бизнеса.">
</head><body>Искусственный интеллект и ИИ-агенты внедряются в компании.</body></html>'''

        report = v12.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-28",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=collector,
            page_fetcher=lambda url: (body, "https://tass.ru/ekonomika/123456", 200),
        )
        payload = json.loads(self.research.read_text(encoding="utf-8"))
        self.assertEqual(report["promotion"]["promoted_count"], 1)
        self.assertEqual(report["paid_api_calls"], 0)
        self.assertEqual(report["web_search_operations"], 0)
        self.assertEqual(payload["candidates"][0]["recommendation"], "consider")
        self.assertEqual(payload["candidates"][0]["source_type"], "news_agency")
        self.assertEqual(payload["candidates"][0]["audit_direction"], "source_pulse_v12")
        self.assertTrue(payload["regional_health"]["russia"]["health_check_needed"])

    def test_tass_redirect_outside_allowlist_fails_closed(self):
        row = lead()
        body = '<meta property="article:published_time" content="2026-08-27T13:26:00+03:00"><p>ИИ платформа</p>'
        report = v12.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-28",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=lambda **kwargs: snapshot(row),
            page_fetcher=lambda url: (body, "https://example.com/copied-story", 200),
        )
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        self.assertEqual(
            report["promotion"]["lead_dispositions"][0]["reason"],
            "trusted_news_redirect_outside_source_allowlist",
        )

    def test_tier_b_stays_lead_only(self):
        row = lead(role="lead_only", tier="B")
        row["source_id"] = "cnews_ai"
        self.registry.write_text(json.dumps({
            "version": 1,
            "mode": "production_shadow",
            "production_integration": True,
            "candidate_influence": False,
            "supplemental_candidate_influence": True,
            "repoll_on_recovery": False,
            "sources": [{
                "id": "cnews_ai", "tier": "B", "region": "russia",
                "role": "lead_only", "publisher": "CNews", "organization": "CNews",
                "adapter": "html_index", "url": "https://www.cnews.ru/news/",
                "allowed_hosts": ["cnews.ru"], "include_url_regex": "news|cnews",
                "max_items": 30,
            }],
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        report = v12.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-28",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=lambda **kwargs: snapshot(row),
            page_fetcher=lambda url: self.fail("Tier B must not be page-promoted"),
        )
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        self.assertEqual(
            report["promotion"]["lead_dispositions"][0]["reason"],
            "tier_b_or_untrusted_lead_only",
        )


class ProductionRegistryV12Tests(unittest.TestCase):
    def test_tass_is_tier_a_trusted_news_and_cnews_remains_tier_b(self):
        config = json.loads((ROOT / "automation" / "config" / "source-pulse-v1.json").read_text(encoding="utf-8"))
        rows = {row["id"]: row for row in config["sources"]}
        self.assertEqual(rows["tass_ai"]["url"], "https://tass.ru/tag/iskusstvennyi-intellekt")
        self.assertEqual(rows["tass_ai"]["tier"], "A")
        self.assertEqual(rows["tass_ai"]["role"], "trusted_news")
        self.assertEqual(rows["yandex_ir"]["tier"], "A")
        self.assertEqual(rows["cnews_ai"]["tier"], "B")
        self.assertEqual(rows["cnews_ai"]["role"], "lead_only")


if __name__ == "__main__":
    unittest.main()
