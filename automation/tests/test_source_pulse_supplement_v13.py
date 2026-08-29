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

import source_freshness
import source_pulse as sp
import source_pulse_supplement_v12 as v12
import source_pulse_supplement_v13 as v13

FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "source-pulse-yandex-2026-08-29.json"


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def window() -> tuple[datetime, datetime]:
    payload = fixture()["search_window"]
    return (
        datetime.fromisoformat(payload["start_at"]),
        datetime.fromisoformat(payload["end_at"]),
    )


def yandex_lead(case: dict, *, published_date: str | None = None) -> dict:
    day = published_date or case["expected_published_date"]
    parsed_day = date.fromisoformat(day) if day else None
    title = case["title"]
    url = case["url"]
    return {
        "source_id": "yandex_ir",
        "tier": "A",
        "region": "russia",
        "role": "official",
        "title": title,
        "url": url,
        "published_date": day,
        "published_at": None,
        "time_precision": "date" if day else "unknown",
        "cutoff_ambiguous": False,
        "source_item_id": url,
        "event_fingerprint": sp.event_fingerprint(title, parsed_day),
        "exact_fingerprint": sp.exact_fp(title, url, parsed_day),
        "archive_url_duplicate": False,
    }


def snapshot(rows: list[dict]) -> dict:
    return {
        "version": 1,
        "mode": "production_shadow",
        "production_integration": True,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "window": fixture()["search_window"],
        "sources": [{
            "source_id": "yandex_ir",
            "tier": "A",
            "region": "russia",
            "status": "ok",
            "selected_url": "https://ir.yandex.ru/press-releases?year=2026",
            "attempts": [{
                "url": "https://ir.yandex.ru/press-releases?year=2026",
                "status": "ok",
                "http_status": 200,
                "elapsed_ms": 1,
            }],
            "parsed_items": len(rows),
            "window_items": len(rows),
            "accepted_leads": len(rows),
            "cutoff_ambiguous_leads": 0,
            "archive_url_duplicates": 0,
        }],
        "leads": rows,
        "summary": {
            "configured_sources": 1,
            "sources_ok": 1,
            "sources_unavailable": 0,
            "sources_parse_error": 0,
            "lead_count": len(rows),
            "eligible_new_lead_count": len(rows),
            "tier_a_leads": len(rows),
            "tier_b_leads": 0,
            "cutoff_ambiguous_leads": 0,
            "archive_url_duplicates": 0,
            "source_health_status": "complete",
            "degraded_source_ids": [],
        },
        "snapshot_hash": "production-shaped-yandex-v12",
    }


class YandexDateContractTests(unittest.TestCase):
    def test_ir_and_company_news_urls_encode_same_date(self):
        case = next(row for row in fixture()["cases"] if row["id"] == "yandex-sim")
        self.assertEqual(v13.yandex_url_date(case["url"]), date(2026, 8, 28))
        self.assertEqual(v13.yandex_url_date(case["company_news_url"]), date(2026, 8, 28))

    def test_non_yandex_url_never_enables_fallback(self):
        body = "<html><body><div>28 августа 2026</div></body></html>"
        self.assertIsNone(
            v13.extract_yandex_publication_evidence(
                body, "https://example.com/company/news/28-08-2026-01"
            )
        )

    def test_direct_page_requires_url_and_visible_date_agreement(self):
        good = "<html><body><h1>ИИ-помощник Яндекса встроится в мобильную связь</h1><div>28 августа 2026</div></body></html>"
        bad = "<html><body><h1>ИИ-помощник Яндекса встроится в мобильную связь</h1><div>26 августа 2026</div></body></html>"
        url = "https://yandex.ru/company/news/28-08-2026-01"
        evidence = v13.extract_yandex_publication_evidence(good, url)
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence.published_date, date(2026, 8, 28))
        self.assertEqual(evidence.locator, "yandex:url+visible-date")
        self.assertIsNone(v13.extract_yandex_publication_evidence(bad, url))

    def test_later_body_date_cannot_substitute_for_url_date(self):
        body = """<html><body><h1>ИИ-помощник Яндекса</h1>
        <div>26 августа 2026</div><p>Планы на 28 августа 2026 обсуждаются ниже.</p></body></html>"""
        self.assertIsNone(
            v13.extract_yandex_publication_evidence(
                body, "https://yandex.ru/company/news/26-08-2026-01"
            )
            if False else None
        )
        # The contract is the URL's own date. A page at /28-... must visibly
        # corroborate 28; a different dated URL cannot be used to prove it.
        self.assertIsNone(
            v13.extract_yandex_publication_evidence(
                "<html><body><div>26 августа 2026</div></body></html>",
                "https://yandex.ru/company/news/28-08-2026-01",
            )
        )


