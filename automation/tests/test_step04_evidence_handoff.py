"""Offline development checks; not a live Terra acceptance experiment."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import primary_recall_search as primary
import ensure_story_coverage as coverage
from ensure_story_coverage_policy import AUDIT_REJECTION_SCHEMA

WINDOW = {"start_at": "2026-09-03T03:58:49+03:00", "end_at": "2026-09-05T03:57:22+03:00"}


def rejection(code="unverified", timestamp="2026-09-04T09:21:00-07:00"):
    return {"title": "Nvidia OpenAI $3 billion investment", "reason_code": code,
            "reason": "Reuters investment report; facts still disputed; HTTP 403",
            "url": "https://example.org/original", "published_at": timestamp,
            "published_date": "2026-09-04", "time_precision": "datetime",
            "date_evidence": "Visible timestamp: Sep 4, 09:21 PDT"}


def reports(row):
    return [{"direction_id": "business", "model_rejections": [row]}]


class EvidenceHandoffTests(unittest.TestCase):
    def test_url_and_evidence_survive_without_mutation(self):
        row = rejection()
        before = copy.deepcopy(row)
        signal = primary.collect_unresolved_signals(reports(row), WINDOW)[0]
        self.assertEqual(signal["rejection_evidence"], before)
        self.assertEqual(signal["url"], row["url"])
        signal["rejection_evidence"]["url"] = "changed"
        self.assertEqual(row, before)

    def test_inside_outside_unknown_pairwise(self):
        for code in ("unverified", "outside_window"):
            for timestamp, status in (("2026-09-04T09:21:00-07:00", "inside"),
                                      ("2026-09-06T09:21:00-07:00", "outside"),
                                      (None, "unknown"), ("invalid", "unknown"),
                                      ("2026-09-04T09:21:00", "unknown")):
                with self.subTest(code=code, timestamp=timestamp):
                    signal = primary.collect_unresolved_signals(reports(rejection(code, timestamp)), WINDOW)[0]
                    self.assertEqual(signal["source_window_status"], status)
                    self.assertEqual(signal["resolution_required"], not (code == "outside_window" and status == "outside"))
                    self.assertNotIn("recommendation", signal)

    def test_date_only_never_becomes_exact(self):
        row = rejection("outside_window")
        row["time_precision"] = "date"
        signal = primary.collect_unresolved_signals(reports(row), WINDOW)[0]
        self.assertEqual(signal["source_window_status"], "unknown")

    def test_weak_signal_does_not_require_slot(self):
        row = {"title": "Tiny app", "reason": "unconfirmed", "reason_code": "outside_window"}
        self.assertFalse(primary.collect_unresolved_signals(reports(row), WINDOW)[0]["resolution_required"])

    def test_other_rejections_stay_excluded(self):
        for code in ("duplicate", "old_reprint", "not_ai_news", "insufficient_significance"):
            self.assertEqual(primary.collect_unresolved_signals(reports(rejection(code)), WINDOW), [])

    def test_prompt_carries_raw_proof_and_original_reason(self):
        row = rejection("outside_window")
        signal = primary.collect_unresolved_signals(reports(row), WINDOW)[0]
        prompt = coverage.build_resolution_prompt(search_window=WINDOW, cluster=[signal], archive={})
        for evidence in (row["url"], row["published_at"], row["date_evidence"], row["reason"]):
            self.assertIn(evidence, prompt)
        self.assertIn("Не делай второй Web Search", prompt)

    def test_legacy_rows_load_without_new_fields(self):
        row = {"title": "Nvidia OpenAI investment", "reason": "Reuters unverified investment", "reason_code": "unverified"}
        signal = primary.collect_unresolved_signals(reports(row))[0]
        self.assertIsNone(signal["url"])
        self.assertEqual(signal["rejection_evidence"], row)

    def test_nullable_strict_schema(self):
        props = AUDIT_REJECTION_SCHEMA["properties"]
        self.assertEqual(set(props), set(AUDIT_REJECTION_SCHEMA["required"]))
        for key in ("published_at", "published_date", "date_evidence", "time_precision"):
            self.assertIn("null", props[key]["type"])

    def test_historical_instants_preserved_not_promoted(self):
        fixture = json.loads((Path(__file__).resolve().parents[1] / "fixtures/recall/primary-temporal-boundary-2026-09-05.json").read_text())
        for case in fixture["observed_model_timezone_errors"]:
            row = rejection("outside_window", case["source_timestamp"])
            row["title"] = case["title"]
            row["reason"] = "Saved model outside_window; facts and significance remain disputed"
            signal = primary.collect_unresolved_signals(reports(row), WINDOW)[0]
            self.assertEqual(signal["source_window_status"], "inside")
            self.assertEqual(signal["rejection_evidence"]["published_at"], case["source_timestamp"])
            self.assertNotIn("recommendation", signal)

    def test_used_adaptive_slot_is_never_repaid(self):
        signals = primary.collect_unresolved_signals(reports(rejection()), WINDOW)
        prior = {"attempts": [{"search_strategy": coverage.AGENCY_RESCUE_STRATEGY, "api": {"web_search_calls_completed": 1}}],
                 "checked_directions": list(coverage.AUDIT_DIRECTION_IDS),
                 "search_budget": {"maximum_calls": 7, "completed_calls": 7, "remaining_calls": 0}}
        with patch.object(coverage, "_required_signals", return_value=signals), patch.object(coverage, "_V8_EXECUTE", side_effect=AssertionError("paid replay")):
            result = coverage.execute_audit_plan(api_key="unused", model="unused", template="", publication_date="2026-09-05", search_window=WINDOW,
                missing_total=1, maximum_web_search_calls=7, existing_candidates=[], archive={}, prior_plan=prior)
        self.assertEqual(result["attempts"], prior["attempts"])
        self.assertEqual(result["search_budget"], prior["search_budget"])
        self.assertEqual(result["audit_status"], "partial")


if __name__ == "__main__":
    unittest.main()
