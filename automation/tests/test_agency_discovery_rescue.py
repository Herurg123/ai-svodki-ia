from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import agency_discovery_rescue as rescue
import primary_recall_search as primary_recall
from source_freshness import verify_candidate


PUBLICATION_DATE = "2026-08-23"
WINDOW = {
    "start_date": "2026-08-21",
    "end_date": "2026-08-23",
    "start_at": "2026-08-21T02:37:50+03:00",
    "end_at": "2026-08-23T02:35:04+03:00",
}


def candidate(
    *,
    title: str = "Nvidia raises AI server prices",
    organization: str = "Nvidia",
    event_type: str = "pricing_change",
    published_date: str = "2026-08-22",
    published_at: str | None = "2026-08-22T19:21:00+00:00",
    url: str = "https://www.reuters.com/technology/nvidia-ai-server-prices-2026-08-22/",
    recommendation: str = "include",
    significance_score: int = 5,
) -> dict:
    return {
        "title": title,
        "organization": organization,
        "published_date": published_date,
        "published_at": published_at,
        "time_precision": "datetime" if published_at else "date",
        "topic": "AI server pricing",
        "event_type": event_type,
        "geography": "world",
        "category": "infrastructure",
        "source_type": "news_agency",
        "event_summary": "A material AI infrastructure business event.",
        "significance": "Material industry impact.",
        "significance_score": significance_score,
        "archive_status": "none",
        "archive_reason": "No matching archived event.",
        "recommendation": recommendation,
        "keywords": ["AI", "servers", "pricing"],
        "verified_facts": ["fact one", "fact two"],
        "verification_status": "verified",
        "verification_notes": "Direct agency source checked.",
        "freshness_status": "new_event",
        "freshness_reason": "Reported inside the effective window.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
        "primary_source": {
            "title": title,
            "publisher": "Reuters",
            "url": url,
        },
        "supporting_sources": [],
    }


def research(existing: list[dict] | None = None) -> dict:
    return {
        "status": "ok",
        "error_message": None,
        "search_window": copy.deepcopy(WINDOW),
        "candidates": copy.deepcopy(existing or []),
        "coverage": [],
        "research_notes": "fixture",
    }


def primary_report(*, raw_count: int, accepted_count: int, status: str = "complete") -> dict:
    raw = [
        {
            "title": f"raw-{index}",
            "organization": "Example",
            "event_type": "example",
            "published_date": "2026-08-22",
        }
        for index in range(raw_count)
    ]
    return {
        "status": "complete",
        "directions": [
            {
                "direction_id": "major_agencies",
                "status": status,
                "raw_candidates": raw,
                "accepted_count": accepted_count,
                "web_search_calls_completed": 1,
                "api": {"web_search_calls_completed": 1},
            }
        ],
    }


def response_payload(rows: list[dict]) -> dict:
    return {
        "status": "complete" if rows else "complete_with_gaps",
        "error_message": None,
        "direction_id": rescue.AGENCY_DISCOVERY_RESCUE_DIRECTION,
        "candidates": copy.deepcopy(rows),
        "rejections": [],
        "notes": "fixture response",
    }


def metadata() -> dict:
    return {
        "web_search_calls_completed": 1,
        "web_search_call_items_total": 1,
        "web_search_navigation_items_total": 0,
        "actual_queries": [rescue.AGENCY_DISCOVERY_RESCUE_QUERY],
        "consulted_sources": ["https://www.reuters.com/"],
    }


