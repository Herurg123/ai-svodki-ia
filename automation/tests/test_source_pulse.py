from __future__ import annotations

import importlib.util
import unittest
import sys
from datetime import datetime
from pathlib import Path

AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = AUTOMATION_ROOT / "scripts" / "source_pulse.py"
spec = importlib.util.spec_from_file_location("source_pulse", MODULE_PATH)
sp = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = sp
spec.loader.exec_module(sp)


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SourcePulseParserTests(unittest.TestCase):
    def test_rss_atom_parses_datetime(self):
        items = sp.parse_rss_atom(
            "<?xml version='1.0'?><rss><channel><item><title>Alibaba launches Wan3.0 AI video model</title><link>https://x.example/news/1</link><pubDate>Mon, 24 Aug 2026 08:15:19 GMT</pubDate></item></channel></rss>",
            "https://x.example/feed.xml",
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].time_precision, "datetime")
        self.assertEqual(items[0].published_at.isoformat(), "2026-08-24T08:15:19+00:00")

    def test_malformed_rss_is_parse_error_not_html_noise(self):
        source = sp.SourceDefinition("x", "A", "global", "official", "rss_atom", "https://x.example/feed.xml", ("x.example",))
        with self.assertRaises(sp.SourcePulseError):
            sp._parse_body(source, "<rss><broken>", source.url)

    def test_html_jsonld_parses_article(self):
        items = sp.parse_html_index(
            '<html><head><script type="application/ld+json">{"@type":"NewsArticle","headline":"NVIDIA Groq 3 LPX full production","url":"/news/groq","datePublished":"2026-08-24T08:00:00-07:00"}</script></head></html>',
            "https://nvidia.example.com/news",
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://nvidia.example.com/news/groq")

    def test_rss_config_can_use_html_fallback_payload(self):
        source = sp.SourceDefinition("xpeng", "A", "china_asia", "official", "rss_atom", "https://xpeng.example/rss.xml", ("xpeng.example",), ("https://xpeng.example/news",))
        items = sp._parse_body(source, '<html><head><script type="application/ld+json">{"@type":"NewsArticle","headline":"XPENG robotics raises US$900 million","url":"https://xpeng.example/news/robotics","datePublished":"2026-08-24"}</script></head></html>', "https://xpeng.example/news")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "XPENG robotics raises US$900 million")


class SourcePulseWindowAndSafetyTests(unittest.TestCase):
    def test_cutoff_day_date_only_is_retained_but_ambiguous(self):
        item = sp.ParsedItem("Example material event", "https://x.example/1", datetime(2026, 8, 25).date(), None, "date", "1")
        allowed, ambiguous = sp._within_window(item, dt("2026-08-24T00:00:00+03:00"), dt("2026-08-25T04:00:00+03:00"))
        self.assertTrue(allowed)
        self.assertTrue(ambiguous)

    def test_after_cutoff_datetime_is_rejected(self):
        item = sp.ParsedItem("Example material event", "https://x.example/1", datetime(2026, 8, 25).date(), dt("2026-08-25T05:00:00+03:00"), "datetime", "1")
        allowed, ambiguous = sp._within_window(item, dt("2026-08-24T00:00:00+03:00"), dt("2026-08-25T04:00:00+03:00"))
        self.assertFalse(allowed)
        self.assertFalse(ambiguous)

    def test_private_or_wrong_host_is_rejected(self):
        with self.assertRaises(sp.SourcePulseError):
            sp._safe_public_url("https://127.0.0.1/a", ("127.0.0.1",))
        with self.assertRaises(sp.SourcePulseError):
            sp._safe_public_url("https://evil.example/a", ("good.example",))

    def test_tracking_query_does_not_change_normalized_url(self):
        a = sp._normalized_url("https://x.example/a?utm_source=z&k=1")
        b = sp._normalized_url("https://x.example/a?k=1")
        self.assertEqual(a, b)

    def test_signed_credentials_are_stripped_from_persisted_url_identity(self):
        value = sp._normalized_url(
            "https://x.example/a?keep=1&token=secret&X-Amz-Signature=abc&credential=xyz"
        )
        self.assertEqual(value, "https://x.example/a?keep=1")
        opaque = sp._safe_source_item_id("opaque-secret-provider-guid")
        self.assertTrue(opaque.startswith("opaque-sha256:"))
        self.assertNotIn("secret", opaque)

    def test_mutable_url_does_not_force_same_event_fingerprint(self):
        a = sp.event_fingerprint("Qwen Cloud releases model Alpha", datetime(2026, 8, 24).date())
        b = sp.event_fingerprint("Qwen Cloud releases model Beta", datetime(2026, 8, 25).date())
        self.assertNotEqual(a, b)


class SourcePulseRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.source = sp.SourceDefinition("x", "A", "global", "official", "rss_atom", "https://x.example/feed.xml", ("x.example",), ("https://x.example/fallback",), 10)

    def test_source_failure_is_fail_open(self):
        def fetch(url, hosts):
            return sp.FetchOutcome(url, None, "error", 500, None, "boom", 1)
        result = sp.run_source_pulse(registry=[self.source], start_at=dt("2026-08-24T00:00:00+00:00"), end_at=dt("2026-08-25T00:00:00+00:00"), fetcher=fetch, fetched_at=dt("2026-08-25T00:00:00+00:00"))
        self.assertEqual(result["summary"]["lead_count"], 0)
        self.assertEqual(result["summary"]["sources_unavailable"], 1)
        self.assertEqual(result["paid_api_calls"], 0)
        self.assertEqual(result["web_search_operations"], 0)

    def test_403_primary_uses_fallback(self):
        xml = "<?xml version='1.0'?><rss><channel><item><title>XPENG robotics raises 900 million for Physical AI</title><link>https://x.example/news/robotics</link><pubDate>Mon, 24 Aug 2026 09:40:44 GMT</pubDate></item></channel></rss>"
        def fetch(url, hosts):
            if url.endswith("feed.xml"):
                return sp.FetchOutcome(url, None, "error", 403, None, "forbidden", 1)
            return sp.FetchOutcome(url, url, "ok", 200, xml, None, 1)
        result = sp.run_source_pulse(registry=[self.source], start_at=dt("2026-08-24T00:00:00+00:00"), end_at=dt("2026-08-25T00:00:00+00:00"), fetcher=fetch, fetched_at=dt("2026-08-25T00:00:00+00:00"))
        self.assertEqual(result["summary"]["lead_count"], 1)
        self.assertEqual(result["sources"][0]["attempts"][0]["http_status"], 403)
        self.assertEqual(result["sources"][0]["attempts"][1]["status"], "ok")

    def test_malformed_source_is_fail_open_parse_error(self):
        def fetch(url, hosts):
            return sp.FetchOutcome(url, url, "ok", 200, "<rss><broken>", None, 1)
        result = sp.run_source_pulse(registry=[self.source], start_at=dt("2026-08-24T00:00:00+00:00"), end_at=dt("2026-08-25T00:00:00+00:00"), fetcher=fetch, fetched_at=dt("2026-08-25T00:00:00+00:00"))
        self.assertEqual(result["summary"]["lead_count"], 0)
        self.assertEqual(result["summary"]["sources_parse_error"], 1)
        self.assertEqual(result["sources"][0]["status"], "parse_error")

    def test_archive_url_duplicate_is_marked_not_deleted(self):
        xml = "<?xml version='1.0'?><rss><channel><item><title>Known important event</title><link>https://x.example/news/known?utm_source=rss</link><pubDate>Mon, 24 Aug 2026 09:40:44 GMT</pubDate></item></channel></rss>"
        def fetch(url, hosts):
            return sp.FetchOutcome(url, url, "ok", 200, xml, None, 1)
        archive = {"items": [{"source_urls": ["https://x.example/news/known"]}]}
        result = sp.run_source_pulse(registry=[self.source], start_at=dt("2026-08-24T00:00:00+00:00"), end_at=dt("2026-08-25T00:00:00+00:00"), archive=archive, fetcher=fetch, fetched_at=dt("2026-08-25T00:00:00+00:00"))
        self.assertTrue(result["leads"][0]["archive_url_duplicate"])
        self.assertEqual(result["summary"]["archive_url_duplicates"], 1)

    def test_quiet_window_stays_zero(self):
        xml = "<?xml version='1.0'?><rss><channel><item><title>Old important event</title><link>https://x.example/news/old</link><pubDate>Wed, 01 Jul 2026 00:00:00 GMT</pubDate></item></channel></rss>"
        def fetch(url, hosts):
            return sp.FetchOutcome(url, url, "ok", 200, xml, None, 1)
        result = sp.run_source_pulse(registry=[self.source], start_at=dt("2026-08-24T00:00:00+00:00"), end_at=dt("2026-08-25T00:00:00+00:00"), fetcher=fetch, fetched_at=dt("2026-08-25T00:00:00+00:00"))
        self.assertEqual(result["summary"]["lead_count"], 0)

    def test_snapshot_hash_is_deterministic_across_fetch_times(self):
        xml = "<?xml version='1.0'?><rss><channel><item><title>Current important event</title><link>https://x.example/news/current</link><pubDate>Mon, 24 Aug 2026 09:40:44 GMT</pubDate></item></channel></rss>"
        def fetch(url, hosts):
            return sp.FetchOutcome(url, url, "ok", 200, xml, None, 1)
        kwargs = dict(registry=[self.source], start_at=dt("2026-08-24T00:00:00+00:00"), end_at=dt("2026-08-25T00:00:00+00:00"), fetcher=fetch)
        a = sp.run_source_pulse(**kwargs, fetched_at=dt("2026-08-25T00:00:00+00:00"))
        b = sp.run_source_pulse(**kwargs, fetched_at=dt("2026-08-25T01:00:00+00:00"))
        self.assertEqual(a["snapshot_hash"], b["snapshot_hash"])
        self.assertNotEqual(a["fetched_at"], b["fetched_at"])


class SourcePulseHistoricalReplayTests(unittest.TestCase):
    def test_weekly_replay_reproduces_bakeoff_9_of_13(self):
        fixture = AUTOMATION_ROOT / "fixtures" / "source-pulse" / "2026-08-19-to-25.json"
        result = sp.replay_fixture(fixture)
        self.assertEqual(result["strict_instances"], 13)
        self.assertEqual(result["strict_hits"], 9)
        self.assertAlmostEqual(result["recovery_rate"], 9 / 13)
        per_day = {row["date"]: row for row in result["days"]}
        self.assertTrue(all(c["hit"] for c in per_day["2026-08-25"]["controls"]))
        self.assertFalse(per_day["2026-08-22"]["controls"][0]["hit"])


if __name__ == "__main__":
    unittest.main()
