"""Period totals must survive copies, missing stages and conflicting recovery."""
import copy
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_pulse_value import build_report
from source_value_period import aggregate
from test_source_value_integrity import evidence


class SourceValuePeriodTests(unittest.TestCase):
    def report(self, day="2026-09-08"):
        return build_report(*evidence(day))

    def totals(self, result, metric):
        return result["sources"][0]["metrics"][metric]

    def test_exact_and_recovery_copies_count_once(self):
        pulse, bundle = evidence()
        first = build_report(pulse, bundle)
        pulse["reused_snapshot"] = True
        recovered = build_report(pulse, bundle)
        result = aggregate([first, copy.deepcopy(first), recovered])
        self.assertEqual(result["exact_duplicate_reports_ignored"], 1)
        self.assertEqual(result["release_count"], 1)
        self.assertEqual(self.totals(result, "editorial_selected")["complete_total"], 1)

    def test_unknown_is_never_an_observed_zero(self):
        report = build_report(evidence()[0])
        result = aggregate([report])
        self.assertEqual(self.totals(result, "editorial_selected"), {
            "observed_total": None, "observed_releases": 0, "unknown_releases": 1, "complete_total": None,
        })

    def test_mixed_release_totals_report_known_and_unknown_denominators(self):
        known = self.report("2026-09-06")
        unknown = build_report(evidence("2026-09-08")[0])
        result = aggregate([known, unknown])
        self.assertEqual(self.totals(result, "editorial_selected"), {
            "observed_total": 1, "observed_releases": 1, "unknown_releases": 1, "complete_total": None,
        })
        self.assertEqual(self.totals(result, "confirmed_promoted_count")["complete_total"], 2)

    def test_different_snapshots_on_one_day_are_not_summed_or_chosen(self):
        first = self.report()
        pulse, bundle = evidence()
        pulse["snapshot"]["sources"][0]["parsed_items"] += 1
        second = build_report(pulse, bundle)
        for reports in itertools.permutations([first, second]):
            result = aggregate(list(reports))
            self.assertIsNone(self.totals(result, "confirmed_promoted_count")["observed_total"])

    def test_same_snapshot_different_editorials_keep_early_counts_only(self):
        pulse, bundle = evidence()
        first = build_report(pulse, bundle)
        bundle["editorial"].update(selected_candidate_ids=[], excluded_candidate_ids=["cand-001"])
        bundle["stories"] = []
        second = build_report(pulse, bundle)
        result = aggregate([first, second])
        self.assertEqual(self.totals(result, "confirmed_promoted_count")["complete_total"], 1)
        self.assertIsNone(self.totals(result, "editorial_selected")["observed_total"])

    def test_conflicting_number_and_null_cannot_be_silently_coalesced(self):
        first = self.report()
        second = copy.deepcopy(first)
        second["sources"][0]["confirmed_promoted_count"] = None
        result = aggregate([first, second])
        self.assertIsNone(self.totals(result, "confirmed_promoted_count")["observed_total"])

    def test_a_publication_label_alone_cannot_promote_a_draft(self):
        report = self.report()
        report["repository_publication_evidence"] = {"scope": "repository_publication_on_origin_main"}
        report["sources"][0]["repository_published"] = 1
        result = aggregate([report])
        self.assertIsNone(self.totals(result, "repository_published")["observed_total"])
        self.assertIn("repository_publication_proof_invalid", result["days"][0]["evidence_gaps"])

    def test_missing_source_on_another_date_remains_unknown(self):
        first = self.report("2026-09-06")
        pulse, bundle = evidence("2026-09-08")
        pulse["snapshot"]["sources"][0]["source_id"] = "other"
        pulse["promotion"]["lead_dispositions"][0]["source_id"] = "other"
        result = aggregate([first, build_report(pulse, bundle)])
        vendor = next(s for s in result["sources"] if s["source_id"] == "vendor")
        self.assertEqual(vendor["metrics"]["confirmed_promoted_count"]["unknown_releases"], 1)
        self.assertIsNone(vendor["metrics"]["confirmed_promoted_count"]["complete_total"])

    def test_old_reports_and_empty_input_require_explicit_regeneration(self):
        for reports in ([], [{"version": 2}]):
            with self.subTest(reports=reports), self.assertRaises(ValueError):
                aggregate(reports)


if __name__ == "__main__":
    unittest.main()
