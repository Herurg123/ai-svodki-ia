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

WINDOW = {"start_at": "2026-08-27T04:43:51+03:00", "end_at": "2026-08-29T05:16:40+03:00"}


def candidate(*, primary_url="https://example.com/article", supporting=None, published_date="2026-08-28", published_at=None, precision=None):
    precision = precision or ("datetime" if published_at else "date")
    return {
        "id": "cand-001", "title": "Test candidate", "organization": "Example",
        "published_date": published_date, "published_at": published_at, "time_precision": precision,
        "topic": "test", "event_type": "test", "keywords": ["test"], "geography": "world",
        "category": "other", "source_type": "news_agency",
        "primary_source": {"title": "Primary", "publisher": "Primary Publisher", "url": primary_url},
        "supporting_sources": supporting or [], "event_summary": "test", "verified_facts": ["a", "b"],
        "significance": "test", "significance_score": 4, "limitations": "", "archive_status": "none",
        "archive_reason": "", "recommendation": "include", "verification_status": "verified",
        "verification_notes": "model verification", "freshness_status": "new_event",
        "freshness_reason": "model claimed fresh", "legal_scale": "not_applicable", "legal_scale_reason": "",
        "curiosity_eligible": False, "curiosity_verification": "",
    }


def research(row):
    return {"status": "ok", "publication_date": "2026-08-29", "search_window": dict(WINDOW), "coverage": [], "candidates": [row]}


def fetch_map(mapping):
    def fetch(url):
        value = mapping[url]
        if isinstance(value, Exception):
            raise value
        return value, url, 200
    return fetch


class PublicationMetadataTests(unittest.TestCase):
    def test_extracts_article_published_time(self):
        proof = source_freshness.extract_publication_evidence('<meta property="article:published_time" content="2026-08-28T13:57:00-07:00">')
        self.assertEqual(proof.time_precision, "datetime")
        self.assertEqual(proof.published_at.isoformat(), "2026-08-28T13:57:00-07:00")

    def test_date_modified_does_not_override_date_published(self):
        html = '<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-08-28T06:11:53Z","dateModified":"2026-08-29T00:00:00Z"}</script>'
        proof = source_freshness.extract_publication_evidence(html)
        self.assertEqual(proof.published_at.isoformat(), "2026-08-28T06:11:53+00:00")

    def test_source_start_boundary_date_only_fails_closed(self):
        proof = source_freshness.extract_publication_evidence('<meta itemprop="datePublished" content="2026-08-27">')
        self.assertFalse(source_freshness.evidence_in_window(
            proof,
            start_at=source_freshness._parse_aware(WINDOW["start_at"], "s"),
            end_at=source_freshness._parse_aware(WINDOW["end_at"], "e"),
        ))

    def test_source_end_boundary_date_only_fails_closed(self):
        proof = source_freshness.extract_publication_evidence('<meta itemprop="datePublished" content="2026-08-29">')
        self.assertFalse(source_freshness.evidence_in_window(
            proof,
            start_at=source_freshness._parse_aware(WINDOW["start_at"], "s"),
            end_at=source_freshness._parse_aware(WINDOW["end_at"], "e"),
        ))


class EventFreshnessTests(unittest.TestCase):
    def _status(self, row):
        ev = source_freshness.extract_event_freshness_evidence(row)
        self.assertIsNotNone(ev)
        return source_freshness.event_evidence_status(
            ev,
            start_at=source_freshness._parse_aware(WINDOW["start_at"], "s"),
            end_at=source_freshness._parse_aware(WINDOW["end_at"], "e"),
        )

    def test_exact_start_is_fresh(self):
        self.assertEqual(self._status(candidate(published_date="2026-08-27", published_at="2026-08-27T04:43:51+03:00")), "fresh")

    def test_one_second_before_start_is_stale(self):
        self.assertEqual(self._status(candidate(published_date="2026-08-27", published_at="2026-08-27T04:43:50+03:00")), "stale")

    def test_exact_end_is_fresh(self):
        self.assertEqual(self._status(candidate(published_date="2026-08-29", published_at="2026-08-29T05:16:40+03:00")), "fresh")

    def test_one_second_after_end_is_stale(self):
        self.assertEqual(self._status(candidate(published_date="2026-08-29", published_at="2026-08-29T05:16:41+03:00")), "stale")

    def test_start_boundary_date_only_is_unknown(self):
        self.assertEqual(self._status(candidate(published_date="2026-08-27")), "unknown")

    def test_end_boundary_date_only_is_unknown(self):
        self.assertEqual(self._status(candidate(published_date="2026-08-29")), "unknown")

    def test_interior_date_only_is_fresh(self):
        self.assertEqual(self._status(candidate(published_date="2026-08-28")), "fresh")


