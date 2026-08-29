from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
FIXTURE = (
    ROOT
    / "automation"
    / "fixtures"
    / "recall"
    / "event-freshness-2026-08-29.json"
)

spec = importlib.util.spec_from_file_location(
    "event_freshness_test_module", SCRIPTS / "event_freshness.py"
)
assert spec and spec.loader
event_freshness = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = event_freshness
spec.loader.exec_module(event_freshness)

source_spec = importlib.util.spec_from_file_location(
    "source_freshness_event_test_module", SCRIPTS / "source_freshness.py"
)
assert source_spec and source_spec.loader
source_freshness = importlib.util.module_from_spec(source_spec)
sys.modules[source_spec.name] = source_freshness
source_spec.loader.exec_module(source_freshness)


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ProductionReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.start = parse(cls.fixture["search_window"]["start_at"])
        cls.end = parse(cls.fixture["search_window"]["end_at"])

    def test_saved_2026_08_29_controls(self):
        observed = {}
        for case in self.fixture["cases"]:
            result = event_freshness.evaluate_candidate(
                case, start_at=self.start, end_at=self.end
            )
            observed[case["id"]] = result.status
        expected = {
            case["id"]: case["expected_status"]
            for case in self.fixture["cases"]
        }
        self.assertEqual(observed, expected)

    def test_three_confirmed_false_positives_are_rejected(self):
        cases = {case["id"]: dict(case) for case in self.fixture["cases"]}
        for case_id in (
            "claudeforce",
            "gemini-enterprise-legal-finance",
            "glm-5-3-flash",
        ):
            case = cases[case_id]
            case["recommendation"] = "include"
            case["freshness_status"] = "new_event"
            result = event_freshness.apply_event_freshness(
                case, start_at=self.start, end_at=self.end
            )
            self.assertEqual(result.status, "stale")
            self.assertEqual(case["recommendation"], "exclude")
            self.assertEqual(
                case["event_freshness_rejection_code"],
                "event_freshness_stale",
            )

    def test_unknown_origin_preserves_recall(self):
        case = next(
            dict(case)
            for case in self.fixture["cases"]
            if case["id"] == "unknown-origin"
        )
        case["recommendation"] = "consider"
        result = event_freshness.apply_event_freshness(
            case, start_at=self.start, end_at=self.end
        )
        self.assertEqual(result.status, "unknown")
        self.assertEqual(case["recommendation"], "consider")
        self.assertIsNone(case["event_freshness_rejection_code"])

    def test_start_boundary_date_only_is_unknown_not_rejected(self):
        case = {
            "event_date": self.start.date().isoformat(),
            "event_at": None,
            "event_time_precision": "date",
            "event_origin_url": "https://example.com/official",
            "event_evidence_kind": "official_announcement",
            "event_date_evidence": "official date only",
            "recommendation": "include",
        }
        result = event_freshness.apply_event_freshness(
            case, start_at=self.start, end_at=self.end
        )
        self.assertEqual(result.status, "unknown")
        self.assertEqual(case["recommendation"], "include")

    def test_exact_start_and_neighboring_second(self):
        common = {
            "event_origin_url": "https://example.com/official",
            "event_evidence_kind": "first_party_timestamp",
            "event_date_evidence": "exact first-party timestamp",
            "event_time_precision": "datetime",
        }
        at = dict(
            common,
            event_date=self.start.date().isoformat(),
            event_at=self.start.isoformat(),
        )
        before_dt = self.start - timedelta(seconds=1)
        before = dict(
            common,
            event_date=before_dt.date().isoformat(),
            event_at=before_dt.isoformat(),
        )
        self.assertEqual(
            event_freshness.evaluate_candidate(
                at, start_at=self.start, end_at=self.end
            ).status,
            "fresh",
        )
        self.assertEqual(
            event_freshness.evaluate_candidate(
                before, start_at=self.start, end_at=self.end
            ).status,
            "stale",
        )

    def test_untrusted_old_date_cannot_force_false_negative(self):
        case = {
            "event_date": "2026-01-01",
            "event_at": None,
            "event_time_precision": "date",
            "event_origin_url": "https://example.com/random-repost",
            "event_evidence_kind": "unknown",
            "event_date_evidence": "a repost claims an old date",
            "recommendation": "consider",
        }
        result = event_freshness.apply_event_freshness(
            case, start_at=self.start, end_at=self.end
        )
        self.assertEqual(result.status, "unknown")
        self.assertEqual(case["recommendation"], "consider")

    def test_stale_event_rejects_before_source_fetch(self):
        case = next(
            dict(case)
            for case in self.fixture["cases"]
            if case["id"] == "claudeforce"
        )
        case.update(
            recommendation="include",
            freshness_status="new_event",
            primary_source={
                "title": "fresh repost",
                "publisher": "Example",
                "url": "https://example.com/fresh-repost",
            },
            supporting_sources=[],
        )
        called: list[str] = []

        def fetch(url: str):
            called.append(url)
            return (
                '<meta property="article:published_time" '
                'content="2026-08-28T12:00:00Z">',
                url,
                200,
            )

        record = source_freshness.verify_candidate(
            case, start_at=self.start, end_at=self.end, fetcher=fetch
        )
        self.assertEqual(record["status"], "excluded_event_freshness_stale")
        self.assertEqual(called, [])

    def test_unknown_event_still_runs_fail_closed_source_gate(self):
        case = {
            "title": "unknown event origin",
            "recommendation": "consider",
            "freshness_status": "new_event",
            "freshness_reason": "model could not establish event origin",
            "verification_status": "verified",
            "event_date": None,
            "event_at": None,
            "event_time_precision": "unknown",
            "event_origin_url": None,
            "event_evidence_kind": "unknown",
            "event_date_evidence": "",
            "primary_source": {
                "title": "source without date",
                "publisher": "Example",
                "url": "https://example.com/no-date",
            },
            "supporting_sources": [],
        }
        verified, report = source_freshness.verify_research_payload(
            {
                "search_window": self.fixture["search_window"],
                "candidates": [case],
            },
            fetcher=lambda url: ("<html>No publication date</html>", url, 200),
        )
        fixed = verified["candidates"][0]
        self.assertEqual(fixed["event_freshness_status"], "unknown")
        self.assertEqual(fixed["recommendation"], "exclude")
        self.assertEqual(report["excluded_unverified_freshness"], 1)
        self.assertEqual(report["excluded_event_freshness_stale"], 0)


if __name__ == "__main__":
    unittest.main()
