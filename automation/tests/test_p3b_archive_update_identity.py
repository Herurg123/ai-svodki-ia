from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ensure_story_coverage as coverage
import primary_recall_search as primary

WINDOW = {
    "start_at": "2026-09-09T00:00:00+00:00",
    "end_at": "2026-09-11T00:00:00+00:00",
    "start_date": "2026-09-09",
    "end_date": "2026-09-11",
}


class P3bArchiveUpdateIdentityTests(unittest.TestCase):
    @staticmethod
    def signal(title: str) -> dict:
        rows = primary.collect_unresolved_signals([
            {
                "direction_id": "independent_missing_events",
                "model_rejections": [{
                    "title": title,
                    "url": "https://weak.example/deepseek-update",
                    "reason_code": "weak_source",
                    "reason": "Weak-source product update awaiting authoritative exact binding.",
                }],
            }
        ])
        if len(rows) != 1:
            raise AssertionError(f"expected one weak-source signal, got {rows!r}")
        return rows[0]

    @staticmethod
    def candidate() -> dict:
        title = "DeepSeek updates V4.1 Flash with one million token context window"
        return {
            "title": title,
            "organization": "DeepSeek",
            "published_date": "2026-09-10",
            "published_at": "2026-09-10T06:30:00+00:00",
            "time_precision": "datetime",
            "topic": "models",
            "event_type": "update",
            "keywords": ["V4.1 Flash", "context window"],
            "geography": "world",
            "category": "models",
            "source_type": "official",
            "primary_source": {
                "title": title,
                "publisher": "DeepSeek",
                "url": "https://www.deepseek.com/en/news/v4-1-flash-context-window/",
            },
            "supporting_sources": [],
            "event_summary": title,
            "verified_facts": ["Runtime verifies the authoritative page independently."],
            "significance": "Material model update",
            "significance_score": 4,
            "limitations": "",
            "archive_status": "none",
            "archive_reason": "",
            "recommendation": "include",
            "verification_status": "verified",
            "verification_notes": "runtime must verify page",
            "freshness_status": "material_update",
            "freshness_reason": "runtime must verify date",
            "legal_scale": "not_applicable",
            "legal_scale_reason": "",
            "curiosity_eligible": False,
            "curiosity_verification": "",
        }

    @staticmethod
    def archive_story(headline: str, *, url: str = "https://example.org/archive-copy") -> dict:
        return {
            "items": [{
                "date": "2026-09-09",
                "source_urls": [url],
                "stories": [{
                    "headline": headline,
                    "organization": "DeepSeek",
                    "event_type": "update",
                    "event_summary": headline,
                    "sources": [{"url": url}],
                }],
            }]
        }

    def setUp(self) -> None:
        self.signal_update = self.signal(
            "DeepSeek updates V4.1 Flash with one million token context window"
        )
        self.assertEqual(self.signal_update["organization"], "DeepSeek")
        self.assertEqual(self.signal_update["product_version_anchors"], ["V4.1 Flash"])
        self.assertEqual(self.signal_update["lifecycle_action_anchors"], ["update"])

    def test_distinct_update_same_model_is_not_archive_duplicate(self) -> None:
        archive = self.archive_story(
            "DeepSeek updates V4.1 Flash with native tool calling and JSON mode"
        )
        candidate = self.candidate()
        surface = "DeepSeek updates V4.1 Flash with native tool calling and JSON mode DeepSeek update"
        matched, _ = coverage._exact_binding.exact_event_identity(surface, self.signal_update)
        self.assertTrue(matched, "old core identity must reproduce Astra's false duplicate precondition")
        self.assertFalse(
            coverage._archive_exact_event(archive, candidate, self.signal_update)
        )

    def test_high_overlap_but_distinct_update_is_not_archive_duplicate(self) -> None:
        candidate = self.candidate()
        candidate["title"] = "DeepSeek updates V4.1 Flash with video input support"
        candidate["event_summary"] = candidate["title"]
        candidate["primary_source"] = {
            "title": candidate["title"],
            "publisher": "DeepSeek",
            "url": "https://www.deepseek.com/en/news/v4-1-flash-video-input/",
        }
        archive = self.archive_story(
            "DeepSeek updates V4.1 Flash with video output support"
        )
        self.assertFalse(
            coverage._archive_exact_event(archive, candidate, self.signal_update)
        )

    def test_same_mutable_update_different_url_keeps_semantic_duplicate_proof(self) -> None:
        archive = self.archive_story(
            "DeepSeek V4.1 Flash update expands the one million token context window"
        )
        self.assertTrue(
            coverage._archive_exact_event(archive, self.candidate(), self.signal_update)
        )

    def test_structured_archive_org_preserves_semantic_duplicate_without_headline_org(self) -> None:
        archive = self.archive_story(
            "V4.1 Flash update expands the one million token context window"
        )
        self.assertTrue(
            coverage._archive_exact_event(archive, self.candidate(), self.signal_update)
        )

    def test_conflicting_structured_archive_org_fails_closed(self) -> None:
        archive = self.archive_story(
            "V4.1 Flash update expands the one million token context window"
        )
        archive["items"][0]["stories"][0]["organization"] = "OpenAI"
        self.assertFalse(
            coverage._archive_exact_event(archive, self.candidate(), self.signal_update)
        )

    def test_structured_org_cannot_reassign_foreign_headline_actor(self) -> None:
        signal = copy.deepcopy(self.signal_update)
        signal["title"] = "DeepSeek launches V4.1 Flash"
        signal["lifecycle_action_anchors"] = ["launch"]
        archive = self.archive_story("OpenAI launches V4.1 Flash")
        archive["items"][0]["stories"][0]["event_type"] = "launch"
        self.assertFalse(
            coverage._archive_exact_event(archive, self.candidate(), signal)
        )

    def test_exact_source_url_remains_conclusive_duplicate_proof(self) -> None:
        candidate = self.candidate()
        archive = self.archive_story(
            "DeepSeek updates V4.1 Flash with native tool calling and JSON mode",
            url=candidate["primary_source"]["url"],
        )
        self.assertTrue(
            coverage._archive_exact_event(archive, candidate, self.signal_update)
        )

    def test_distinct_update_survives_full_p3b_archive_admission(self) -> None:
        candidate = self.candidate()
        query = coverage.build_p3b_query(self.signal_update)
        title = candidate["title"]
        html = (
            "<html><head>"
            f"<title>{title}</title>"
            f"<meta property='og:title' content='{title}'>"
            "<meta property='article:published_time' content='2026-09-10T06:30:00+00:00'>"
            "</head><body>"
            f"<h1>{title}</h1><p>{title}</p>"
            "</body></html>"
        )
        archive = self.archive_story(
            "DeepSeek updates V4.1 Flash with native tool calling and JSON mode"
        )
        result = coverage._process_p3b_payload_v2(
            base_plan={
                "publication_date": "2026-09-11",
                "audit_status": "complete_with_gaps",
                "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
                "attempts": [],
                "candidates": [],
                "search_budget": {
                    "maximum_calls": 7,
                    "completed_calls": 6,
                    "remaining_calls": 1,
                },
            },
            signal=copy.deepcopy(self.signal_update),
            query=query,
            prompt="distinct mutable update archive control",
            payload={"status": "complete", "candidates": [candidate], "rejections": []},
            metadata={
                "status": "completed",
                "actual_queries": [query],
                "web_search_calls_completed": 1,
                "web_search_call_items_total": 1,
            },
            slot_state="response_saved",
            search_window=copy.deepcopy(WINDOW),
            archive=archive,
            allow_page_fetch=True,
            page_fetcher=lambda url: (html, url, 200),
        )
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["title"], title)
        self.assertFalse(any(
            row.get("reason") == "archive_exact_event_duplicate"
            for row in result["attempts"][-1]["binding_rejections"]
        ))


if __name__ == "__main__":
    unittest.main()
