"""Regression: 2026-11-02 verified OpenAI Chat/Work story rejected by fake precision.

Uses the exact effective-window dates and the candidate's temporal field
combination from GitHub Actions run 41375795360. No network or paid API calls.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "scripts" / "story_coverage.py"
SPEC = importlib.util.spec_from_file_location("story_coverage_nov02_recovery", PATH)
assert SPEC and SPEC.loader
coverage = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = coverage
SPEC.loader.exec_module(coverage)

WINDOW = {
    "start_at": "2026-10-31T05:06:28+03:00",
    "end_at": "2026-11-02T05:06:26+03:00",
    "start_date": "2026-10-31",
    "end_date": "2026-11-02",
}


def chat_work_candidate():
    return {
        "title": "OpenAI готовит объединение Chat и Work в ChatGPT",
        "organization": "OpenAI",
        "published_date": "2026-11-01",
        "published_at": None,
        "time_precision": "datetime",  # Actual contradictory model payload.
        "topic": "ChatGPT Work integration",
        "event_type": "reported product change",
        "keywords": ["ChatGPT", "Work", "OpenAI"],
        "geography": "world",
        "category": "agents",
        "source_type": "industry_media",
        "primary_source": {
            "title": "OpenAI says it's doubling Pro usage limits and bringing Work features to Chat",
            "publisher": "BleepingComputer",
            "url": "https://www.bleepingcomputer.com/news/artificial-intelligence/openai-says-its-doubling-pro-usage-limits-and-bringing-work-features-to-chat/",
        },
        "supporting_sources": [],
        "event_summary": (
            "По письму OpenAI, которое видело BleepingComputer, в ближайшие недели "
            "пройдёт небольшой тест объединённых Chat и Work, но общего релиза ещё нет."
        ),
        "verified_facts": [
            "Статья BleepingComputer опубликована 1 ноября 2026 года.",
            "Объединение Chat и Work только готовится к тесту на небольшой группе.",
        ],
        "significance": "Переход от переписки к выполнению задач без смены интерфейса.",
        "significance_score": 2,
        "limitations": "Публичного самостоятельного релиза OpenAI пока нет.",
        "archive_status": "none",
        "archive_reason": "Сюжет не опубликован в предыдущей сводке.",
        "recommendation": "consider",
        "verification_status": "verified",
        "verification_notes": "BleepingComputer описало письмо подписчикам OpenAI.",
        "freshness_status": "new_event",
        "freshness_reason": "Первое сообщение о предстоящем ограниченном тесте.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
        "event_date": "2026-11-01",
        "event_at": None,
        "event_time_precision": "date",
        "event_origin_url": "https://www.bleepingcomputer.com/news/artificial-intelligence/openai-says-its-doubling-pro-usage-limits-and-bringing-work-features-to-chat/",
        "event_evidence_kind": "authoritative_secondary",
        "event_date_evidence": "Отчёт издания от 1 ноября с описанием письма OpenAI.",
        "audit_direction": "general_coverage_gaps",
    }


class November2EditorialRecoveryTests(unittest.TestCase):
    def test_saved_work_story_is_accepted_without_inventing_publication_time(self):
        original = chat_work_candidate()
        research = {"candidates": [], "search_window": WINDOW, "research_notes": ""}
        merged, accepted, rejected = coverage.merge_candidates(research, [original])
        self.assertEqual(rejected, [])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(merged["candidates"][0]["id"], "cand-001")
        self.assertEqual(accepted[0]["time_precision"], "date")
        self.assertIsNone(accepted[0]["published_at"])
        self.assertEqual(accepted[0]["event_date"], "2026-11-01")
        self.assertIn("не придуман", accepted[0]["verification_notes"])
        self.assertEqual(original["time_precision"], "datetime", "source evidence immutable")

    def test_start_and_end_boundary_days_stay_fail_closed(self):
        for day in ("2026-10-31", "2026-11-02"):
            with self.subTest(day=day):
                candidate = chat_work_candidate()
                candidate["published_date"] = day
                candidate["event_date"] = day
                errors = coverage.validate_audit_candidate(candidate, WINDOW)
                self.assertIn("кандидат находится вне редакционного окна", errors)
                self.assertEqual(candidate["time_precision"], "datetime")

    def test_unverified_or_wrong_event_day_never_gets_recovered(self):
        for field, value in (
            ("verification_status", "unconfirmed"),
            ("event_date", "2026-10-30"),
            ("event_evidence_kind", "unspecified"),
            ("event_date_evidence", ""),
            ("event_at", "2026-11-01T15:00:00+03:00"),
        ):
            with self.subTest(field=field):
                candidate = chat_work_candidate()
                candidate[field] = value
                errors = coverage.validate_audit_candidate(candidate, WINDOW)
                self.assertIn("кандидат находится вне редакционного окна", errors)
                self.assertEqual(candidate["time_precision"], "datetime")

    def test_real_datetime_stays_exact_and_not_downgraded(self):
        candidate = chat_work_candidate()
        candidate["published_at"] = "2026-11-01T13:53:00+00:00"
        notes = candidate["verification_notes"]
        self.assertEqual(coverage.validate_audit_candidate(candidate, WINDOW), [])
        self.assertEqual(candidate["time_precision"], "datetime")
        self.assertEqual(candidate["verification_notes"], notes)

    def test_no_time_data_does_not_create_a_fictitious_timestamp(self):
        candidate = chat_work_candidate()
        self.assertTrue(coverage.recover_verified_date_only_precision(candidate, WINDOW))
        self.assertIsNone(candidate["published_at"])
        self.assertIsNone(candidate["event_at"])


if __name__ == "__main__":
    unittest.main()