class RescueFixture:
    def __init__(self, *, raw_count: int = 0, accepted_count: int = 0, existing=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "artifact"
        self.output = self.root / "production-daily"
        self.archive = self.root / "archive.json"
        self.artifact.mkdir()
        self.output.mkdir()
        (self.artifact / "candidates.json").write_text(
            json.dumps(research(existing), ensure_ascii=False), encoding="utf-8"
        )
        (self.artifact / "primary-recall.json").write_text(
            json.dumps(primary_report(raw_count=raw_count, accepted_count=accepted_count)),
            encoding="utf-8",
        )
        self.archive.write_text(json.dumps({"items": []}), encoding="utf-8")

    def close(self):
        self.tmp.cleanup()

    def run(self, runner, *, maximum_candidates: int = 20):
        return rescue.run_agency_discovery_rescue(
            artifact_dir=self.artifact,
            archive_path=self.archive,
            publication_date=PUBLICATION_DATE,
            api_key="test-key",
            model="test-model",
            maximum_candidates=maximum_candidates,
            search_runner=runner,
            output_root=self.output,
        )


class AgencyDiscoveryRescueTests(unittest.TestCase):
    def test_raw_positive_and_accepted_positive_does_not_search(self):
        fx = RescueFixture(raw_count=1, accepted_count=1)
        calls = 0

        def forbidden(**_kwargs):
            nonlocal calls
            calls += 1
            raise AssertionError("search must not run")

        try:
            report = fx.run(forbidden)
            self.assertFalse(report["triggered"])
            self.assertFalse(report["executed"])
            self.assertEqual(calls, 0)
            self.assertEqual(report["search_operation_count_contribution"], 0)
        finally:
            fx.close()

    def test_raw_zero_triggers_exactly_one_search_even_when_pool_is_already_full(self):
        existing = [
            candidate(
                title=f"Existing {index}",
                organization=f"Org {index}",
                event_type=f"event_{index}",
                url=f"https://example.com/{index}",
            )
            for index in range(9)
        ]
        fx = RescueFixture(raw_count=0, accepted_count=0, existing=existing)
        calls = 0

        def empty(**_kwargs):
            nonlocal calls
            calls += 1
            return response_payload([]), metadata()

        try:
            report = fx.run(empty)
            self.assertEqual(calls, 1)
            self.assertTrue(report["triggered"])
            self.assertEqual(report["trigger_reason"], "major_agencies_raw_zero")
            self.assertTrue(report["candidate_count_independent_trigger"])
            self.assertEqual(report["candidate_pool_count_at_trigger"], 9)
            self.assertEqual(report["state"], "completed_no_addition")
        finally:
            fx.close()

    def test_raw_positive_accepted_zero_triggers_rescue(self):
        fx = RescueFixture(raw_count=2, accepted_count=0)
        calls = 0

        def empty(**_kwargs):
            nonlocal calls
            calls += 1
            return response_payload([]), metadata()

        try:
            report = fx.run(empty)
            self.assertEqual(calls, 1)
            self.assertEqual(report["trigger_reason"], "major_agencies_accepted_zero")
        finally:
            fx.close()

    def test_valid_new_candidate_is_merged(self):
        fx = RescueFixture()
        try:
            report = fx.run(lambda **_kwargs: (response_payload([candidate()]), metadata()))
            merged = json.loads((fx.artifact / "candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(report["added_count"], 1)
            self.assertEqual(len(merged["candidates"]), 1)
            self.assertEqual(
                merged["candidates"][0]["audit_direction"],
                rescue.AGENCY_DISCOVERY_RESCUE_DIRECTION,
            )
        finally:
            fx.close()

    def test_same_event_different_url_is_rejected_as_duplicate(self):
        known = candidate(url="https://example.com/known-nvidia")
        fx = RescueFixture(existing=[known])
        rescued = candidate(
            url="https://www.reuters.com/technology/different-url-same-event-2026-08-22/"
        )
        try:
            report = fx.run(lambda **_kwargs: (response_payload([rescued]), metadata()))
            merged = json.loads((fx.artifact / "candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(report["added_count"], 0)
            self.assertEqual(report["duplicate_count"], 1)
            self.assertEqual(len(merged["candidates"]), 1)
        finally:
            fx.close()

    def test_out_of_window_candidate_is_rejected_before_editorial(self):
        fx = RescueFixture()
        stale = candidate(
            published_date="2026-08-20",
            published_at="2026-08-20T12:00:00+00:00",
        )
        try:
            report = fx.run(lambda **_kwargs: (response_payload([stale]), metadata()))
            self.assertEqual(report["added_count"], 0)
            errors = " ".join(
                " ".join(item.get("errors") or [])
                for item in report.get("rejections") or []
                if isinstance(item, dict)
            )
            self.assertIn("вне редакционного окна", errors)
        finally:
            fx.close()

    def test_existing_source_freshness_proof_excludes_stale_reuters_timestamp(self):
        row = candidate()
        start = datetime.fromisoformat(WINDOW["start_at"])
        end = datetime.fromisoformat(WINDOW["end_at"])

        def stale_fetcher(url: str):
            html = (
                '<html><head><meta property="article:published_time" '
                'content="2026-08-20T12:00:00+00:00"></head></html>'
            )
            return html, url, 200

        record = verify_candidate(
            row, start_at=start, end_at=end, fetcher=stale_fetcher
        )
        self.assertEqual(record["status"], "excluded_outside_window")
        self.assertEqual(row["recommendation"], "exclude")
        self.assertEqual(row["freshness_status"], "old_reprint")

    def test_weak_candidate_gets_no_agency_privilege(self):
        fx = RescueFixture()
        weak = candidate(recommendation="consider", significance_score=1)
        try:
            report = fx.run(lambda **_kwargs: (response_payload([weak]), metadata()))
            merged = json.loads((fx.artifact / "candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(report["added_count"], 1)
            found = merged["candidates"][0]
            self.assertEqual(found["recommendation"], "consider")
            self.assertEqual(found["significance_score"], 1)
            self.assertNotIn("must_include", found)
        finally:
            fx.close()

    def test_zero_result_is_non_fatal(self):
        fx = RescueFixture()
        try:
            report = fx.run(lambda **_kwargs: (response_payload([]), metadata()))
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["state"], "completed_no_addition")
            self.assertEqual(report["raw_count"], 0)
            self.assertEqual(report["added_count"], 0)
        finally:
            fx.close()

    def test_completed_rescue_is_idempotent_on_resume(self):
        fx = RescueFixture()
        calls = 0

        def first(**_kwargs):
            nonlocal calls
            calls += 1
            return response_payload([candidate()]), metadata()

        try:
            first_report = fx.run(first)
            self.assertEqual(first_report["added_count"], 1)

            def forbidden(**_kwargs):
                raise AssertionError("resume must not search again")

            resumed = fx.run(forbidden)
            self.assertTrue(resumed["resumed"])
            self.assertEqual(resumed["search_operation_count_contribution"], 1)
            self.assertEqual(calls, 1)
            merged = json.loads((fx.artifact / "candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(len(merged["candidates"]), 1)
        finally:
            fx.close()

    def test_merge_failure_reuses_saved_search_response_without_second_search(self):
        fx = RescueFixture()
        calls = 0

        def once(**_kwargs):
            nonlocal calls
            calls += 1
            return response_payload([candidate()]), metadata()

        real_merge = rescue.merge_candidates
        try:
            with mock.patch.object(rescue, "merge_candidates", side_effect=RuntimeError("boom")):
                partial = fx.run(once)
            self.assertEqual(partial["state"], "merge_failed")
            self.assertEqual(calls, 1)

            def forbidden(**_kwargs):
                raise AssertionError("saved search response must be reused")

            with mock.patch.object(rescue, "merge_candidates", wraps=real_merge):
                resumed = fx.run(forbidden)
            self.assertEqual(calls, 1)
            self.assertEqual(resumed["state"], "completed")
            self.assertEqual(resumed["added_count"], 1)
            self.assertTrue(resumed["recovered_from_artifact"])
        finally:
            fx.close()

    def test_search_started_partial_state_never_retries_unknown_operation(self):
        fx = RescueFixture()
        try:
            base = rescue._base_report(
                publication_date=PUBLICATION_DATE,
                trigger_reason="major_agencies_raw_zero",
                trigger_facts={
                    "major_agencies_status": "complete",
                    "major_agencies_raw_count": 0,
                    "major_agencies_accepted_count": 0,
                },
                candidate_pool_count=0,
            )
            base.update(
                {
                    "triggered": True,
                    "executed": True,
                    "state": "search_started",
                    "search_operation_reserved": 1,
                }
            )
            rescue._persist_report(
                base,
                artifact_dir=fx.artifact,
                output_root=fx.output,
                publication_date=PUBLICATION_DATE,
            )

            def forbidden(**_kwargs):
                raise AssertionError("indeterminate search must not be retried")

            report = fx.run(forbidden)
            self.assertEqual(report["state"], "indeterminate_after_interruption")
            self.assertEqual(report["search_operation_count_contribution"], 1)
            self.assertFalse(report["search_retry_allowed"])
        finally:
            fx.close()

    def test_non_direct_agency_source_is_not_added(self):
        fx = RescueFixture()
        syndicated = candidate(url="https://example.com/reuters-syndication")
        try:
            report = fx.run(
                lambda **_kwargs: (response_payload([syndicated]), metadata())
            )
            self.assertEqual(report["added_count"], 0)
            reasons = {
                item.get("reason_code")
                for item in report.get("rejections") or []
                if isinstance(item, dict)
            }
            self.assertIn("non_direct_reuters_ap_source", reasons)
        finally:
            fx.close()

    def test_primary_and_regional_routes_are_not_consumed_by_rescue(self):
        ids = tuple(str(item["id"]) for item in primary_recall.PRIMARY_DIRECTIONS)
        self.assertEqual(primary_recall.DEFAULT_MAXIMUM_SEARCH_CALLS, 12)
        self.assertIn("china_asia_models", ids)
        self.assertIn("china_asia_integrations", ids)
        self.assertIn("russia", ids)

    def test_budget_is_explicitly_bounded_at_24(self):
        self.assertEqual(rescue.MAXIMUM_SEARCH_OPERATIONS, 1)
        self.assertEqual(rescue.PIPELINE_MAXIMUM_SEARCH_OPERATIONS, 24)
        self.assertEqual(
            rescue.PIPELINE_MAXIMUM_SEARCH_OPERATIONS,
            12 + 1 + 4 + 7,
        )

    def test_discovery_diagnostics_are_distinct_from_corroboration(self):
        self.assertEqual(
            rescue.AGENCY_DISCOVERY_RESCUE_STRATEGY,
            "agency_discovery_rescue",
        )
        self.assertNotEqual(
            rescue.AGENCY_DISCOVERY_RESCUE_STRATEGY,
            "fresh_agency_rescue",
        )


if __name__ == "__main__":
    unittest.main()