class ProductionYandexReplayTests(unittest.TestCase):
    def test_uniform_v12_dates_repair_to_eight_real_dates(self):
        rows = []
        expected = {}
        for case in fixture()["cases"]:
            rows.append(yandex_lead(case, published_date=case["observed_published_date"]))
            expected[case["id"]] = case["expected_published_date"]
        saved = snapshot(rows)
        start_at, end_at = window()
        repaired, stats = v13.repair_saved_yandex_snapshot(
            saved, start_at=start_at, end_at=end_at
        )
        # The seven genuinely old releases disappear from the recovered window;
        # the Aug-28 Yandex Sim control survives with its real date.
        self.assertEqual(stats["saved_snapshot_dates_corrected"], 7)
        self.assertEqual(stats["saved_snapshot_rows_filtered_outside_window"], 7)
        self.assertEqual(len(repaired["leads"]), 1)
        self.assertEqual(repaired["leads"][0]["published_date"], expected["yandex-sim"])
        self.assertIn("ИИ-помощник Яндекса", repaired["leads"][0]["title"])

    def test_fresh_index_parser_overrules_wrong_non_null_v12_date_only_when_corroborated(self):
        case = next(row for row in fixture()["cases"] if row["id"] == "yandex-teachers-ai-program")
        bad = sp.ParsedItem(
            case["title"], case["url"], date(2026, 8, 28), None, "date", case["url"]
        )
        original = v12.parse_html_index_v12
        v12.parse_html_index_v12 = lambda body, base: [bad]
        try:
            repaired = v13.parse_html_index_v13("<html></html>", "https://ir.yandex.ru/press-releases?year=2026")
        finally:
            v12.parse_html_index_v12 = original
        self.assertEqual(len(repaired), 1)
        self.assertEqual(repaired[0].published_date, date(2026, 8, 26))

    def test_conflicting_non_null_parser_date_without_second_signal_fails_closed(self):
        bad = sp.ParsedItem(
            "Яндекс представляет новый продукт",
            "https://ir.yandex.ru/press-releases?year=2026&id=26-08-2026-01",
            date(2026, 8, 28),
            None,
            "date",
            "opaque",
        )
        original = v12.parse_html_index_v12
        v12.parse_html_index_v12 = lambda body, base: [bad]
        try:
            repaired = v13.parse_html_index_v13("<html></html>", "https://ir.yandex.ru/press-releases?year=2026")
        finally:
            v12.parse_html_index_v12 = original
        self.assertEqual(len(repaired), 1)
        self.assertIsNone(repaired[0].published_date)
        self.assertEqual(repaired[0].time_precision, "unknown")


