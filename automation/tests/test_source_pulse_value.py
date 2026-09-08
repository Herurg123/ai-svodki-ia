"""Evidence correctness for the offline step-5 checkpoint."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_pulse_value import build_report


class SourcePulseValueTest(unittest.TestCase):
    def fixture(self):
        return {"publication_date": "2026-09-08", "snapshot": {"sources": [
            {"source_id": "yandex", "status": "ok", "parsed_items": 30, "window_items": 2, "accepted_leads": 2}
        ]}, "promotion": {"accepted_candidate_urls": ["https://ir.yandex.ru/news?id=a"], "lead_dispositions": [
            {"source_id": "yandex", "promotion_status": "promoted", "url": "https://ir.yandex.ru/news?id=a"},
            {"source_id": "yandex", "promotion_status": "rejected", "url": "https://ir.yandex.ru/news?id=b", "reason": "old_event"}
        ]}}

    def test_stage_counts_are_not_interchangeable(self):
        row = build_report(self.fixture())["sources"][0]
        self.assertEqual((row["parsed_items"], row["accepted_leads"], row["confirmed_promoted_count"]), (30, 2, 1))
        self.assertIsNone(row["editorial_selected"])
        self.assertIsNone(row["published"])

    def test_same_host_different_article_never_counts_as_promoted(self):
        data = self.fixture()
        data["promotion"]["accepted_candidate_urls"] = ["https://ir.yandex.ru/news?id=b"]
        result = build_report(data)
        self.assertEqual(result["sources"][0]["confirmed_promoted_count"], 0)
        self.assertTrue(result["evidence_gaps"])

    def test_redirect_does_not_replace_candidate_identity(self):
        data = self.fixture()
        data["promotion"]["lead_dispositions"][0]["final_url"] = "https://ir.yandex.ru/article/a"
        self.assertEqual(build_report(data)["sources"][0]["confirmed_promoted_count"], 1)

    def test_final_url_alone_cannot_impersonate_merge_acceptance(self):
        data = self.fixture()
        data["promotion"]["lead_dispositions"][0]["final_url"] = "https://ir.yandex.ru/article/a"
        data["promotion"]["accepted_candidate_urls"] = ["https://ir.yandex.ru/article/a"]
        self.assertEqual(build_report(data)["sources"][0]["confirmed_promoted_count"], 0)

    def test_missing_promotion_remains_unknown(self):
        data = self.fixture()
        del data["promotion"]
        self.assertIsNone(build_report(data)["sources"][0]["confirmed_promoted_count"])

    def test_unavailable_is_preserved_and_not_scored(self):
        data = self.fixture()
        data["snapshot"]["sources"][0] = {"source_id": "yandex", "status": "source_unavailable"}
        row = build_report(data)["sources"][0]
        self.assertEqual(row["source_status"], "source_unavailable")
        self.assertIsNone(row["parsed_items"])
        self.assertNotIn("score", row)

    def test_input_is_not_mutated_and_duplicate_source_is_rejected(self):
        data = self.fixture()
        original = copy.deepcopy(data)
        build_report(data)
        self.assertEqual(data, original)
        data["snapshot"]["sources"] *= 2
        with self.assertRaises(ValueError):
            build_report(data)


if __name__ == "__main__":
    unittest.main()
