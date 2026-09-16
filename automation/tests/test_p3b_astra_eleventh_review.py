from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


primary = load("p3b_eleventh_primary", "primary_recall_search.py")
binder = load("p3b_eleventh_binder", "weak_source_exact_binding_v4.py")
legacy_v2 = load("p3b_eleventh_legacy_v2", "weak_source_exact_binding_v2.py")
coverage = load("p3b_eleventh_coverage", "ensure_story_coverage.py")

WINDOW = {
    "start_at": "2026-09-15T00:00:00+00:00",
    "end_at": "2026-09-17T00:00:00+00:00",
}


class P3bAstraEleventhReviewTests(unittest.TestCase):
    @staticmethod
    def _signal(surface: str, expected_action: str) -> dict:
        reports = [
            {
                "direction_id": "china_asia_models",
                "model_rejections": [
                    {
                        "title": f"DeepSeek {surface} V4.1 Flash",
                        "organization": "DeepSeek",
                        "url": "https://example.com/weak/deepseek-v4-1-flash",
                        "reason_code": "weak_source",
                        "reason": "Weak-source clue; authoritative page not obtained.",
                    }
                ],
            }
        ]
        signals = primary.collect_unresolved_signals(reports)
        if len(signals) != 1:
            raise AssertionError(f"expected one P3a signal for {surface!r}, got {signals!r}")
        signal = signals[0]
        if signal.get("lifecycle_action_anchors") != [expected_action]:
            raise AssertionError(
                f"unexpected canonical action for {surface!r}: {signal.get('lifecycle_action_anchors')!r}"
            )
        return signal

    @staticmethod
    def _candidate(title: str, event_type: str = "release") -> dict:
        return {
            "title": title,
            "organization": "DeepSeek",
            "published_date": "2026-09-16",
            "published_at": "2026-09-16T06:30:00+00:00",
            "time_precision": "datetime",
            "topic": "models",
            "event_type": event_type,
            "keywords": ["V4.1 Flash"],
            "geography": "world",
            "category": "models",
            "source_type": "official",
            "primary_source": {
                "title": title,
                "publisher": "DeepSeek",
                "url": "https://www.deepseek.com/en/news/deepseek-v4-1-flash/",
            },
            "supporting_sources": [],
            "event_summary": title,
            "verified_facts": [title],
            "significance": "Material model lifecycle event",
            "significance_score": 4,
            "limitations": "",
            "archive_status": "none",
            "archive_reason": "",
            "recommendation": "include",
            "verification_status": "verified",
            "verification_notes": "Provider card; runtime must independently prove it.",
            "freshness_status": "new_event",
            "freshness_reason": "Provider says fresh; runtime must independently prove it.",
            "legal_scale": "not_applicable",
            "legal_scale_reason": "",
            "curiosity_eligible": False,
            "curiosity_verification": "",
        }

    @staticmethod
    def _plan() -> dict:
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
            "publication_date": "2026-09-16",
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
            "retrieval_quality": {
                "version": coverage._pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
                "status": "complete",
            },
        }

    @staticmethod
    def _html(title: str) -> str:
        return (
            "<html><head>"
            f"<title>{title}</title>"
            f"<meta property='og:title' content='{title}'>"
            "<meta property='article:published_time' content='2026-09-16T06:30:00+00:00'>"
            "</head><body>"
            f"<h1>{title}</h1><p>{title}</p>"
            "</body></html>"
        )

    def _process(self, signal: dict, candidate: dict) -> dict:
        query = binder.build_query(signal)
        title = candidate["title"]
        return coverage._process_p3b_payload_v2(
            base_plan=self._plan(),
            signal=copy.deepcopy(signal),
            query=query,
            prompt="offline eleventh-review lifecycle alignment test",
            payload={"status": "complete", "candidates": [copy.deepcopy(candidate)], "rejections": []},
            metadata={
                "status": "completed",
                "web_search_calls_completed": 1,
                "web_search_call_items_total": 1,
                "actual_queries": [query],
                "consulted_sources": [],
            },
            slot_state="response_saved",
            search_window=copy.deepcopy(WINDOW),
            archive={"items": []},
            allow_page_fetch=True,
            page_fetcher=lambda url: (self._html(title), url, 200),
        )

    def test_p3a_canonical_lifecycle_accepts_reachable_and_adjacent_morphology(self) -> None:
        # Each signal_source is a real P3a-retained surface. Two authoritative
        # claim controls deliberately use adjacent natural morphology that maps to
        # the same already-produced canonical action: bare `launch` and
        # progressive `rolling out`. They do not create new P3a semantics.
        cases = (
            ("release", "release", "release"),
            ("releases", "releases", "release"),
            ("released", "released", "release"),
            ("launched", "launch", "launch"),
            ("launches", "launches", "launch"),
            ("launched", "launched", "launch"),
            ("introduce", "introduce", "introduce"),
            ("introduces", "introduces", "introduce"),
            ("introduced", "introduced", "introduce"),
            ("unveil", "unveil", "unveil"),
            ("unveils", "unveils", "unveil"),
            ("unveiled", "unveiled", "unveil"),
            ("update", "update", "update"),
            ("updates", "updates", "update"),
            ("updated", "updated", "update"),
            ("upgrade", "upgrade", "upgrade"),
            ("upgrades", "upgrades", "upgrade"),
            ("upgraded", "upgraded", "upgrade"),
            ("ship", "ship", "ship"),
            ("ships", "ships", "ship"),
            ("shipped", "shipped", "ship"),
            ("roll out", "roll out", "rollout"),
            ("rolls out", "rolls out", "rollout"),
            ("rolled out", "rolled out", "rollout"),
            ("rolled out", "rolling out", "rollout"),
            ("preview", "preview", "preview"),
            ("general availability", "general availability", "general_availability"),
            ("generally available", "generally available", "general_availability"),
            ("retire", "retire", "retire"),
            ("retires", "retires", "retire"),
            ("retired", "retired", "retire"),
            ("discontinue", "discontinue", "retire"),
            ("discontinues", "discontinues", "retire"),
            ("discontinued", "discontinued", "retire"),
        )
        for signal_source, claim_surface, canonical in cases:
            with self.subTest(
                signal_source=signal_source,
                claim_surface=claim_surface,
                canonical=canonical,
            ):
                signal = self._signal(signal_source, canonical)
                ok, reason = binder.exact_event_identity(
                    f"DeepSeek {claim_surface} V4.1 Flash",
                    signal,
                )
                self.assertTrue(ok, reason)
                self.assertEqual(reason, "exact_event_identity")

    def test_release_signal_accepts_released_and_releases_directly(self) -> None:
        signal = self._signal("released", "release")
        for surface in (
            "DeepSeek released V4.1 Flash",
            "DeepSeek releases V4.1 Flash",
            "DeepSeek release V4.1 Flash",
        ):
            with self.subTest(surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, signal),
                    (True, "exact_event_identity"),
                )

    def test_passive_foreign_agent_remains_fail_closed_for_newly_aligned_actions(self) -> None:
        cases = (
            ("released", "release", "DeepSeek V4.1 Flash was released by OpenAI"),
            ("introduced", "introduce", "DeepSeek V4.1 Flash was introduced by OpenAI"),
            ("unveiled", "unveil", "DeepSeek V4.1 Flash was unveiled by OpenAI"),
            ("shipped", "ship", "DeepSeek V4.1 Flash was shipped by OpenAI"),
            ("rolled out", "rollout", "DeepSeek V4.1 Flash was rolled out by OpenAI"),
            ("retired", "retire", "DeepSeek V4.1 Flash was retired by OpenAI"),
        )
        for source_surface, canonical, claim in cases:
            with self.subTest(canonical=canonical):
                signal = self._signal(source_surface, canonical)
                ok, reason = binder.exact_event_identity(claim, signal)
                self.assertFalse(ok)
                self.assertEqual(reason, "organization_event_attribution_mismatch")

    def test_passive_same_agent_positive_control(self) -> None:
        signal = self._signal("released", "release")
        self.assertEqual(
            binder.exact_event_identity(
                "DeepSeek V4.1 Flash was released by DeepSeek",
                signal,
            ),
            (True, "exact_event_identity"),
        )

    def test_release_morphology_survives_real_coverage_and_freshness_path(self) -> None:
        signal = self._signal("released", "release")
        candidate = self._candidate("DeepSeek released V4.1 Flash", event_type="release")
        result = self._process(signal, candidate)
        self.assertEqual(result["weak_source_exact_binding"]["status"], "bound_candidate")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["search_budget"]["remaining_calls"], 0)
        self.assertEqual(result["candidates"][0]["p3b_exact_binding_version"], 2)

    def test_foreign_passive_release_is_rejected_by_real_coverage_path(self) -> None:
        signal = self._signal("released", "release")
        candidate = self._candidate(
            "DeepSeek V4.1 Flash was released by OpenAI",
            event_type="release",
        )
        result = self._process(signal, candidate)
        self.assertEqual(result["weak_source_exact_binding"]["status"], "unresolved")
        self.assertEqual(result["candidates"], [])
        reasons = [row["reason"] for row in result["attempts"][-1]["binding_rejections"]]
        self.assertIn("organization_event_attribution_mismatch", reasons)

    def test_historical_v2_source_contract_is_not_mutated(self) -> None:
        self.assertNotIn("release", legacy_v2._LIFECYCLE_GROUPS)
        for action in ("introduce", "unveil", "ship", "rollout", "retire"):
            self.assertNotIn(action, legacy_v2._LIFECYCLE_GROUPS)
        self.assertEqual(binder.VERSION, 2)
        self.assertEqual(binder.EVIDENCE_VERSION, 6)


if __name__ == "__main__":
    unittest.main()