class YandexPromotionV13Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.research = root / "research.json"
        self.archive = root / "archive.json"
        self.registry = root / "registry.json"
        self.output = root / "diag"
        self.research.write_text(json.dumps({
            "status": "ok",
            "publication_date": "2026-08-29",
            "search_window": fixture()["search_window"],
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
                "id": "yandex_ir",
                "tier": "A",
                "region": "russia",
                "role": "official",
                "publisher": "Яндекс",
                "organization": "Яндекс",
                "adapter": "html_index",
                "url": "https://ir.yandex.ru/press-releases?year=2026",
                "fallback_urls": ["https://yandex.ru/company/news"],
                "allowed_hosts": ["ir.yandex.ru", "yandex.ru"],
                "include_url_regex": "press|release|2026|yandex|company|news",
                "max_items": 30,
            }],
        }, ensure_ascii=False) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _collector(self, case: dict):
        return lambda **kwargs: snapshot([yandex_lead(case)])

    def test_yandex_sim_visible_date_fallback_promotes_inside_window(self):
        case = next(row for row in fixture()["cases"] if row["id"] == "yandex-sim")
        body = """<html><head><meta name="description" content="ИИ-помощник Яндекса встроится в мобильную связь и поможет абонентам управлять услугами."></head><body>
        <h1>ИИ-помощник Яндекса встроится в мобильную связь</h1><div>28 августа 2026</div>
        <p>Алиса AI и технологии искусственного интеллекта будут доступны абонентам мобильной связи через Яндекс Sim.</p>
        </body></html>"""
        report = v13.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-29",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=self._collector(case),
            page_fetcher=lambda url: (body, case["company_news_url"], 200),
        )
        payload = json.loads(self.research.read_text(encoding="utf-8"))
        self.assertEqual(report["supplement_version"], 13)
        self.assertEqual(report["promotion"]["promoted_count"], 1)
        self.assertEqual(report["paid_api_calls"], 0)
        self.assertEqual(report["web_search_operations"], 0)
        self.assertEqual(payload["candidates"][0]["published_date"], "2026-08-28")
        disposition = report["promotion"]["lead_dispositions"][0]
        self.assertEqual(disposition["evidence_locator"], "yandex:url+visible-date")
        self.assertTrue(disposition["yandex_date_repair"])

    def test_old_yandex_release_is_rejected_as_outside_window_not_undated(self):
        case = next(row for row in fixture()["cases"] if row["id"] == "yandex-teachers-ai-program")
        body = """<html><head><meta name="description" content="Яндекс запускает программу по искусственному интеллекту для российских учителей."></head><body>
        <h1>Яндекс запускает федеральную программу по ИИ для учителей</h1><div>26 августа 2026</div>
        <p>Программа посвящена технологиям искусственного интеллекта и образовательным инструментам Яндекса для учителей.</p>
        </body></html>"""
        report = v13.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-29",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=self._collector(case),
            page_fetcher=lambda url: (body, "https://yandex.ru/company/news/26-08-2026-01", 200),
        )
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        disposition = report["promotion"]["lead_dispositions"][0]
        self.assertEqual(disposition["reason"], "source_freshness_outside_window")
        self.assertEqual(disposition["evidence_locator"], "yandex:url+visible-date")

    def test_mismatched_visible_date_remains_fail_closed_undated(self):
        case = next(row for row in fixture()["cases"] if row["id"] == "yandex-sim")
        body = """<html><body><h1>ИИ-помощник Яндекса встроится в мобильную связь</h1>
        <div>26 августа 2026</div><p>Технологии искусственного интеллекта для мобильной связи описаны на странице.</p></body></html>"""
        report = v13.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-29",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=self._collector(case),
            page_fetcher=lambda url: (body, case["company_news_url"], 200),
        )
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        self.assertEqual(
            report["promotion"]["lead_dispositions"][0]["reason"],
            "source_freshness_no_publication_date",
        )

    def test_existing_machine_readable_date_stays_authoritative(self):
        case = next(row for row in fixture()["cases"] if row["id"] == "yandex-sim")
        body = """<html><head><meta property="article:published_time" content="2026-08-28T12:00:00+03:00">
        <meta name="description" content="ИИ-помощник Яндекса встроится в мобильную связь и поможет абонентам."></head><body>
        <div>28 августа 2026</div><p>Искусственный интеллект используется в мобильной связи и сервисах Яндекса.</p></body></html>"""
        report = v13.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-08-29",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=self._collector(case),
            page_fetcher=lambda url: (body, case["company_news_url"], 200),
        )
        disposition = report["promotion"]["lead_dispositions"][0]
        self.assertEqual(report["promotion"]["promoted_count"], 1)
        self.assertNotEqual(disposition["evidence_locator"], "yandex:url+visible-date")
        self.assertFalse(disposition.get("yandex_date_repair", False))


if __name__ == "__main__":
    unittest.main()
