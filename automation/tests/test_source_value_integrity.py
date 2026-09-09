"""Damaged evidence must not turn into zero contribution or publication proof."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_pulse_value import build_report
from source_value_publication import verify_page


def evidence(day="2026-09-08"):
    url = "https://vendor.example/news?id=one"
    pulse = {"publication_date": day, "snapshot": {"sources": [{
        "source_id": "vendor", "status": "ok", "parsed_items": 5, "window_items": 1, "accepted_leads": 1,
    }]}, "promotion": {"accepted_candidate_urls": [url], "lead_dispositions": [{
        "source_id": "vendor", "url": url, "title": "One release", "promotion_status": "promoted",
    }]}}
    identity = {"organization": "Vendor", "topic": "One", "event_type": "release", "published_date": day, "published_at": None}
    candidate = {**identity, "id": "cand-001", "title": "One release", "audit_direction": "source_pulse_v12",
                 "primary_source": {"url": url}, "source_freshness_status": "fresh",
                 "event_freshness_status": "unknown", "recommendation": "consider"}
    story = {**identity, "candidate_id": "cand-001", "headline": "One release", "sources": [{"url": url}]}
    bundle = {"candidates": {"publication_date": day, "candidates": [candidate]},
              "editorial": {"status": "ok", "digest": {"date": day}, "selected_candidate_ids": ["cand-001"], "excluded_candidate_ids": []},
              "stories": [story]}
    return pulse, bundle


class EvidenceIntegrityTests(unittest.TestCase):
    def test_malformed_rows_and_duplicates_are_unknown_at_every_later_stage(self):
        for damage in ("non_object", "duplicate_disposition", "duplicate_accepted", "missing_status", "object_status", "orphan_accepted", "missing_decision"):
            with self.subTest(damage=damage):
                pulse, bundle = evidence()
                promotion = pulse["promotion"]
                if damage == "non_object": promotion["lead_dispositions"] = ["broken"]
                elif damage == "duplicate_disposition": promotion["lead_dispositions"] *= 2
                elif damage == "duplicate_accepted": promotion["accepted_candidate_urls"] *= 2
                elif damage == "missing_status": promotion["lead_dispositions"][0].pop("promotion_status")
                elif damage == "object_status": promotion["lead_dispositions"][0]["promotion_status"] = {}
                elif damage == "orphan_accepted": promotion["accepted_candidate_urls"].append("https://vendor.example/other")
                else: promotion["lead_dispositions"] = []; promotion["accepted_candidate_urls"] = []
                report = build_report(pulse, bundle)
                row = report["sources"][0]
                self.assertFalse(row["promotion_evidence_complete"])
                for key in ("confirmed_promoted_count", "post_freshness_survivors", "editorial_selected", "assembled_stories"):
                    self.assertIsNone(row[key], key)
                self.assertTrue(report["evidence_gaps"])

    def test_null_blank_or_invalid_event_identity_cannot_prove_selection(self):
        for field, value in (("organization", None), ("topic", " "), ("event_type", []),
                             ("published_date", "2026-02-30"), ("published_at", "2026-09-08T10:00:00")):
            with self.subTest(field=field):
                pulse, bundle = evidence()
                bundle["candidates"]["candidates"][0][field] = value
                bundle["stories"][0][field] = value
                row = build_report(pulse, bundle)["sources"][0]
                self.assertIsNone(row["editorial_selected"])
                self.assertIsNone(row["assembled_stories"])

    def test_explicit_date_only_identity_still_works(self):
        pulse, bundle = evidence()
        self.assertEqual(build_report(pulse, bundle)["sources"][0]["editorial_selected"], 1)

    def test_unavailable_collector_zero_is_not_observed_source_zero(self):
        pulse, _ = evidence()
        source = pulse["snapshot"]["sources"][0]
        source.update(status="source_unavailable", parsed_items=0, window_items=0, accepted_leads=0)
        pulse["promotion"] = {"lead_dispositions": [], "accepted_candidate_urls": []}
        row = build_report(pulse)["sources"][0]
        self.assertIsNone(row["parsed_items"])
        self.assertEqual(row["reported_counts"]["parsed_items"], 0)
        self.assertEqual(row["confirmed_promoted_count"], 0)  # Actual pool contribution is known.

    def test_hidden_or_neighboring_links_cannot_confirm_a_story(self):
        stories = [{"headline": "Story A", "sources": [{"url": "https://source.example/A"}]},
                   {"headline": "Story B", "sources": [{"url": "https://source.example/B"}]}]
        correct = '<h3>Story A</h3><a href="https://source.example/A">A</a><h3>Story B</h3><a href="https://source.example/B">B</a>'
        verify_page(correct.encode(), stories)
        bad_pages = [
            correct.replace('example/A', 'example/temp').replace('example/B', 'example/A').replace('example/temp', 'example/B'),
            correct.replace('<a href="https://source.example/A">', '<a hidden href="https://source.example/A">'),
            correct.replace('<a href="https://source.example/A">', '<a style="display: none" href="https://source.example/A">'),
            '<h3>Story A</h3><h3>Story B</h3><a href="https://source.example/B">B</a><footer><a href="https://source.example/A">A</a></footer>',
            correct.replace('Story A', 'Different story'),
        ]
        for page in bad_pages:
            with self.subTest(page=page), self.assertRaises(ValueError):
                verify_page(page.encode(), stories)

    def test_meta_marker_is_narrow_and_all_sources_belong_to_the_block(self):
        story = {"headline": "Meta release", "sources": [{"url": "https://source.example/A"}]}
        verify_page(b'<h3>Meta* release</h3><a href="https://source.example/A">A</a>', [story])
        for headline in ("Meta** release", "SomeMeta* release"):
            with self.subTest(headline=headline), self.assertRaises(ValueError):
                verify_page(f'<h3>{headline}</h3><a href="https://source.example/A">A</a>'.encode(), [story])
        story["sources"].append({"url": "https://source.example/B"})
        with self.assertRaises(ValueError):
            verify_page(b'<h3>Meta* release</h3><a href="https://source.example/A">A</a>', [story])

    def test_source_observation_identity_ignores_copy_metadata_only(self):
        pulse, bundle = evidence()
        first = build_report(pulse, bundle)
        original = copy.deepcopy(pulse)
        pulse["reused_snapshot"] = True
        pulse["fusion_post_hybrid"] = {"later": True}
        second = build_report(pulse, bundle)
        self.assertEqual(first["source_observation_id"], second["source_observation_id"])
        self.assertEqual(first["trace_observation_id"], second["trace_observation_id"])
        pulse["snapshot"]["sources"][0]["parsed_items"] += 1
        self.assertNotEqual(first["source_observation_id"], build_report(pulse, bundle)["source_observation_id"])
        self.assertEqual(build_report(original, bundle)["source_observation_id"], first["source_observation_id"])


if __name__ == "__main__":
    unittest.main()
