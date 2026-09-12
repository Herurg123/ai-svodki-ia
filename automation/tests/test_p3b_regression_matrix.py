from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ensure_story_coverage as coverage
import weak_source_exact_binding as binder


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


class P3bExactBindingMatrixTests(unittest.TestCase):
    @staticmethod
    def signal() -> dict:
        return {
            "signal_id": "weak-source-product-deepseek-v4-1-flash",
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
            "event_type": "release",
            "keywords": ["V4 Pro", "V4.1 Flash"],
            "event_summary": "DeepSeek replaced V4 Pro with V4.1 Flash.",
            "verified_facts": [
                "DeepSeek replaced V4 Pro.",
                "V4.1 Flash is the replacement model.",
            ],
            "source_type": "official",
            "primary_source": {
                "title": "DeepSeek V4.1 Flash",
                "publisher": "DeepSeek",
                "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
            },
            "recommendation": "include",
            "verification_status": "verified",
            "freshness_status": "new_event",
            "archive_status": "none",
        }
        value.update(overrides)
        return value

    @property
    def domains(self) -> tuple[str, ...]:
        return tuple(coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS)

    def binding(self, candidate: dict, signal: dict | None = None):
        return binder.candidate_exact_binding(
            candidate,
            signal or self.signal(),
            authoritative_domains=self.domains,
        )

    def test_matrix_contract_has_exactly_twenty_named_cases(self) -> None:
        self.assertEqual(list(MATRIX), list(range(1, 21)))
        self.assertEqual(len(set(MATRIX.values())), 20)

    def test_cases_01_to_04_exact_product_and_freshness_boundaries(self) -> None:
        ok, reason = self.binding(self.candidate())
        self.assertEqual((ok, reason), (True, "exact_authoritative_binding"))

        other = self.candidate(
            title="DeepSeek launches R2",
            event_type="launch",
            keywords=["R2"],
            event_summary="DeepSeek launched R2.",
            verified_facts=["DeepSeek launched R2."],
        )
        self.assertEqual(self.binding(other), (False, "version_identity_mismatch"))

        similar = self.candidate(
            title="DeepSeek replaces V4 Pro with V4.2 Flash",
            keywords=["V4 Pro", "V4.2 Flash"],
            event_summary="DeepSeek replaced V4 Pro with V4.2 Flash.",
            verified_facts=["V4 Pro was replaced by V4.2 Flash."],
        )
        self.assertEqual(self.binding(similar), (False, "version_identity_mismatch"))

        old = self.candidate(freshness_status="old_reprint")
        self.assertEqual(self.binding(old), (False, "candidate_not_fresh_event"))

    def test_cases_05_06_and_20_lifecycle_identity_is_exact(self) -> None:
        preview_signal = self.signal()
        preview_signal["product_version_anchors"] = ["V4.1 Flash"]
        preview_signal["lifecycle_action_anchors"] = ["preview"]
        ga = self.candidate(
            title="DeepSeek announces general availability of V4.1 Flash",
            event_type="general availability",
            keywords=["V4.1 Flash", "general availability"],
            event_summary="V4.1 Flash is generally available.",
            verified_facts=["V4.1 Flash reached GA."],
        )
        self.assertEqual(
            self.binding(ga, preview_signal),
            (False, "lifecycle_identity_mismatch"),
        )

        benchmark = self.candidate(
            title="DeepSeek V4 Pro and V4.1 Flash benchmark results",
            event_type="benchmark",
            event_summary="DeepSeek compared V4 Pro and V4.1 Flash performance.",
            verified_facts=["The benchmark covered V4 Pro and V4.1 Flash."],
        )
        self.assertEqual(
            self.binding(benchmark),
            (False, "lifecycle_identity_mismatch"),
        )

        updated = self.candidate(
            title="DeepSeek updates V4 Pro and V4.1 Flash",
            event_type="update",
            event_summary="DeepSeek updated V4 Pro and V4.1 Flash.",
            verified_facts=["Both V4 Pro and V4.1 Flash were updated."],
        )
        self.assertEqual(
            self.binding(updated),
            (False, "lifecycle_identity_mismatch"),
        )

    def test_case_07_exact_authoritative_duplicate_is_terminal_not_positive(self) -> None:
        rejection = {
            "title": "DeepSeek replaced V4 Pro with V4.1 Flash",
            "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
            "reason_code": "duplicate",
            "reason": "DeepSeek replaced V4 Pro with V4.1 Flash; this exact event is already represented.",
        }
        self.assertEqual(
            binder.rejection_exact_terminal_binding(
                rejection,
                self.signal(),
                authoritative_domains=self.domains,
            ),
            (True, "exact_terminal_negative"),
        )

    def test_cases_08_09_false_alias_and_non_authoritative_source_fail_closed(self) -> None:
        alias = self.candidate(
            title="DeepSeek replaces V4 Pro with V4.1 Flashpoint",
            keywords=["V4 Pro", "V4.1 Flashpoint"],
            event_summary="DeepSeek replaced V4 Pro with V4.1 Flashpoint.",
            verified_facts=["V4 Pro was replaced by V4.1 Flashpoint."],
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

    def test_cases_10_11_17_18_19_never_promote_nonfresh_or_nonbinding_candidates(self) -> None:
        wrong_date = self.candidate(
            published_date="2025-09-10",
            published_at="2025-09-10T06:30:00+00:00",
            freshness_status="old_reprint",
        )
        self.assertEqual(
            self.binding(wrong_date),
            (False, "candidate_not_fresh_event"),
        )

        valid_other_event = self.candidate(
            title="DeepSeek releases R2",
            event_type="release",
            keywords=["R2"],
            event_summary="DeepSeek released R2.",
            verified_facts=["DeepSeek released R2."],
            primary_source={
                "title": "DeepSeek R2",
                "publisher": "DeepSeek",
                "url": "https://www.deepseek.com/en/news/deepseek-r2/",
            },
        )
        self.assertEqual(
            self.binding(valid_other_event),
            (False, "version_identity_mismatch"),
        )

        stale_official = self.candidate(freshness_status="stale")
        self.assertEqual(
            self.binding(stale_official),
            (False, "candidate_not_fresh_event"),
        )

        archive_duplicate = self.candidate(
            recommendation="exclude",
            archive_status="duplicate",
        )
        self.assertEqual(
            self.binding(archive_duplicate),
            (False, "recommendation_not_eligible"),
        )

        freshness_failed = self.candidate(freshness_status="uncertain")
        self.assertEqual(
            self.binding(freshness_failed),
            (False, "candidate_not_fresh_event"),
        )

    def test_case_12_result_order_permutation_is_deterministic(self) -> None:
        official = self.candidate()
        agency = self.candidate(
            source_type="news_agency",
            primary_source={
                "title": "DeepSeek V4.1 Flash",
                "publisher": "Reuters",
                "url": "https://www.reuters.com/world/asia-pacific/deepseek-v41/",
            },
        )
        query = "DeepSeek V4 Pro V4.1 Flash replace latest"
        metadata = {
            "status": "completed",
            "web_search_calls_completed": 1,
            "web_search_call_items_total": 1,
            "actual_queries": [query],
            "consulted_sources": [],
        }
        selected = []
        for values in ([agency, official], [official, agency]):
            result = coverage._process_p3b_payload(
                base_plan={
                    "publication_date": "2026-09-11",
                    "attempts": [],
                    "candidates": [],
                    "search_budget": {
                        "maximum_calls": 7,
                        "completed_calls": 6,
                        "remaining_calls": 1,
                    },
                },
                signal=self.signal(),
                query=query,
                prompt="prompt",
                payload={"status": "complete", "candidates": values, "rejections": []},
                metadata=metadata,
                slot_state="response_saved",
            )
            selected.append(result["candidates"][0]["primary_source"]["url"])
        self.assertEqual(selected[0], selected[1])
        self.assertIn("deepseek.com", selected[0])

    def test_cases_13_to_16_are_owned_by_durable_slot_recovery_suite(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
