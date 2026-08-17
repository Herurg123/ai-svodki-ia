from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"

spec = importlib.util.spec_from_file_location("source_freshness_test_module", SCRIPTS / "source_freshness.py")
assert spec and spec.loader
source_freshness = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = source_freshness
spec.loader.exec_module(source_freshness)


WINDOW = {
    "start_at": "2026-08-15T08:59:33+03:00",
    "end_at": "2026-08-17T02:33:51+03:00",
}


def candidate(*, primary_url: str, supporting: list[dict] | None = None, published_at=None, published_date="2026-08-16"):
    return {
        "id": "cand-001",
        "title": "Test candidate",
        "organization": "Example",
        "published_date": published_date,
        "published_at": published_at,
        "time_precision": "datetime" if published_at else "date",
        "topic": "test",
        "event_type": "test",
        "keywords": ["test"],
        "geography": "world",
        "category": "other",
        "source_type": "news_agency",
        "primary_source": {
            "title": "Primary",
            "publisher": "Primary Publisher",
            "url": primary_url,
        },
        "supporting_sources": supporting or [],
        "event_summary": "test",
        "verified_facts": ["a", "b"],
        "significance": "test",
        "significance_score": 4,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "model verification",
        "freshness_status": "new_event",
        "freshness_reason": "model claimed fresh",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


def research(row: dict) -> dict:
    return {
        "status": "ok",
        "publication_date": "2026-08-17",
        "search_window": dict(WINDOW),
        "coverage": [],
        "candidates": [row],
    }


def fetch_map(mapping):
    def fetch(url: str):
        value = mapping[url]
        if isinstance(value, Exception):
            raise value
        return value, url, 200
    return fetch


class PublicationMetadataTests(unittest.TestCase):
    def test_extracts_article_published_time(self):
        html = '<meta property="article:published_time" content="2026-08-16T13:57:00-07:00">'
        proof = source_freshness.extract_publication_evidence(html)
        self.assertIsNotNone(proof)
        self.assertEqual(proof.time_precision, "datetime")
        self.assertEqual(proof.published_at.isoformat(), "2026-08-16T13:57:00-07:00")

    def test_extracts_newsarticle_jsonld(self):
        html = '''<script type="application/ld+json">{
          "@context":"https://schema.org",
          "@type":"NewsArticle",
          "datePublished":"2026-07-31T06:11:53Z",
          "dateModified":"2026-08-16T00:00:00Z"
        }</script>'''
        proof = source_freshness.extract_publication_evidence(html)
        self.assertIsNotNone(proof)
        self.assertEqual(proof.published_at.isoformat(), "2026-07-31T06:11:53+00:00")
        self.assertIn("datePublished", proof.locator)

    def test_timezone_math_uses_python_not_model_conversion(self):
        html = '<meta property="article:published_time" content="2026-08-16T13:57:00-07:00">'
        proof = source_freshness.extract_publication_evidence(html)
        start = source_freshness._parse_aware(WINDOW["start_at"], "start")
        end = source_freshness._parse_aware(WINDOW["end_at"], "end")
        self.assertTrue(source_freshness.evidence_in_window(proof, start_at=start, end_at=end))

    def test_cutoff_day_date_only_fails_closed(self):
        html = '<meta itemprop="datePublished" content="2026-08-17">'
        proof = source_freshness.extract_publication_evidence(html)
        start = source_freshness._parse_aware(WINDOW["start_at"], "start")
        end = source_freshness._parse_aware(WINDOW["end_at"], "end")
        self.assertFalse(source_freshness.evidence_in_window(proof, start_at=start, end_at=end))


class SourceFreshnessCandidateTests(unittest.TestCase):
    def test_aug17_anthropic_ap_claim_is_excluded_by_real_page_date(self):
        url = "https://apnews.com/article/b0a2c284b981de79c55e2a33712f4bec"
        row = candidate(primary_url=url, published_date="2026-08-16")
        html = '''<script type="application/ld+json">{
          "@type":"NewsArticle",
          "datePublished":"2026-07-31T06:11:53Z"
        }</script>'''
        verified, report = source_freshness.verify_research_payload(
            research(row), fetcher=fetch_map({url: html})
        )
        fixed = verified["candidates"][0]
        self.assertEqual(fixed["recommendation"], "exclude")
        self.assertEqual(fixed["freshness_status"], "old_reprint")
        self.assertEqual(fixed["published_date"], "2026-07-31")
        self.assertEqual(report["excluded_outside_window"], 1)
        self.assertEqual(report["paid_api_calls"], 0)

    def test_fresh_supporting_source_can_replace_unverifiable_primary(self):
        primary = "https://www.bloomberg.com/example"
        support = "https://techcrunch.com/example"
        row = candidate(
            primary_url=primary,
            supporting=[{"title":"Support","publisher":"TechCrunch","url":support}],
        )
        mapping = {
            primary: '<html><head><title>No date</title></head></html>',
            support: '<meta property="article:published_time" content="2026-08-16T13:57:00-07:00">',
        }
        verified, report = source_freshness.verify_research_payload(
            research(row), fetcher=fetch_map(mapping)
        )
        fixed = verified["candidates"][0]
        self.assertEqual(fixed["recommendation"], "include")
        self.assertEqual(fixed["primary_source"]["url"], support)
        self.assertEqual(fixed["published_at"], "2026-08-16T13:57:00-07:00")
        self.assertEqual(report["verified_fresh"], 1)
        self.assertEqual(report["eligible_after"], 1)

    def test_no_page_date_excludes_candidate_without_guessing(self):
        url = "https://example.com/no-date"
        row = candidate(primary_url=url)
        verified, report = source_freshness.verify_research_payload(
            research(row), fetcher=fetch_map({url: '<html><body>No machine readable date</body></html>'})
        )
        fixed = verified["candidates"][0]
        self.assertEqual(fixed["recommendation"], "exclude")
        self.assertEqual(fixed["verification_status"], "unconfirmed")
        self.assertEqual(report["excluded_unverified_freshness"], 1)

    def test_date_modified_does_not_make_old_article_fresh(self):
        url = "https://example.com/article"
        row = candidate(primary_url=url)
        html = '''<script type="application/ld+json">{
          "@type":"NewsArticle",
          "datePublished":"2026-07-31T06:11:53Z",
          "dateModified":"2026-08-16T18:00:00Z"
        }</script>'''
        verified, _report = source_freshness.verify_research_payload(
            research(row), fetcher=fetch_map({url: html})
        )
        self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
        self.assertEqual(verified["candidates"][0]["published_date"], "2026-07-31")

    def test_existing_excluded_candidate_is_not_fetched(self):
        url = "https://example.com/excluded"
        row = candidate(primary_url=url)
        row["recommendation"] = "exclude"
        called = []
        def fetch(_url: str):
            called.append(_url)
            raise AssertionError("fetch must not run")
        verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch)
        self.assertEqual(called, [])
        self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
        self.assertEqual(report["eligible_before"], 0)


if __name__ == "__main__":
    unittest.main()
