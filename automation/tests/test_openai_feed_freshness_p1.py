from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import source_freshness
import source_pulse as sp
import source_pulse_supplement_v14 as v14
import trusted_feed_publication as trusted_feed

FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "openai-feed-freshness-2026-09-11.json"


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def registry_contract() -> dict:
    return {
        "version": 1,
        "mode": "production_shadow",
        "production_integration": True,
        "candidate_influence": False,
        "supplemental_candidate_influence": True,
        "repoll_on_recovery": False,
        "sources": [{
            "id": "openai_news_rss",
            "tier": "A",
            "region": "global",
            "role": "official",
            "publisher": "OpenAI",
            "organization": "OpenAI",
            "adapter": "rss_atom",
            "url": "https://openai.com/news/rss.xml",
            "allowed_hosts": ["openai.com"],
            "include_url_regex": "openai\\.com/(index|research|news)",
            "max_items": 16,
        }],
    }


def openai_lead(**changes) -> dict:
    source = fixture()["trusted_source"]
    day = date.fromisoformat(source["published_date"])
    row = {
        "source_id": source["source_id"],
        "tier": "A",
        "region": "global",
        "role": "official",
        "title": source["title"],
        "url": source["item_url"],
        "published_date": source["published_date"],
        "published_at": source["published_at"],
        "time_precision": "datetime",
        "cutoff_ambiguous": False,
        "source_item_id": source["item_url"],
        "event_fingerprint": sp.event_fingerprint(source["title"], day),
        "exact_fingerprint": sp.exact_fp(source["title"], source["item_url"], day),
        "archive_url_duplicate": False,
        "publication_evidence_kind": source["publication_evidence_kind"],
    }
    row.update(changes)
    return row


def snapshot(row: dict) -> dict:
    return {
        "version": 1,
        "mode": "production_shadow",
        "production_integration": True,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "window": fixture()["search_window"],
        "sources": [{
            "source_id": row["source_id"],
            "tier": row["tier"],
            "region": row["region"],
            "status": "ok",
            "selected_url": "https://openai.com/news/rss.xml",
            "attempts": [{
                "url": "https://openai.com/news/rss.xml",
                "status": "ok",
                "http_status": 200,
                "elapsed_ms": 1,
            }],
            "parsed_items": 1,
            "window_items": 1,
            "accepted_leads": 1,
            "cutoff_ambiguous_leads": 0,
            "archive_url_duplicates": 0,
        }],
        "leads": [row],
        "summary": {
            "configured_sources": 1,
            "sources_ok": 1,
            "sources_unavailable": 0,
            "sources_parse_error": 0,
            "lead_count": 1,
            "eligible_new_lead_count": 1,
            "tier_a_leads": 1,
            "tier_b_leads": 0,
            "cutoff_ambiguous_leads": 0,
            "archive_url_duplicates": 0,
            "source_health_status": "complete",
            "degraded_source_ids": [],
        },
        "snapshot_hash": "openai-feed-p1-fixture",
    }


class TrustedFeedContractTests(unittest.TestCase):
    def test_pubdate_is_trusted_but_atom_updated_is_not(self):
        rss = """<rss><channel><item><title>OpenAI for Financial Services</title>
        <link>https://openai.com/index/openai-for-financial-services</link>
        <pubDate>Thu, 10 Sep 2026 20:00:00 GMT</pubDate></item></channel></rss>"""
        atom = """<feed><entry><title>OpenAI update</title>
        <link href="https://openai.com/index/openai-update"/>
        <updated>2026-09-10T20:00:00Z</updated></entry></feed>"""
        self.assertEqual(
            trusted_feed.feed_publication_fields(rss, "https://openai.com/news/rss.xml")[
                "https://openai.com/index/openai-for-financial-services"
            ],
            "rss_pubdate",
        )
        self.assertEqual(
            trusted_feed.feed_publication_fields(atom, "https://openai.com/news/rss.xml")[
                "https://openai.com/index/openai-update"
            ],
            "atom_updated",
        )

    def test_updated_cross_host_and_item_identity_mismatch_are_rejected(self):
        registry = registry_contract()
        self.assertIsNone(trusted_feed.build_evidence(
            openai_lead(publication_evidence_kind="atom_updated"), registry
        ))
        self.assertIsNone(trusted_feed.build_evidence(
            openai_lead(
                url="https://cdn.openai.com/index/openai-for-financial-services",
                source_item_id="https://cdn.openai.com/index/openai-for-financial-services",
            ),
            registry,
        ))
        self.assertIsNone(trusted_feed.build_evidence(
            openai_lead(source_item_id="opaque-sha256:not-an-exact-item-url"),
            registry,
        ))
        evidence = trusted_feed.build_evidence(openai_lead(), registry)
        self.assertIsNotNone(evidence)
        candidate = {
            "primary_source": {"url": "https://openai.com/index/different-item"},
            "trusted_feed_publication_evidence": evidence,
        }
        self.assertIsNone(trusted_feed.validate_evidence(candidate, registry))


class OpenAIFeedPromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.research = root / "research.json"
        self.archive = root / "archive.json"
        self.registry = root / "registry.json"
        self.output = root / "diag"
        self._reset_research()
        self.archive.write_text('{"items": []}\n', encoding="utf-8")
        self.registry.write_text(
            json.dumps(registry_contract(), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _reset_research(self) -> None:
        self.research.write_text(json.dumps({
            "status": "ok",
            "publication_date": "2026-09-11",
            "search_window": fixture()["search_window"],
            "coverage": [],
            "candidates": [],
            "regional_health": {},
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        if self.output.exists():
            for path in self.output.glob("*"):
                if path.is_file():
                    path.unlink()

    def _run_pulse(self, row: dict, page_fetcher):
        return v14.run_source_pulse_supplement(
            research_path=self.research,
            archive_path=self.archive,
            publication_date="2026-09-11",
            output_root=self.output,
            registry_path=self.registry,
            collector_fn=lambda **kwargs: snapshot(row),
            page_fetcher=page_fetcher,
        )

    def test_403_and_undated_page_use_saved_pubdate_without_repoll(self):
        row = openai_lead()
        calls = []

        def blocked(url: str):
            calls.append(url)
            raise RuntimeError("HTTP Error 403: Forbidden")

        report = self._run_pulse(row, blocked)
        payload = json.loads(self.research.read_text(encoding="utf-8"))
        self.assertEqual(calls, [row["url"]])
        self.assertEqual(report["promotion"]["promoted_count"], 1)
        self.assertFalse(report["trusted_feed_publication_evidence"]["feed_repolled_for_fallback"])
        self.assertEqual(report["paid_api_calls"], 0)
        self.assertEqual(report["web_search_operations"], 0)
        self.assertEqual(
            payload["candidates"][0]["trusted_feed_publication_evidence"]["feed_date_field"],
            "rss_pubdate",
        )

        self._reset_research()
        body = "<html><body><h1>OpenAI for Financial Services</h1></body></html>"
        report = self._run_pulse(openai_lead(), lambda url: (body, url, 200))
        self.assertEqual(report["promotion"]["promoted_count"], 1)
        self.assertEqual(report["trusted_feed_publication_evidence"]["undated_page_fallback_count"], 1)

    def test_updated_conflict_and_redirect_drift_stay_fail_closed(self):
        report = self._run_pulse(
            openai_lead(publication_evidence_kind="atom_updated"),
            lambda url: (_ for _ in ()).throw(RuntimeError("403")),
        )
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        self.assertEqual(report["trusted_feed_publication_evidence"]["saved_proof_count"], 0)

        self._reset_research()
        conflict_html = '<meta property="article:published_time" content="2026-09-09T20:00:00Z">'
        report = self._run_pulse(openai_lead(), lambda url: (conflict_html, url, 200))
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        self.assertEqual(
            report["promotion"]["lead_dispositions"][0]["reason"],
            "trusted_feed_direct_publication_date_conflict",
        )

        self._reset_research()
        report = self._run_pulse(
            openai_lead(),
            lambda url: ("<html>No date</html>", "https://openai.com/index/different", 200),
        )
        self.assertEqual(report["promotion"]["promoted_count"], 0)
        self.assertEqual(
            report["promotion"]["lead_dispositions"][0]["reason"],
            "trusted_feed_redirect_or_canonical_mismatch",
        )


class OpenAIFeedSourceFreshnessTests(unittest.TestCase):
    def _candidate(self, *, published_at: str | None = None) -> dict:
        row = openai_lead()
        if published_at is not None:
            row["published_at"] = published_at
            row["published_date"] = published_at[:10]
        evidence = trusted_feed.build_evidence(row, registry_contract())
        self.assertIsNotNone(evidence)
        return {
            "id": "openai-feed-p1",
            "title": row["title"],
            "organization": "OpenAI",
            "published_date": row["published_date"],
            "published_at": row["published_at"],
            "time_precision": "datetime",
            "topic": row["title"],
            "event_type": "source_pulse_official_update",
            "keywords": ["OpenAI", "AI"],
            "geography": "world",
            "category": "other",
            "source_type": "official",
            "primary_source": {"title": row["title"], "publisher": "OpenAI", "url": row["url"]},
            "supporting_sources": [],
            "event_summary": row["title"],
            "verified_facts": [row["title"], "OpenAI official publication"],
            "significance": "fixture",
            "significance_score": 3,
            "limitations": "",
            "archive_status": "none",
            "archive_reason": "",
            "recommendation": "consider",
            "verification_status": "verified",
            "verification_notes": "fixture",
            "freshness_status": "new_event",
            "freshness_reason": "fixture",
            "legal_scale": "not_applicable",
            "legal_scale_reason": "",
            "curiosity_eligible": False,
            "curiosity_verification": "",
            "audit_direction": "source_pulse_v14",
            "trusted_feed_publication_evidence": evidence,
        }

    def _research(self, candidate: dict) -> dict:
        return {
            "status": "ok",
            "publication_date": "2026-09-11",
            "search_window": fixture()["search_window"],
            "coverage": [],
            "candidates": [candidate],
        }

    def test_second_403_reuses_saved_proof_and_old_timestamp_stays_stale(self):
        verified, report = source_freshness.verify_research_payload(
            self._research(self._candidate()),
            fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("403")),
        )
        fixed = verified["candidates"][0]
        self.assertEqual(fixed["recommendation"], "consider")
        self.assertEqual(fixed["source_freshness_status"], "fresh")
        self.assertEqual(fixed["source_freshness_evidence_kind"], "trusted_first_party_feed")
        self.assertIn("trusted_feed:openai_news_rss:rss_pubdate", fixed["source_publication_evidence"])
        self.assertEqual(report["trusted_feed_evidence_used"], 1)
        self.assertEqual(report["paid_api_calls"], 0)
        self.assertEqual(report["web_search_operations"], 0)

        verified, report = source_freshness.verify_research_payload(
            self._research(self._candidate(published_at="2026-09-01T20:00:00+00:00")),
            fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("403")),
        )
        self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
        self.assertEqual(verified["candidates"][0]["freshness_status"], "old_reprint")
        self.assertEqual(report["excluded_outside_window"], 1)

    def test_direct_conflict_and_redirect_drift_are_fail_closed(self):
        conflict_html = '<meta property="article:published_time" content="2026-09-09T20:00:00Z">'
        verified, report = source_freshness.verify_research_payload(
            self._research(self._candidate()),
            fetcher=lambda url: (conflict_html, url, 200),
        )
        self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
        self.assertEqual(report["trusted_feed_conflicts"], 1)

        verified, report = source_freshness.verify_research_payload(
            self._research(self._candidate()),
            fetcher=lambda url: ("<html>No date</html>", "https://openai.com/index/different", 200),
        )
        self.assertEqual(verified["candidates"][0]["recommendation"], "exclude")
        self.assertEqual(report["trusted_feed_conflicts"], 1)


if __name__ == "__main__":
    unittest.main()
