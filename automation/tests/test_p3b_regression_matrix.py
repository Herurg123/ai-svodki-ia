from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ensure_story_coverage as coverage
import weak_source_exact_binding_v4 as binder


MATRIX = {
    1: "exact_positive",
    2: "same_company_different_product",
    3: "similar_version",
    4: "old_release",
    5: "preview_vs_ga",
    6: "benchmark_vs_release",
    7: "duplicate_reprint",
    8: "false_alias",
    9: "missing_authoritative_source",
    10: "wrong_event_date_official_page",
    11: "independently_valid_candidate_not_binding",
    12: "result_order_permutation",
    13: "occupied_seventh_slot",
    14: "spent_before_recovery",
    15: "interrupted_ambiguous_transport",
    16: "saved_completed_resolution_replay",
    17: "stale_authoritative_page",
    18: "archive_duplicate",
    19: "candidate_fails_freshness",
    20: "same_company_version_lifecycle_differs",
}

WINDOW = {
    "start_at": "2026-09-09T00:00:00+00:00",
    "end_at": "2026-09-11T00:00:00+00:00",
}


class P3bExactBindingMatrixTests(unittest.TestCase):
    @staticmethod
    def signal() -> dict:
        return {
            "signal_id": "weak-source-product-deepseek-v4-1-flash",
            "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
            "organization": "DeepSeek",
            "product_version_anchors": ["V4 Pro", "V4.1 Flash"],
            "lifecycle_action_anchors": ["replace"],
            "source_provenance": {
                "url": "https://huggingnews.com/ai/deepseek-v41-flash"
            },
        }

    @staticmethod
    def candidate(**overrides) -> dict:
        value = {
            "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
            "organization": "DeepSeek",
            "published_date": "2026-09-10",
            "published_at": "2026-09-10T06:30:00+00:00",
            "time_precision": "datetime",
            "topic": "models",
            "event_type": "release",
            "keywords": ["V4 Pro", "V4.1 Flash"],
            "geography": "world",
            "category": "models",
            "source_type": "official",
            "primary_source": {
                "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
                "publisher": "DeepSeek",
                "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
            },
            "supporting_sources": [],
            "event_summary": "DeepSeek replaces V4 Pro with V4.1 Flash",
            "verified_facts": ["Runtime independently verifies the exact authoritative page."],
            "significance": "Material model event",
            "significance_score": 4,
            "limitations": "",
            "archive_status": "none",
            "archive_reason": "",
            "recommendation": "include",
            "verification_status": "verified",
            "verification_notes": "runtime proof required",
            "freshness_status": "new_event",
            "freshness_reason": "runtime proof required",
            "legal_scale": "not_applicable",
            "legal_scale_reason": "",
            "curiosity_eligible": False,
            "curiosity_verification": "",
        }
        value.update(overrides)
        return value

    @property
    def domains(self) -> tuple[str, ...]:
        return tuple(coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS)

    @staticmethod
    def html(title: str, published: str = "2026-09-10T06:30:00+00:00") -> str:
        return (
            "<html><head>"
            f"<title>{title}</title>"
            f"<meta property='og:title' content='{title}'>"
            f"<meta property='article:published_time' content='{published}'>"
            "</head><body>"
            f"<h1>{title}</h1><p>{title}</p>"
            "</body></html>"
        )

    def plan(self) -> dict:
        attempts = [
            {
                "direction_id": direction,
                "attempt": 1,
                "status": "checked_with_gaps",
                "api": {
                    "status": "completed",
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                },
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
        }

    def binding(
        self,
        candidate: dict,
        signal: dict | None = None,
        *,
        page_surface: str | None = None,
    ):
        source = candidate.get("primary_source") or {}
        return binder.candidate_exact_binding(
            candidate,
            signal or self.signal(),
            authoritative_domains=self.domains,
            authoritative_page_surface=(
                candidate.get("title") if page_surface is None else page_surface
            ),
            authoritative_final_url=source.get("url"),
        )

    def process(self, candidates, *, archive=None, html_by_url=None, rejections=None):
        signal = self.signal()
        query = binder.build_query(signal)
        html_by_url = html_by_url or {}

        def fetcher(url: str):
            body = html_by_url.get(
                url,
                self.html("DeepSeek replaces V4 Pro with V4.1 Flash"),
            )
            return body, url, 200

        return coverage._process_p3b_payload_v2(
            base_plan=self.plan(),
            signal=copy.deepcopy(signal),
            query=query,
            prompt="active permanent matrix",
            payload={
                "status": "complete",
                "candidates": copy.deepcopy(candidates),
                "rejections": copy.deepcopy(rejections or []),
            },
            metadata={
                "status": "completed",
                "web_search_calls_completed": 1,
                "web_search_call_items_total": 1,
                "actual_queries": [query],
                "consulted_sources": [],
            },
            slot_state="response_saved",
            search_window=copy.deepcopy(WINDOW),
            archive=copy.deepcopy(archive or {"items": []}),
            allow_page_fetch=True,
            page_fetcher=fetcher,
        )

    def test_matrix_contract_has_exactly_twenty_named_cases_on_active_versions(self) -> None:
        self.assertEqual(list(MATRIX), list(range(1, 21)))
        self.assertEqual(len(set(MATRIX.values())), 20)
        self.assertEqual(binder.VERSION, 2)
        self.assertEqual(coverage.P3B_EXACT_BINDING_VERSION, 2)
        self.assertIs(coverage._exact_binding, binder)
        self.assertIs(coverage._impl._exact_binding, binder)
        self.assertEqual(
            coverage.P3B_BINDER_EVIDENCE_VERSION,
            binder.EVIDENCE_VERSION,
        )
        self.assertIs(
            coverage._impl._v2._run_p3b_binding_v2,
            coverage._impl._guarded_run_p3b_binding_v2,
        )

    def test_cases_01_to_04_exact_product_and_freshness_boundaries(self) -> None:
        self.assertEqual(
            self.binding(self.candidate()),
            (True, "exact_authoritative_page_binding"),
        )

        other = self.candidate(
            title="DeepSeek launches R2",
            event_type="launch",
            keywords=["R2"],
            event_summary="DeepSeek launched R2.",
        )
        self.assertEqual(self.binding(other), (False, "version_identity_mismatch"))

        similar = self.candidate(
            title="DeepSeek replaces V4 Pro with V4.2 Flash",
            keywords=["V4 Pro", "V4.2 Flash"],
            event_summary="DeepSeek replaced V4 Pro with V4.2 Flash.",
        )
        self.assertEqual(self.binding(similar), (False, "version_identity_mismatch"))

        old = self.candidate(freshness_status="old_reprint")
        self.assertEqual(self.binding(old), (False, "candidate_not_fresh_event"))

    def test_cases_05_06_and_20_lifecycle_identity_is_exact(self) -> None:
        preview_signal = self.signal()
        preview_signal["title"] = "DeepSeek previews V4.1 Flash"
        preview_signal["product_version_anchors"] = ["V4.1 Flash"]
        preview_signal["lifecycle_action_anchors"] = ["preview"]
        ga = self.candidate(
            title="DeepSeek announces general availability of V4.1 Flash",
            event_type="general availability",
            keywords=["V4.1 Flash", "general availability"],
        )
        self.assertEqual(
            self.binding(ga, preview_signal),
            (False, "lifecycle_identity_mismatch"),
        )

        benchmark = self.candidate(
            title="DeepSeek V4 Pro and V4.1 Flash benchmark results",
            event_type="benchmark",
        )
        self.assertEqual(
            self.binding(benchmark),
            (False, "benchmark_lifecycle_mismatch"),
        )

        updated = self.candidate(
            title="DeepSeek updates V4 Pro and V4.1 Flash",
            event_type="update",
        )
        self.assertEqual(
            self.binding(updated),
            (False, "replacement_direction_mismatch"),
        )

    def test_case_07_duplicate_reprint_requires_independent_archive_proof(self) -> None:
        rejection = {
            "title": "DeepSeek replaced V4 Pro with V4.1 Flash",
            "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
            "reason_code": "duplicate",
            "reason": "Provider says duplicate.",
        }
        self.assertEqual(
            binder.rejection_exact_terminal_binding(
                rejection,
                self.signal(),
                authoritative_domains=self.domains,
            ),
            (False, "terminal_negative_requires_independent_proof"),
        )
        candidate = self.candidate()
        archive = {
            "items": [{
                "date": "2026-09-10",
                "source_urls": [candidate["primary_source"]["url"]],
                "stories": [],
            }]
        }
        self.assertTrue(coverage._archive_exact_event(archive, candidate, self.signal()))

    def test_cases_08_09_false_alias_and_non_authoritative_source_fail_closed(self) -> None:
        alias = self.candidate(
            title="DeepSeek replaces V4 Pro with V4.1 Flashpoint",
            keywords=["V4 Pro", "V4.1 Flashpoint"],
        )
        self.assertEqual(self.binding(alias), (False, "version_identity_mismatch"))

        weak = self.candidate(
            source_type="technology_media",
            primary_source={
                "title": "Aggregator card",
                "publisher": "HuggingNews",
                "url": "https://huggingnews.com/ai/deepseek-v41-flash",
            },
        )
        ok, reason = self.binding(weak)
        self.assertFalse(ok)
        self.assertIn(
            reason,
            {"primary_source_not_authoritative", "weak_source_cannot_self_authorize"},
        )

    def test_cases_10_11_17_18_19_active_admission_fail_closed(self) -> None:
        candidate = self.candidate()
        url = candidate["primary_source"]["url"]
        stale_page = self.html(
            "DeepSeek replaces V4 Pro with V4.1 Flash",
            "2026-08-20T06:30:00+00:00",
        )
        wrong_date = self.process([candidate], html_by_url={url: stale_page})
        self.assertEqual(wrong_date["candidates"], [])
        self.assertTrue(any(
            "deterministic_freshness_rejected" in row.get("reason", "")
            for row in wrong_date["attempts"][-1]["binding_rejections"]
        ))

        other = self.candidate(
            title="DeepSeek releases R2",
            event_type="release",
            keywords=["R2"],
            primary_source={
                "title": "DeepSeek R2",
                "publisher": "DeepSeek",
                "url": "https://www.deepseek.com/en/news/deepseek-r2/",
            },
        )
        self.assertEqual(self.binding(other), (False, "version_identity_mismatch"))

        stale_again = self.process([candidate], html_by_url={url: stale_page})
        self.assertEqual(stale_again["candidates"], [])

        archive = {
            "items": [{
                "date": "2026-09-10",
                "source_urls": [url],
                "stories": [],
            }]
        }
        duplicate = self.process([candidate], archive=archive)
        self.assertEqual(duplicate["candidates"], [])
        self.assertTrue(any(
            row.get("reason") == "archive_exact_event_duplicate"
            for row in duplicate["attempts"][-1]["binding_rejections"]
        ))

        freshness_failed = self.candidate(freshness_status="uncertain")
        self.assertEqual(
            self.binding(freshness_failed),
            (False, "candidate_not_fresh_event"),
        )

    def test_case_12_result_order_permutation_is_deterministic_on_active_runtime(self) -> None:
        official = self.candidate()
        agency = self.candidate(
            source_type="news_agency",
            primary_source={
                "title": "DeepSeek V4.1 Flash",
                "publisher": "Reuters",
                "url": "https://www.reuters.com/world/asia-pacific/deepseek-v41/",
            },
        )
        selected = []
        for rows in ([agency, official], [official, agency]):
            result = self.process(rows)
            selected.append(result["candidates"][0]["primary_source"]["url"])
        self.assertEqual(selected[0], selected[1])
        self.assertIn("deepseek.com", selected[0])

    def test_cases_13_to_16_are_owned_by_active_v4_durable_slot_suite(self) -> None:
        recovery_cases = {
            13: "occupied_seventh_slot",
            14: "spent_before_recovery",
            15: "interrupted_ambiguous_transport",
            16: "saved_completed_resolution_replay",
        }
        self.assertEqual(
            recovery_cases,
            {case: MATRIX[case] for case in range(13, 17)},
        )
        self.assertIs(
            coverage._impl._v2._run_p3b_binding_v2,
            coverage._impl._guarded_run_p3b_binding_v2,
        )
        recovery_test = Path(__file__).with_name("test_p3b_optional_slot_recovery.py")
        source = recovery_test.read_text(encoding="utf-8")
        for required_control in (
            "test_reserved_journal_does_not_override_zero_runtime_budget",
            "test_request_started_is_ambiguous_and_never_retried",
            "test_response_saved_replays_offline_without_provider_or_page_fetch",
            "test_processed_v2_snapshot_is_reused_at_zero_runtime_budget",
        ):
            self.assertIn(required_control, source)


if __name__ == "__main__":
    unittest.main()
