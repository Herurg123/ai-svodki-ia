from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
FIXTURE = ROOT / "automation" / "fixtures" / "recall" / "weak-source-signal-retention-2026-09-11.json"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


primary = load("p3b_primary_hardened", "primary_recall_search.py")
binder_v1 = load("p3b_binder_v1_baseline", "weak_source_exact_binding.py")
binder = load("p3b_binder_v2_hardened", "weak_source_exact_binding_v2.py")
coverage = load("p3b_coverage_hardened", "ensure_story_coverage.py")

WINDOW = {
    "start_at": "2026-09-09T00:00:00+00:00",
    "end_at": "2026-09-11T00:00:00+00:00",
}


class P3bExactAuthoritativeBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        rejection = fixture["positive_control"]["rejection"]
        cls.signal = primary.collect_unresolved_signals([
            {
                "direction_id": fixture["positive_control"]["direction_id"],
                "model_rejections": [rejection],
            }
        ])[0]

    def _candidate(
        self,
        *,
        title: str = "DeepSeek replaces V4 Pro with V4.1 Flash",
        organization: str = "DeepSeek",
        event_type: str = "release",
        source_url: str = "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
        source_type: str = "official",
        freshness: str = "new_event",
    ) -> dict:
        return {
            "title": title,
            "organization": organization,
            "published_date": "2026-09-10",
            "published_at": "2026-09-10T06:30:00+00:00",
            "time_precision": "datetime",
            "topic": "models",
            "event_type": event_type,
            "keywords": ["V4 Pro", "V4.1 Flash"],
            "geography": "world",
            "category": "models",
            "source_type": source_type,
            "primary_source": {
                "title": title,
                "publisher": "DeepSeek" if source_type == "official" else "Reuters",
                "url": source_url,
            },
            "supporting_sources": [],
            "event_summary": title,
            "verified_facts": ["Historical context is not binding evidence."],
            "significance": "Material model event",
            "significance_score": 4,
            "limitations": "",
            "archive_status": "none",
            "archive_reason": "",
            "recommendation": "include",
            "verification_status": "verified",
            "verification_notes": "Provider card; runtime must independently prove it.",
            "freshness_status": freshness,
            "freshness_reason": "Provider says fresh; runtime must independently prove it.",
            "legal_scale": "not_applicable",
            "legal_scale_reason": "",
            "curiosity_eligible": False,
            "curiosity_verification": "",
        }

    def _plan(self) -> dict:
        attempts = [
            {
                "direction_id": direction,
                "attempt": 1,
                "status": "checked_with_gaps",
                "api": {"status": "completed", "web_search_calls_completed": 1, "web_search_call_items_total": 1},
            }
            for direction in coverage._pre.AUDIT_DIRECTION_IDS
        ]
        return {
            "status": "ok",
            "publication_date": "2026-09-11",
            "audit_status": "complete_with_gaps",
            "audit_state": "completed_usable",
            "checked_directions": list(coverage._pre.AUDIT_DIRECTION_IDS),
            "attempts": attempts,
            "directions": copy.deepcopy(attempts),
            "candidates": [],
            "search_budget": {
                "maximum_calls": 7,
                "minimum_required_calls": 6,
                "completed_calls": 6,
                "remaining_calls": 1,
                "exhausted": False,
                "provider_overrun": False,
            },
            "retrieval_quality_contract_version": coverage._pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
            "retrieval_quality": {"version": coverage._pre.RETRIEVAL_QUALITY_CONTRACT_VERSION, "status": "complete"},
        }

    def _metadata(self, query: str) -> dict:
        return {
            "status": "completed",
            "web_search_calls_completed": 1,
            "web_search_call_items_total": 1,
            "actual_queries": [query],
            "consulted_sources": [],
        }

    @staticmethod
    def _html(title: str, published: str = "2026-09-10T06:30:00+00:00") -> str:
        return (
            "<html><head>"
            f"<title>{title}</title>"
            f"<meta property='og:title' content='{title}'>"
            f"<meta property='article:published_time' content='{published}'>"
            "</head><body>"
            f"<h1>{title}</h1><p>{title}</p>"
            "</body></html>"
        )

    def _process(self, candidates, *, html_by_url=None, archive=None, rejections=None):
        query = binder.build_query(self.signal)
        html_by_url = html_by_url or {}
        def fetcher(url: str):
            body = html_by_url.get(url, self._html("DeepSeek replaces V4 Pro with V4.1 Flash"))
            return body, url, 200
        return coverage._process_p3b_payload_v2(
            base_plan=self._plan(),
            signal=copy.deepcopy(self.signal),
            query=query,
            prompt="offline hardened P3b test",
            payload={"status": "complete", "candidates": copy.deepcopy(candidates), "rejections": copy.deepcopy(rejections or [])},
            metadata=self._metadata(query),
            slot_state="response_saved",
            search_window=copy.deepcopy(WINDOW),
            archive=copy.deepcopy(archive or {"items": []}),
            allow_page_fetch=True,
            page_fetcher=fetcher,
        )

    def test_p3a_signal_remains_evidence_only_but_is_qualified_for_p3b(self) -> None:
        report = {
            "retrieval_quality_contract_version": primary.RETRIEVAL_QUALITY_CONTRACT_VERSION,
            "unresolved_signals": [copy.deepcopy(self.signal)],
        }
        signals = binder.qualifying_signals(report, contract_version=primary.RETRIEVAL_QUALITY_CONTRACT_VERSION)
        self.assertEqual(len(signals), 1)
        self.assertFalse(signals[0]["resolution_required"])
        self.assertFalse(signals[0]["candidate_eligible"])

    def test_query_stays_one_date_free_source_neutral_identity_hint(self) -> None:
        query = binder.build_query(self.signal)
        self.assertEqual(query, "DeepSeek V4 Pro V4.1 Flash replace latest")
        for forbidden in ("site:", "reuters", "bloomberg", "2026-"):
            self.assertNotIn(forbidden, query.casefold())

    def test_old_fuzzy_match_can_accept_wrong_event_but_v2_rejects(self) -> None:
        wrong = self._candidate(title="DeepSeek launches R2 model", event_type="launch")
        legacy_signal = copy.deepcopy(self.signal)
        legacy_signal["entities"] = ["DeepSeek"]
        self.assertTrue(coverage._pre._candidate_matches_cluster(wrong, [legacy_signal]))
        ok, reason = binder.candidate_exact_binding(
            wrong,
            self.signal,
            authoritative_domains=tuple(coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS),
            authoritative_page_surface="DeepSeek launches R2 model",
            authoritative_final_url=wrong["primary_source"]["url"],
        )
        self.assertFalse(ok)
        self.assertIn(reason, {"version_identity_mismatch", "replacement_direction_mismatch"})

    def test_reverse_replacement_is_not_same_event(self) -> None:
        reverse = self._candidate(title="DeepSeek replaces V4.1 Flash with V4 Pro")
        ok, reason = binder.candidate_exact_binding(
            reverse, self.signal,
            authoritative_domains=tuple(coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS),
            authoritative_page_surface="DeepSeek replaces V4.1 Flash with V4 Pro",
            authoritative_final_url=reverse["primary_source"]["url"],
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "replacement_direction_mismatch")

    def test_similar_version_is_not_exact_version(self) -> None:
        signal = copy.deepcopy(self.signal)
        signal["product_version_anchors"] = ["V4"]
        signal["lifecycle_action_anchors"] = ["launch"]
        candidate = self._candidate(title="DeepSeek launches V4.1 Flash", event_type="launch")
        ok, reason = binder.candidate_exact_binding(
            candidate, signal,
            authoritative_domains=tuple(coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS),
            authoritative_page_surface="DeepSeek launches V4.1 Flash",
            authoritative_final_url=candidate["primary_source"]["url"],
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "version_identity_mismatch")

    def test_preview_signal_rejects_ga_with_historical_preview_mention(self) -> None:
        signal = copy.deepcopy(self.signal)
        signal["product_version_anchors"] = ["V4.1 Flash"]
        signal["lifecycle_action_anchors"] = ["preview"]
        candidate = self._candidate(
            title="DeepSeek V4.1 Flash is generally available after preview",
            event_type="general availability",
        )
        ok, reason = binder.candidate_exact_binding(
            candidate, signal,
            authoritative_domains=tuple(coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS),
            authoritative_page_surface="DeepSeek V4.1 Flash is generally available after preview",
            authoritative_final_url=candidate["primary_source"]["url"],
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "preview_ga_mismatch")

    def test_replacement_signal_rejects_benchmark_with_historical_replacement(self) -> None:
        benchmark = self._candidate(
            title="DeepSeek benchmarks V4.1 Flash after it replaced V4 Pro",
            event_type="benchmark",
        )
        ok, reason = binder.candidate_exact_binding(
            benchmark, self.signal,
            authoritative_domains=tuple(coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS),
            authoritative_page_surface="DeepSeek benchmarks V4.1 Flash after it replaced V4 Pro",
            authoritative_final_url=benchmark["primary_source"]["url"],
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "benchmark_lifecycle_mismatch")

    def test_positive_binding_requires_real_matching_page_and_freshness(self) -> None:
        candidate = self._candidate()
        result = self._process([candidate])
        self.assertEqual(result["weak_source_exact_binding"]["status"], "bound_candidate")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["p3b_exact_binding_version"], 2)
        self.assertEqual(result["candidates"][0]["audit_direction"], "weak_source_exact_binding")
        self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_fresh_wrong_official_page_does_not_bind(self) -> None:
        candidate = self._candidate()
        url = candidate["primary_source"]["url"]
        result = self._process([candidate], html_by_url={url: self._html("DeepSeek launches R2 model")})
        self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
        self.assertEqual(result["candidates"], [])
        attempt = result["attempts"][-1]
        self.assertTrue(any("authoritative_page_" in row["reason"] for row in attempt["binding_rejections"]))

    def test_model_new_event_cannot_override_old_real_page_date(self) -> None:
        candidate = self._candidate(freshness="new_event")
        url = candidate["primary_source"]["url"]
        old_page = self._html("DeepSeek replaces V4 Pro with V4.1 Flash", "2026-08-20T06:30:00+00:00")
        result = self._process([candidate], html_by_url={url: old_page})
        self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any("deterministic_freshness_rejected" in row["reason"] for row in result["attempts"][-1]["binding_rejections"]))

    def test_archive_exact_source_url_blocks_positive_admission(self) -> None:
        candidate = self._candidate()
        archive = {"items": [{"date": "2026-09-10", "source_urls": [candidate["primary_source"]["url"]], "stories": []}]}
        result = self._process([candidate], archive=archive)
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any(row["reason"] == "archive_exact_event_duplicate" for row in result["attempts"][-1]["binding_rejections"]))

    def test_model_duplicate_rejection_is_not_terminal_proof(self) -> None:
        rejection = {
            "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
            "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
            "reason_code": "duplicate",
            "reason": "Provider says duplicate",
        }
        result = self._process([], rejections=[rejection])
        self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
        self.assertTrue(any(row["reason"] == "terminal_negative_requires_independent_proof" for row in result["attempts"][-1]["binding_rejections"]))

    def test_result_order_is_deterministic_after_page_and_freshness_gates(self) -> None:
        official = self._candidate()
        agency = self._candidate(
            source_url="https://www.reuters.com/world/asia-pacific/deepseek-v41/",
            source_type="news_agency",
        )
        selected = []
        for rows in ([agency, official], [official, agency]):
            result = self._process(rows)
            selected.append(result["candidates"][0]["primary_source"]["url"])
        self.assertEqual(selected[0], selected[1])
        self.assertIn("deepseek.com", selected[0])

    def test_offline_replay_without_saved_page_proof_fails_closed(self) -> None:
        query = binder.build_query(self.signal)
        result = coverage._process_p3b_payload_v2(
            base_plan=self._plan(),
            signal=copy.deepcopy(self.signal),
            query=query,
            prompt="offline replay",
            payload={"status": "complete", "candidates": [self._candidate()], "rejections": []},
            metadata=self._metadata(query),
            slot_state="response_saved",
            search_window=copy.deepcopy(WINDOW),
            archive={"items": []},
            allow_page_fetch=False,
            page_fetcher=lambda _url: self.fail("offline replay must not fetch a mutable page"),
        )
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")


if __name__ == "__main__":
    unittest.main()
