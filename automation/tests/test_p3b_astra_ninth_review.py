from __future__ import annotations

import copy
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
TESTS = ROOT / "automation" / "tests"
sys.path[:0] = [str(SCRIPTS), str(TESTS)]

import test_p3b_astra_regressions as controls
import test_p3b_astra_second_review as second
import weak_source_exact_binding_v4 as binder


def _full_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _previous_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


class AstraNinthReviewRegressions(unittest.TestCase):
    def test_reporting_time_predicates_do_not_promote_old_positive_event(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        current = _full_date(date.today())
        historical = _full_date(_previous_year(date.today()))
        surfaces = (
            f"On {current}, according to DeepSeek, DeepSeek launched V4.1 Flash on {historical}",
            f"On {current}, citing DeepSeek documentation, DeepSeek launched V4.1 Flash on {historical}",
            f"On {current}, based on DeepSeek documentation, DeepSeek launched V4.1 Flash on {historical}",
            f"On {current}, referencing DeepSeek documentation, DeepSeek launched V4.1 Flash on {historical}",
            f"On {current}, per DeepSeek, DeepSeek launched V4.1 Flash on {historical}",
        )

        for surface in surfaces:
            with self.subTest(surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, copy.deepcopy(signal)),
                    (False, "historical_event_context"),
                )
                result = second.process_candidate(
                    signal=copy.deepcopy(signal),
                    candidate=copy.deepcopy(item),
                    surface=surface,
                )
                self.assertEqual(result["candidates"], [], msg=surface)
                self.assertEqual(
                    result["weak_source_exact_binding"]["candidate_count"],
                    0,
                    msg=surface,
                )
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                    msg=surface,
                )

    def test_reporting_evidence_date_does_not_hide_current_negation(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        current = _full_date(date.today())
        historical = _full_date(_previous_year(date.today()))
        surfaces = (
            f"On {current}, according to {historical} report, DeepSeek did not launch V4.1 Flash",
            f"On {current}, citing documentation dated {historical}, DeepSeek did not launch V4.1 Flash",
            f"On {current}, based on reporting from {historical}, DeepSeek did not launch V4.1 Flash",
            f"On {current}, referencing records from {historical}, DeepSeek did not launch V4.1 Flash",
            f"On {current}, per {historical} report, DeepSeek did not launch V4.1 Flash",
        )

        for surface in surfaces:
            with self.subTest(surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, copy.deepcopy(signal)),
                    (False, "lifecycle_negated"),
                )
                result = second.process_candidate(
                    signal=copy.deepcopy(signal),
                    candidate=copy.deepcopy(item),
                    surface=surface,
                )
                self.assertEqual(result["candidates"], [], msg=surface)
                self.assertEqual(
                    result["weak_source_exact_binding"]["candidate_count"],
                    0,
                    msg=surface,
                )

    def test_historical_negation_does_not_veto_separate_current_positive_claim(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        current = _full_date(date.today())
        historical = _full_date(_previous_year(date.today()))
        historical_negative_claims = (
            f"On {current}, DeepSeek said it did not launch V4.1 Flash on {historical}",
            f"On {current}, DeepSeek reported it did not launch V4.1 Flash on {historical}",
            f"On {current}, according to DeepSeek, DeepSeek did not launch V4.1 Flash on {historical}",
            f"On {current}, citing DeepSeek documentation, DeepSeek did not launch V4.1 Flash on {historical}",
        )

        for historical_negative in historical_negative_claims:
            surface = f"DeepSeek launches V4.1 Flash | {historical_negative}"
            with self.subTest(surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, copy.deepcopy(signal)),
                    (True, "exact_event_identity"),
                )
                result = second.process_candidate(
                    signal=copy.deepcopy(signal),
                    candidate=copy.deepcopy(item),
                    surface=surface,
                )
                self.assertEqual(len(result["candidates"]), 1, msg=surface)
                self.assertEqual(
                    result["weak_source_exact_binding"]["candidate_count"],
                    1,
                    msg=surface,
                )
                self.assertEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                    msg=surface,
                )

    def test_semicolon_cannot_split_away_foreign_trailing_replacement_agent(self) -> None:
        signal = copy.deepcopy(controls.SIGNAL)
        item = controls.candidate()
        bad_surfaces = (
            "DeepSeek: [V4 Pro was replaced by V4.1 Flash]; by OpenAI",
            "DeepSeek: «V4 Pro was replaced by V4.1 Flash»;   by OpenAI",
            "DeepSeek: «[V4 Pro was replaced by V4.1 Flash]»; by OpenAI",
            "DeepSeek: （V4 Pro was replaced by V4.1 Flash）; by OpenAI, Anthropic",
        )

        for surface in bad_surfaces:
            with self.subTest(surface=surface):
                self.assertEqual(len(binder._v3._v2._event_claims(surface)), 2)
                self.assertEqual(len(binder._event_claims_v4(surface)), 1)
                self.assertEqual(
                    binder.exact_event_identity(surface, copy.deepcopy(signal)),
                    (False, "organization_event_attribution_mismatch"),
                )
                result = second.process_candidate(
                    signal=copy.deepcopy(signal),
                    candidate=copy.deepcopy(item),
                    surface=surface,
                )
                self.assertEqual(result["candidates"], [], msg=surface)
                self.assertEqual(
                    result["weak_source_exact_binding"]["candidate_count"],
                    0,
                    msg=surface,
                )

        good_surface = "DeepSeek: [V4 Pro was replaced by V4.1 Flash]; by DeepSeek"
        self.assertEqual(
            binder.exact_event_identity(good_surface, copy.deepcopy(signal)),
            (True, "exact_event_identity"),
        )

    def test_reporting_boundary_is_shared_and_versions_stay_compatible(self) -> None:
        for phrase in (
            "according to DeepSeek",
            "citing DeepSeek documentation",
            "based on DeepSeek documentation",
            "referencing DeepSeek documentation",
            "per DeepSeek",
            "DeepSeek said",
            "DeepSeek reported",
        ):
            self.assertTrue(binder._has_event_attribution_break(phrase), msg=phrase)
        self.assertEqual(binder.VERSION, 2)
        self.assertEqual(binder.EVIDENCE_VERSION, 6)


if __name__ == "__main__":
    unittest.main()
