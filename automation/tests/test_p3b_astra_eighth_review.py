from __future__ import annotations

import copy
import sys
import unittest
from datetime import date, timedelta
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
        # February 29 has no same-day representation in a non-leap prior year.
        return value.replace(year=value.year - 1, day=28)


class AstraEighthReviewRegressions(unittest.TestCase):
    def test_explicit_current_full_date_cannot_be_laundered_by_cited_history(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        today = date.today()
        current = _full_date(today)
        historical = _full_date(_previous_year(today))

        surfaces = (
            (
                "DeepSeek launches V4.1 Flash | "
                f"On {current}, DeepSeek did not launch V4.1 Flash, citing reporting "
                f"from {historical}"
            ),
            (
                "DeepSeek launches V4.1 Flash | "
                f"According to {historical} records, on {current}, DeepSeek did not "
                "launch V4.1 Flash"
            ),
            (
                "DeepSeek launches V4.1 Flash | "
                f"On {current}, according to {historical} report, DeepSeek did not "
                "launch V4.1 Flash"
            ),
            (
                "DeepSeek launches V4.1 Flash | "
                f"On {current}, DeepSeek did not launch V4.1 Flash, based on "
                f"reporting from {historical}"
            ),
            (
                "DeepSeek launches V4.1 Flash | "
                f"On {current}, DeepSeek did not launch V4.1 Flash, referencing "
                f"records from {historical}"
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

    def test_explicit_current_full_date_is_a_relation_marker(self) -> None:
        signal = second.launch_signal()
        today = date.today()
        historical = _previous_year(today)
        claim = (
            f"On {_full_date(today)}, DeepSeek did not launch V4.1 Flash, "
            f"citing reporting from {_full_date(historical)}"
        )
        spans = binder._signal_action_spans(claim, signal)
        self.assertEqual(len(spans), 1)
        self.assertTrue(binder._action_span_has_current_prefix_marker(claim, spans[0]))

    def test_reporting_time_control_and_real_past_full_date_stay_historical(self) -> None:
        signal = second.launch_signal()
        today = date.today()
        historical = _previous_year(today)
        reporting_control = (
            f"On {_full_date(today)}, DeepSeek said it launched V4.1 Flash on "
            f"{_full_date(historical)}"
        )
        self.assertEqual(
            binder.exact_event_identity(reporting_control, copy.deepcopy(signal)),
            (False, "historical_event_context"),
        )

        recent_past = today - timedelta(days=1)
        direct_history = f"DeepSeek launched V4.1 Flash on {_full_date(recent_past)}"
        self.assertEqual(
            binder.exact_event_identity(direct_history, copy.deepcopy(signal)),
            (False, "historical_event_context"),
        )

    def test_neutral_punctuation_cannot_hide_foreign_replacement_agent(self) -> None:
        signal = copy.deepcopy(controls.SIGNAL)
        item = controls.candidate()
        bad_surfaces = (
            "DeepSeek: [V4 Pro was replaced by V4.1 Flash] / by OpenAI",
            "DeepSeek: «V4 Pro was replaced by V4.1 Flash» • by OpenAI",
            "DeepSeek: (V4 Pro was replaced by V4.1 Flash) … by OpenAI",
            "DeepSeek: ［V4 Pro was replaced by V4.1 Flash］ = by OpenAI",
            "DeepSeek: «[V4 Pro was replaced by V4.1 Flash]» / • = by OpenAI",
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

        good_surface = "DeepSeek: [V4 Pro was replaced by V4.1 Flash] / by DeepSeek"
        self.assertEqual(
            binder.exact_event_identity(good_surface, copy.deepcopy(signal)),
            (True, "exact_event_identity"),
        )

    def test_trailing_agent_punctuation_normalizer_does_not_skip_words(self) -> None:
        self.assertIsNone(
            binder._TRAILING_REPLACEMENT_AGENT_RE.match(
                "] attribution according to notes by OpenAI"
            )
        )

    def test_unreleased_evidence_marker_remains_6(self) -> None:
        self.assertEqual(binder.VERSION, 2)
        self.assertEqual(binder.EVIDENCE_VERSION, 6)


if __name__ == "__main__":
    unittest.main()
