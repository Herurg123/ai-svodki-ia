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


class AstraSeventhReviewRegressions(unittest.TestCase):
    def test_current_negation_cannot_be_laundered_by_cited_historical_date(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        current = _full_date(date.today())
        surfaces = (
            (
                "DeepSeek launches V4.1 Flash | "
                "Today, DeepSeek did not launch V4.1 Flash, citing reporting from "
                "September 1, 2025"
            ),
            (
                "DeepSeek launches V4.1 Flash | "
                "Today, DeepSeek did not launch V4.1 Flash, according to "
                "September 1, 2025 records"
            ),
            (
                "DeepSeek launches V4.1 Flash | "
                "Today, DeepSeek did not launch V4.1 Flash, per "
                "September 1, 2025 reporting"
            ),
            (
                "DeepSeek launches V4.1 Flash | "
                f"Today, on {current}, DeepSeek did not launch V4.1 Flash, "
                "citing reporting from September 1, 2025"
            ),
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
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                    msg=surface,
                )

    def test_current_reporting_time_does_not_make_old_launch_current(self) -> None:
        signal = second.launch_signal()
        historical = (
            "Today, DeepSeek said it launched V4.1 Flash on September 1, 2025"
        )
        self.assertEqual(
            binder.exact_event_identity(historical, copy.deepcopy(signal)),
            (False, "historical_event_context"),
        )

    def test_closing_wrappers_cannot_hide_foreign_replacement_agent(self) -> None:
        signal = copy.deepcopy(controls.SIGNAL)
        item = controls.candidate()
        bad_surfaces = (
            "DeepSeek: «V4 Pro was replaced by V4.1 Flash» by OpenAI",
            "DeepSeek: [V4 Pro was replaced by V4.1 Flash] by OpenAI",
            "DeepSeek: (V4 Pro was replaced by V4.1 Flash) by OpenAI",
            "DeepSeek: （V4 Pro was replaced by V4.1 Flash） by OpenAI",
            "DeepSeek: «[V4 Pro was replaced by V4.1 Flash]» by OpenAI",
        )

        for surface in bad_surfaces:
            with self.subTest(surface=surface):
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

        good_surface = "DeepSeek: «V4 Pro was replaced by V4.1 Flash» by DeepSeek"
        self.assertEqual(
            binder.exact_event_identity(good_surface, copy.deepcopy(signal)),
            (True, "exact_event_identity"),
        )

    def test_unreleased_evidence_marker_remains_6(self) -> None:
        self.assertEqual(binder.VERSION, 2)
        self.assertEqual(binder.EVIDENCE_VERSION, 6)


if __name__ == "__main__":
    unittest.main()
