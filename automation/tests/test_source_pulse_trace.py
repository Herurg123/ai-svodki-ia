import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_pulse_value import build_report


class SourcePulseTraceTests(unittest.TestCase):
    def fixture(self):
        date = "2026-09-08"
        url = "https://vendor.example/news?id=one"
        pulse = {"publication_date": date, "snapshot": {"sources": [{"source_id": "vendor"}]}, "promotion": {
            "accepted_candidate_urls": [url], "lead_dispositions": [{"source_id": "vendor", "url": url, "title": "One release", "promotion_status": "promoted"}]}}
        candidate = {"id": "cand-001", "title": "One release", "audit_direction": "source_pulse_v12", "primary_source": {"url": url},
                     "organization": "Vendor", "topic": "One", "event_type": "release", "published_date": date, "published_at": None,
                     "source_freshness_status": "fresh", "event_freshness_status": "unknown", "recommendation": "consider", "verification_status": "verified"}
        story = {k: candidate[k] for k in ["organization", "topic", "event_type", "published_date", "published_at"]}
        story.update(candidate_id="cand-001", sources=[{"url": url}])
        bundle = {"candidates": {"publication_date": date, "candidates": [candidate]},
                  "editorial": {"status": "ok", "digest": {"date": date}, "selected_candidate_ids": ["cand-001"], "excluded_candidate_ids": []}, "stories": [story]}
        return pulse, bundle

    def test_selected_and_assembled_is_not_published(self):
        p, b = self.fixture()
        before = copy.deepcopy((p, b))
        row = build_report(p, b)["sources"][0]
        self.assertEqual((row["post_freshness_survivors"], row["editorial_selected"], row["assembled_stories"]), (1, 1, 1))
        self.assertIsNone(row["published"])
        self.assertEqual((p, b), before)

    def test_excluded_candidate_is_not_lost_from_trace(self):
        p, b = self.fixture()
        b["editorial"].update(selected_candidate_ids=[], excluded_candidate_ids=["cand-001"])
        b["stories"] = []
        b["candidates"]["candidates"][0]["recommendation"] = "exclude"
        row = build_report(p, b)["sources"][0]
        self.assertEqual(row["editorial_selected"], 0)
        self.assertEqual(row["candidate_trace"][0]["recommendation"], "exclude")

    def test_reused_id_with_other_event_is_unknown(self):
        p, b = self.fixture()
        b["stories"][0]["topic"] = "Different release"
        result = build_report(p, b)
        self.assertIsNone(result["sources"][0]["editorial_selected"])
        self.assertIn("selected_story_identity_conflict", result["evidence_gaps"])

    def test_same_url_different_pulse_title_is_unknown(self):
        p, b = self.fixture()
        b["candidates"]["candidates"][0]["title"] = "Different release"
        self.assertIsNone(build_report(p, b)["sources"][0]["editorial_selected"])

    def test_duplicate_candidate_and_different_date_are_unknown(self):
        for variant in ("duplicate", "date"):
            with self.subTest(variant=variant):
                p, b = self.fixture()
                if variant == "duplicate": b["candidates"]["candidates"] *= 2
                else: b["candidates"]["publication_date"] = "2026-09-07"
                self.assertIsNone(build_report(p, b)["sources"][0]["editorial_selected"])

    def test_incomplete_partition_and_missing_story_remain_unknown(self):
        for variant in ("partition", "story"):
            with self.subTest(variant=variant):
                p, b = self.fixture()
                if variant == "partition": b["editorial"]["excluded_candidate_ids"] = ["foreign-id"]
                else: b.pop("stories")
                self.assertIsNone(build_report(p, b)["sources"][0]["editorial_selected"])

    def test_unknown_promotion_cannot_become_downstream_zero(self):
        p, b = self.fixture()
        p["promotion"]["accepted_candidate_urls"] = []
        row = build_report(p, b)["sources"][0]
        self.assertIsNone(row["post_freshness_survivors"])
        self.assertIsNone(row["editorial_selected"])

    def test_saved_positive_and_excluded_releases(self):
        fixture = json.loads((ROOT / "fixtures/recall/source-value-trace-2026-09.json").read_text())
        for case in fixture["cases"]:
            with self.subTest(date=case["date"]):
                result = build_report(case["pulse"], case["bundle"])
                self.assertEqual(next(r for r in result["sources"] if r["source_id"] == case["source_id"])["editorial_selected"], case["expected_editorial_selected"])


if __name__ == "__main__":
    unittest.main()
