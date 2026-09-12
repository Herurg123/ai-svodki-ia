from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
FIXTURE = (
    ROOT
    / "automation"
    / "fixtures"
    / "recall"
    / "weak-source-signal-retention-2026-09-11.json"
)
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


primary = load("p3b_primary", "primary_recall_search.py")
binder = load("p3b_binder", "weak_source_exact_binding.py")
coverage = load("p3b_coverage", "ensure_story_coverage.py")


class P3bExactAuthoritativeBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        rejection = cls.fixture["positive_control"]["rejection"]
        cls.signal = primary.collect_unresolved_signals(
            [
                {
                    "direction_id": cls.fixture["positive_control"]["direction_id"],
                    "model_rejections": [rejection],
                }
            ]
        )[0]

    def _candidate(
        self,
        *,
        title: str = "DeepSeek replaces V4 Pro with V4.1 Flash",
        organization: str = "DeepSeek",
        event_summary: str = "DeepSeek replaced V4 Pro with V4.1 Flash.",
        event_type: str = "release",
        keywords: list[str] | None = None,
        facts: list[str] | None = None,
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
            "keywords": keywords or ["V4 Pro", "V4.1 Flash"],
            "geography": "world",
            "category": "models",
            "source_type": source_type,
            "primary_source": {
                "title": "DeepSeek V4.1 Flash",
                "publisher": "DeepSeek",
                "url": source_url,
            },
            "supporting_sources": [],
            "event_summary": event_summary,
            "verified_facts": facts
            or [
                "DeepSeek replaced V4 Pro.",
                "V4.1 Flash is the replacement model.",
            ],
            "significance": "Material model release",
            "significance_score": 4,
            "limitations": "",
            "archive_status": "none",
            "archive_reason": "",
            "recommendation": "include",
            "verification_status": "verified",
            "verification_notes": "Official release.",
            "freshness_status": freshness,
            "freshness_reason": "New release inside the window.",
            "legal_scale": "not_applicable",
            "legal_scale_reason": "",
            "curiosity_eligible": False,
            "curiosity_verification": "",
        }

    def _base_plan(self) -> dict:
        attempts = [
            {
                "direction_id": direction_id,
                "attempt": 1,
                "status": "checked_with_gaps",
                "api": {
                    "status": "completed",
                    "web_search_calls_completed": 1,
                    "web_search_call_items_total": 1,
                },
            }
            for direction_id in coverage._pre.AUDIT_DIRECTION_IDS
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
                "response_attempts": 6,
                "observed_call_items": 6,
                "completed_calls": 6,
                "remaining_calls": 1,
                "exhausted": False,
                "search_budget_exhausted": False,
                "response_attempt_limit_exhausted": False,
                "provider_overrun": False,
            },
            "retrieval_quality_contract_version": coverage._pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
            "retrieval_quality": {
                "version": coverage._pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
                "status": "complete",
            },
        }

    def _metadata(self, query: str) -> dict:
        return {
            "status": "completed",
            "web_search_calls_completed": 1,
            "web_search_call_items_total": 1,
            "actual_queries": [query],
            "consulted_sources": [
                {"url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/"}
            ],
        }

    def test_p3a_signal_becomes_only_qualified_p3b_input_not_mutated(self) -> None:
        report = {
            "retrieval_quality_contract_version": primary.RETRIEVAL_QUALITY_CONTRACT_VERSION,
            "unresolved_signals": [copy.deepcopy(self.signal)],
        }
        signals = binder.qualifying_signals(
            report,
            contract_version=primary.RETRIEVAL_QUALITY_CONTRACT_VERSION,
        )
        self.assertEqual(len(signals), 1)
        self.assertFalse(signals[0]["resolution_required"])
        self.assertFalse(signals[0]["candidate_eligible"])
        self.assertEqual(
            signals[0]["resolution_eligibility"],
            "deferred_exact_authoritative_binding",
        )

    def test_query_is_single_date_free_publisher_neutral_exact_identity_hint(self) -> None:
        query = binder.build_query(self.signal)
        self.assertEqual(query, "DeepSeek V4 Pro V4.1 Flash replace latest")
        folded = query.casefold()
        for forbidden in ("site:", "reuters", "bloomberg", "2026-"):
            self.assertNotIn(forbidden, folded)

    def test_baseline_fuzzy_match_accepts_same_company_different_event_but_p3b_rejects(self) -> None:
        candidate = self._candidate(
            title="DeepSeek launches R2 model",
            event_summary="DeepSeek launches the R2 model.",
            event_type="launch",
            keywords=["DeepSeek", "R2", "model"],
            facts=["DeepSeek launched R2.", "R2 is a model release."],
        )
        legacy_signal = copy.deepcopy(self.signal)
        legacy_signal["entities"] = ["DeepSeek"]
        self.assertTrue(
            coverage._pre._candidate_matches_cluster(candidate, [legacy_signal])
        )
        ok, reason = binder.candidate_exact_binding(
            candidate,
            self.signal,
            authoritative_domains=tuple(
                coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS
            ),
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "version_identity_mismatch")

    def test_similar_version_is_not_exact_event(self) -> None:
        candidate = self._candidate(
            title="DeepSeek replaces V4 Pro with V4.2 Flash",
            event_summary="DeepSeek replaced V4 Pro with V4.2 Flash.",
            keywords=["V4 Pro", "V4.2 Flash"],
            facts=["V4 Pro was replaced.", "V4.2 Flash is the replacement."],
        )
        ok, reason = binder.candidate_exact_binding(
            candidate,
            self.signal,
            authoritative_domains=tuple(
                coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS
            ),
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "version_identity_mismatch")

    def test_preview_and_general_availability_are_different_events(self) -> None:
        signal = copy.deepcopy(self.signal)
        signal["product_version_anchors"] = ["V4.1 Flash"]
        signal["lifecycle_action_anchors"] = ["preview"]
        candidate = self._candidate(
            title="DeepSeek announces general availability of V4.1 Flash",
            event_summary="V4.1 Flash is generally available.",
            event_type="general availability",
            keywords=["V4.1 Flash", "general availability"],
            facts=["V4.1 Flash reached GA.", "The model is generally available."],
        )
        ok, reason = binder.candidate_exact_binding(
            candidate,
            signal,
            authoritative_domains=tuple(
                coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS
            ),
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "lifecycle_identity_mismatch")

    def test_old_release_and_missing_authoritative_proof_remain_negative(self) -> None:
        old = self._candidate(freshness="old_reprint")
        ok, reason = binder.candidate_exact_binding(
            old,
            self.signal,
            authoritative_domains=tuple(
                coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS
            ),
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "candidate_not_fresh_event")

        weak = self._candidate(
            source_url=self.signal["source_provenance"]["url"],
            source_type="technology_media",
        )
        ok, reason = binder.candidate_exact_binding(
            weak,
            self.signal,
            authoritative_domains=tuple(
                coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS
            ),
        )
        self.assertFalse(ok)
        self.assertIn(
            reason,
            {"primary_source_not_authoritative", "weak_source_cannot_self_authorize"},
        )

    def test_unverified_never_auto_closes_weak_signal(self) -> None:
        rejection = {
            "title": "DeepSeek replaces V4 Pro with V4.1 Flash",
            "url": "https://www.reuters.com/world/asia-pacific/deepseek-v41/",
            "reason_code": "unverified",
            "reason": "Could not prove the exact product transition.",
        }
        ok, reason = binder.rejection_exact_terminal_binding(
            rejection,
            self.signal,
            authoritative_domains=tuple(
                coverage._policy.AUTHORITATIVE_LAST_MILE_DOMAINS
            ),
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "rejection_not_terminal")

    def test_exact_authoritative_positive_is_admitted_once(self) -> None:
        plan = self._base_plan()
        query = binder.build_query(self.signal)
        payload = {
            "status": "complete",
            "candidates": [self._candidate()],
            "rejections": [],
        }
        result = coverage._process_p3b_payload(
            base_plan=plan,
            signal=self.signal,
            query=query,
            prompt="prompt",
            payload=payload,
            metadata=self._metadata(query),
            slot_state="response_saved",
        )
        self.assertEqual(
            result["weak_source_exact_binding"]["status"], "bound_candidate"
        )
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(
            result["candidates"][0]["audit_direction"],
            "weak_source_exact_binding",
        )
        self.assertEqual(result["search_budget"]["remaining_calls"], 0)
        p3b_attempts = [
            item
            for item in result["attempts"]
            if item.get("p3b_exact_binding_version") == 1
        ]
        self.assertEqual(len(p3b_attempts), 1)
        self.assertNotIn("unresolved_resolution_version", p3b_attempts[0])

    def test_authoritative_reference_outside_binding_path_does_not_admit_candidate(self) -> None:
        plan = self._base_plan()
        query = binder.build_query(self.signal)
        metadata = self._metadata(query)
        metadata["consulted_sources"].append(
            {"url": "https://www.reuters.com/world/asia-pacific/deepseek-v41/"}
        )
        result = coverage._process_p3b_payload(
            base_plan=plan,
            signal=self.signal,
            query=query,
            prompt="prompt",
            payload={"status": "complete_with_gaps", "candidates": [], "rejections": []},
            metadata=metadata,
            slot_state="response_saved",
        )
        self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["audit_status"], "complete_with_gaps")

    def test_provider_ordering_chooses_deterministic_authoritative_candidate(self) -> None:
        official = self._candidate()
        agency = self._candidate(
            source_url="https://www.reuters.com/world/asia-pacific/deepseek-v41/",
            source_type="news_agency",
        )
        query = binder.build_query(self.signal)
        selected_urls = []
        for candidates in ([agency, official], [official, agency]):
            result = coverage._process_p3b_payload(
                base_plan=self._base_plan(),
                signal=self.signal,
                query=query,
                prompt="prompt",
                payload={"status": "complete", "candidates": candidates, "rejections": []},
                metadata=self._metadata(query),
                slot_state="response_saved",
            )
            selected_urls.append(result["candidates"][0]["primary_source"]["url"])
        self.assertEqual(selected_urls[0], selected_urls[1])
        self.assertIn("deepseek.com", selected_urls[0])

    def test_existing_required_unverified_keeps_slot_priority(self) -> None:
        original_exec = coverage._P3A_EXECUTE_AUDIT_PLAN
        original_required = coverage._pre._required_signals
        original_p3b_signals = coverage._p3b_signals
        original_run = coverage._run_p3b_binding
        calls = []
        try:
            coverage._P3A_EXECUTE_AUDIT_PLAN = lambda *args, **kwargs: self._base_plan()
            coverage._pre._required_signals = lambda _date: [
                {"signal_id": "legacy-required"}
            ]
            coverage._p3b_signals = lambda _date: [copy.deepcopy(self.signal)]
            coverage._run_p3b_binding = lambda **kwargs: calls.append(kwargs) or kwargs["plan"]
            result = coverage.execute_audit_plan(
                publication_date="2026-09-11",
                api_key="unused",
                model="unused",
                search_window={},
                archive={},
            )
        finally:
            coverage._P3A_EXECUTE_AUDIT_PLAN = original_exec
            coverage._pre._required_signals = original_required
            coverage._p3b_signals = original_p3b_signals
            coverage._run_p3b_binding = original_run
        self.assertEqual(calls, [])
        self.assertEqual(result["weak_source_exact_binding"]["status"], "deferred")
        self.assertIn("slot priority", result["weak_source_exact_binding"]["reason"])

    def test_consumed_optional_slot_cannot_create_eighth_search(self) -> None:
        original_exec = coverage._P3A_EXECUTE_AUDIT_PLAN
        original_required = coverage._pre._required_signals
        original_p3b_signals = coverage._p3b_signals
        original_load = coverage.load_journal
        original_consumed = coverage.slot_is_consumed_or_ambiguous
        original_run = coverage._run_p3b_binding
        calls = []
        try:
            coverage._P3A_EXECUTE_AUDIT_PLAN = lambda *args, **kwargs: self._base_plan()
            coverage._pre._required_signals = lambda _date: []
            coverage._p3b_signals = lambda _date: [copy.deepcopy(self.signal)]
            coverage.load_journal = lambda *_args, **_kwargs: {
                "state": "request_started",
                "slot_consumed_or_ambiguous": True,
            }
            coverage.slot_is_consumed_or_ambiguous = lambda *_args, **_kwargs: True
            coverage._run_p3b_binding = lambda **kwargs: calls.append(kwargs) or kwargs["plan"]
            result = coverage.execute_audit_plan(
                publication_date="2026-09-11",
                api_key="unused",
                model="unused",
                search_window={},
                archive={},
            )
        finally:
            coverage._P3A_EXECUTE_AUDIT_PLAN = original_exec
            coverage._pre._required_signals = original_required
            coverage._p3b_signals = original_p3b_signals
            coverage.load_journal = original_load
            coverage.slot_is_consumed_or_ambiguous = original_consumed
            coverage._run_p3b_binding = original_run
        self.assertEqual(calls, [])
        self.assertEqual(result["weak_source_exact_binding"]["status"], "deferred")
        self.assertEqual(result["search_budget"]["remaining_calls"], 0)
        self.assertLessEqual(
            result["search_budget"]["effective_consumed_calls"], 7
        )

    def test_signal_selection_is_order_independent(self) -> None:
        low = copy.deepcopy(self.signal)
        low["signal_id"] = "sig-z"
        low["likely_significance_score"] = 3
        high = copy.deepcopy(self.signal)
        high["signal_id"] = "sig-a"
        high["likely_significance_score"] = 5
        for values in ([low, high], [high, low]):
            selected = binder.select_signal(values)
            self.assertEqual(selected["signal_id"], "sig-a")


if __name__ == "__main__":
    unittest.main()