class CombinedFreshnessTests(unittest.TestCase):
    def test_source_page_timestamp_never_overwrites_event_timestamp(self):
        url = "https://example.com/article"
        row = candidate(primary_url=url, published_date="2026-08-28", published_at="2026-08-28T10:00:00+03:00")
        html = '<meta property="article:published_time" content="2026-08-28T20:00:00+03:00">'
        verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch_map({url: html}))
        fixed = verified["candidates"][0]
        self.assertEqual(fixed["published_at"], "2026-08-28T10:00:00+03:00")
        self.assertEqual(report["candidates"][0]["source_published_at"], "2026-08-28T20:00:00+03:00")
        self.assertEqual(report["verified_fresh"], 1)

    def test_fresh_supporting_source_can_replace_unverifiable_primary_without_rewriting_event(self):
        primary = "https://www.bloomberg.com/example"
        support = "https://techcrunch.com/example"
        row = candidate(
            primary_url=primary,
            supporting=[{"title": "Support", "publisher": "TechCrunch", "url": support}],
            published_date="2026-08-28",
            published_at="2026-08-28T10:00:00+03:00",
        )
        mapping = {
            primary: '<html><head><title>No date</title></head></html>',
            support: '<meta property="article:published_time" content="2026-08-28T13:57:00-07:00">',
        }
        verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch_map(mapping))
        fixed = verified["candidates"][0]
        self.assertEqual(fixed["recommendation"], "include")
        self.assertEqual(fixed["primary_source"]["url"], support)
        self.assertEqual(fixed["published_at"], "2026-08-28T10:00:00+03:00")
        self.assertEqual(report["candidates"][0]["source_published_at"], "2026-08-28T13:57:00-07:00")

    def test_old_event_with_fresh_reprint_is_excluded_before_source_fetch(self):
        url = "https://example.com/fresh-reprint"
        row = candidate(primary_url=url, published_date="2026-08-26", published_at="2026-08-26T20:21:00+00:00")
        calls = []
        def fetch(_url):
            calls.append(_url)
            return '<meta property="article:published_time" content="2026-08-28T10:00:00Z">', _url, 200
        verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch)
        fixed = verified["candidates"][0]
        self.assertEqual(calls, [])
        self.assertEqual(fixed["recommendation"], "exclude")
        self.assertEqual(fixed["freshness_status"], "old_reprint")
        self.assertEqual(report["excluded_event_outside_window"], 1)

    def test_three_aug29_false_positive_shapes_fail_offline(self):
        for title in ("Claudeforce", "Gemini Enterprise Legal/Finance", "GLM-5.3-Flash"):
            with self.subTest(title=title):
                row = candidate(primary_url="https://example.com/" + title.replace(" ", "-"), published_date="2026-08-27")
                row["title"] = title
                calls = []
                def fetch(_url):
                    calls.append(_url)
                    return '<meta property="article:published_time" content="2026-08-28T10:00:00Z">', _url, 200
                verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch)
                self.assertEqual(calls, [])
                self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
                self.assertEqual(report["excluded_unverified_event_freshness"], 1)

    def test_fresh_event_and_fresh_secondary_source_pass(self):
        url = "https://www.reuters.com/example"
        row = candidate(primary_url=url, published_date="2026-08-28", published_at="2026-08-28T12:00:00Z")
        html = '<meta property="article:published_time" content="2026-08-28T12:51:14Z">'
        verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch_map({url: html}))
        self.assertEqual(verified["candidates"][0]["recommendation"], "include")
        self.assertEqual(report["verified_fresh"], 1)

    def test_fresh_event_but_old_source_still_fails_existing_source_gate(self):
        url = "https://example.com/old-source"
        row = candidate(primary_url=url, published_date="2026-08-28", published_at="2026-08-28T12:00:00Z")
        html = '<meta property="article:published_time" content="2026-08-20T12:00:00Z">'
        verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch_map({url: html}))
        self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
        self.assertEqual(report["excluded_outside_window"], 1)

    def test_no_source_page_date_still_fails_closed(self):
        url = "https://example.com/no-date"
        row = candidate(primary_url=url, published_date="2026-08-28", published_at="2026-08-28T12:00:00Z")
        verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch_map({url: '<html>No date</html>'}))
        self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
        self.assertEqual(report["excluded_unverified_freshness"], 1)

    def test_existing_excluded_candidate_is_not_fetched(self):
        url = "https://example.com/excluded"
        row = candidate(primary_url=url)
        row["recommendation"] = "exclude"
        calls = []
        def fetch(_url):
            calls.append(_url)
            raise AssertionError("fetch must not run")
        verified, report = source_freshness.verify_research_payload(research(row), fetcher=fetch)
        self.assertEqual(calls, [])
        self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
        self.assertEqual(report["eligible_before"], 0)


if __name__ == "__main__":
    unittest.main()
