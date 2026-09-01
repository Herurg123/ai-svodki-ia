from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agency_discovery_rescue_v5 as v5
import agency_health_viability as health
import recover_digest_artifact as recovery

DATE = "2026-09-01"
REUTERS_URL = "https://www.reuters.com/technology/example-ai-event-2026-09-01/"
PULSE_URL = "https://example.com/same-title-different-source"


def row(
    *,
    url: str = REUTERS_URL,
    title: str = "Major AI infrastructure deal",
    recommendation: str = "include",
    freshness_status: str = "new_event",
    event_freshness_status: str = "unknown",
    supporting_urls: tuple[str, ...] = (),
) -> dict:
    return {
        "title": title,
        "organization": "Example AI",
        "event_type": "infrastructure_deal",
        "published_date": DATE,
        "recommendation": recommendation,
        "freshness_status": freshness_status,
        "event_freshness_status": event_freshness_status,
        "primary_source": {
            "title": title,
            "publisher": "Reuters" if "reuters.com" in url else "Other",
            "url": url,
        },
        "supporting_sources": [
            {"title": "support", "publisher": "Reuters", "url": value}
            for value in supporting_urls
        ],
    }


def primary(candidate: dict | None = None) -> dict:
    candidate = copy.deepcopy(candidate or row())
    return {
        "publication_date": DATE,
        "status": "complete",
        "directions": [
            {
                "direction_id": "major_agencies",
                "status": "complete",
                "raw_candidates": [copy.deepcopy(candidate)],
                "accepted_count": 1,
            }
        ],
        "final_candidates": [copy.deepcopy(candidate)],
        "regional_health": {},
    }


def research(candidate: dict | None = None) -> dict:
    return {
        "status": "ok",
        "search_window": {
            "start_at": "2026-08-31T02:00:00+03:00",
            "end_at": "2026-09-01T02:00:00+03:00",
        },
        "candidates": [copy.deepcopy(candidate or row())],
    }


def empty_response() -> dict:
    return {
        "status": "complete_with_gaps",
        "error_message": None,
        "direction_id": v5.AGENCY_DISCOVERY_RESCUE_DIRECTION,
        "candidates": [],
        "rejections": [],
        "notes": "controlled empty response",
    }


def metadata() -> dict:
    return {
        "web_search_calls_completed": 1,
        "web_search_call_items_total": 1,
        "web_search_navigation_items_total": 0,
        "actual_queries": [v5.AGENCY_DISCOVERY_RESCUE_QUERY],
        "consulted_sources": ["https://www.reuters.com/"],
        "web_search_call_items": [],
    }


class AgencyHealthPureTests(unittest.TestCase):
    def test_stale_primary_agency_survivor_reopens_rescue(self):
        stale = row(recommendation="exclude", freshness_status="old_reprint")
        triggered, reason, facts, diagnostics = health.evaluate_agency_health(
            primary_report=primary(), current_research=research(stale)
        )
        self.assertTrue(triggered)
        self.assertEqual(reason, health.POST_FILTER_TRIGGER_REASON)
        self.assertEqual(facts["major_agencies_post_filter_viable_count"], 0)
        self.assertEqual(diagnostics["status"], "no_viable_survivor_after_filtering")
        self.assertEqual(diagnostics["web_search_operations"], 0)

    def test_viable_primary_agency_survivor_suppresses_rescue(self):
        triggered, reason, facts, diagnostics = health.evaluate_agency_health(
            primary_report=primary(), current_research=research(row())
        )
        self.assertFalse(triggered)
        self.assertIsNone(reason)
        self.assertEqual(facts["major_agencies_post_filter_viable_count"], 1)
        self.assertEqual(diagnostics["status"], "viable_primary_agency_survivor")

    def test_primary_identity_survives_when_reuters_url_moves_to_supporting_source(self):
        promoted = row(
            url="https://official.example.com/announcement",
            supporting_urls=(REUTERS_URL,),
        )
        triggered, reason, facts, diagnostics = health.evaluate_agency_health(
            primary_report=primary(), current_research=research(promoted)
        )
        self.assertFalse(triggered)
        self.assertIsNone(reason)
        self.assertEqual(facts["major_agencies_post_filter_matched_count"], 1)
        self.assertEqual(diagnostics["viable_count"], 1)

    def test_unrelated_pulse_same_title_cannot_impersonate_primary_agency_candidate(self):
        pulse = row(url=PULSE_URL)
        triggered, reason, facts, diagnostics = health.evaluate_agency_health(
            primary_report=primary(), current_research=research(pulse)
        )
        self.assertFalse(triggered)
        self.assertIsNone(reason)
        self.assertEqual(facts["major_agencies_post_filter_unmatched_count"], 1)
        self.assertEqual(diagnostics["status"], "identity_incomplete_preserved")


class AgencyHealthRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifact = self.root / "artifact"
        self.output = self.root / "output"
        self.archive = self.root / "archive.json"
        self.artifact.mkdir()
        self.output.mkdir()
        self.archive.write_text('{"items": []}\n', encoding="utf-8")
        (self.artifact / "primary-recall.json").write_text(
            json.dumps(primary(), ensure_ascii=False), encoding="utf-8"
        )
        stale = row(recommendation="exclude", freshness_status="old_reprint")
        (self.artifact / "candidates.json").write_text(
            json.dumps(research(stale), ensure_ascii=False), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def _run(self, runner):
        return v5.run_agency_discovery_rescue(
            artifact_dir=self.artifact,
            archive_path=self.archive,
            publication_date=DATE,
            api_key="test-key",
            model="test-model",
            search_runner=runner,
            output_root=self.output,
        )

    def _save_old_not_triggered(self):
        report = {
            "version": 5,
            "search_strategy": "agency_discovery_rescue",
            "publication_date": DATE,
            "triggered": False,
            "trigger_reason": None,
            "executed": False,
            "state": "not_triggered",
            "status": "complete",
            "search_operation_reserved": 0,
            "search_operation_count_contribution": 0,
            "search_retry_allowed": False,
            "added_count": 0,
        }
        (self.artifact / "agency-discovery-rescue.json").write_text(
            json.dumps(report), encoding="utf-8"
        )

    def test_old_zero_spend_not_triggered_is_rechecked_and_uses_existing_slot_once(self):
        self._save_old_not_triggered()
        calls = 0

        def runner(**_kwargs):
            nonlocal calls
            calls += 1
            return empty_response(), metadata()

        first = self._run(runner)
        self.assertEqual(calls, 1)
        self.assertTrue(first["triggered"])
        self.assertEqual(first["trigger_reason"], health.POST_FILTER_TRIGGER_REASON)
        self.assertTrue(first["prior_not_triggered_rechecked"])
        self.assertEqual(first["search_operation_count_contribution"], 1)
        self.assertEqual(first["state"], "completed_no_addition")
        self.assertEqual(first["agency_health_trigger_version"], 2)

        def forbidden(**_kwargs):
            raise AssertionError("completed rescue must never search twice")

        second = self._run(forbidden)
        self.assertTrue(second["resumed"])
        self.assertEqual(second["search_operation_count_contribution"], 1)
        self.assertEqual(calls, 1)

    def test_search_started_remains_at_most_once_even_when_health_now_triggers(self):
        report = {
            "version": 5,
            "search_strategy": "agency_discovery_rescue",
            "publication_date": DATE,
            "triggered": True,
            "trigger_reason": health.POST_FILTER_TRIGGER_REASON,
            "executed": True,
            "state": "search_started",
            "status": "complete_with_gaps",
            "search_operation_reserved": 1,
            "search_operation_count_contribution": 0,
            "search_retry_allowed": False,
            "added_count": 0,
        }
        (self.artifact / "agency-discovery-rescue.json").write_text(
            json.dumps(report), encoding="utf-8"
        )

        def forbidden(**_kwargs):
            raise AssertionError("indeterminate search must not be retried")

        result = self._run(forbidden)
        self.assertEqual(result["state"], "indeterminate_after_interruption")
        self.assertEqual(result["search_operation_count_contribution"], 1)
        self.assertFalse(result["search_retry_allowed"])

    def test_recovery_planner_reopens_old_not_triggered_without_repeating_spent_search(self):
        self._save_old_not_triggered()
        needed, reason = recovery.agency_discovery_upgrade_needed(
            self.artifact, self.root, DATE
        )
        self.assertTrue(needed)
        self.assertIn("agency_discovery_not_triggered_recheck", reason)
        self.assertIn(health.POST_FILTER_TRIGGER_REASON, reason)

        saved = json.loads(
            (self.artifact / "agency-discovery-rescue.json").read_text(encoding="utf-8")
        )
        saved.update(
            {
                "executed": True,
                "state": "search_started",
                "search_operation_reserved": 1,
            }
        )
        (self.artifact / "agency-discovery-rescue.json").write_text(
            json.dumps(saved), encoding="utf-8"
        )
        needed, reason = recovery.agency_discovery_upgrade_needed(
            self.artifact, self.root, DATE
        )
        self.assertFalse(needed)
        self.assertEqual(reason, "agency_discovery_indeterminate_no_retry")


if __name__ == "__main__":
    unittest.main()
