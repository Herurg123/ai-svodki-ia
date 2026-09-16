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


class AstraTenthReviewRegressions(unittest.TestCase):
    def test_underscore_cannot_hide_foreign_trailing_replacement_agent(self) -> None:
        signal = copy.deepcopy(controls.SIGNAL)
        item = controls.candidate()
        bad_surfaces = (
            "DeepSeek: [V4 Pro was replaced by V4.1 Flash] _ by OpenAI",
            "DeepSeek: [V4 Pro was replaced by V4.1 Flash]_by OpenAI",
            "DeepSeek: «V4 Pro was replaced by V4.1 Flash»_by OpenAI",
            "DeepSeek: （[V4 Pro was replaced by V4.1 Flash]） __ by OpenAI, Anthropic",
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

        for surface in (
            "DeepSeek: [V4 Pro was replaced by V4.1 Flash] _ by DeepSeek",
            "DeepSeek: [V4 Pro was replaced by V4.1 Flash]_by DeepSeek",
        ):
            with self.subTest(surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, copy.deepcopy(signal)),
                    (True, "exact_event_identity"),
                )

    def test_underscore_matcher_still_cannot_jump_substantive_words(self) -> None:
        self.assertIsNone(
            binder._TRAILING_REPLACEMENT_AGENT_RE.match(" note_by OpenAI")
        )
        self.assertIsNone(
            binder._TRAILING_REPLACEMENT_AGENT_RE.match(" attribution _ by OpenAI")
        )

    def test_future_event_date_is_noncurrent_not_current_proof(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        future = _full_date(date.today() + timedelta(days=1))
        surfaces = (
            f"On {future}, DeepSeek launches V4.1 Flash",
            f"DeepSeek launches V4.1 Flash on {future}",
        )

        for surface in surfaces:
            with self.subTest(surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, copy.deepcopy(signal)),
                    (False, "lifecycle_noncurrent"),
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

    def test_future_negation_is_noncurrent_not_current_veto(self) -> None:
        signal = second.launch_signal()
        future = _full_date(date.today() + timedelta(days=1))
        surface = f"On {future}, DeepSeek did not launch V4.1 Flash"
        self.assertEqual(
            binder.exact_event_identity(surface, copy.deepcopy(signal)),
            (False, "lifecycle_noncurrent"),
        )

    def test_future_reporting_date_does_not_promote_old_event(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        future = _full_date(date.today() + timedelta(days=1))
        historical = _full_date(date.today() - timedelta(days=1))
        surface = (
            f"On {future}, according to DeepSeek, "
            f"DeepSeek launched V4.1 Flash on {historical}"
        )
        self.assertEqual(
            binder.exact_event_identity(surface, copy.deepcopy(signal)),
            (False, "historical_event_context"),
        )
        result = second.process_candidate(
            signal=copy.deepcopy(signal),
            candidate=copy.deepcopy(item),
            surface=surface,
        )
        self.assertEqual(result["candidates"], [])
        self.assertEqual(
            result["weak_source_exact_binding"]["candidate_count"],
            0,
        )

    def test_today_yesterday_and_invalid_date_boundaries(self) -> None:
        signal = second.launch_signal()
        today = _full_date(date.today())
        yesterday = _full_date(date.today() - timedelta(days=1))

        self.assertEqual(
            binder.exact_event_identity(
                f"On {today}, DeepSeek launches V4.1 Flash",
                copy.deepcopy(signal),
            ),
            (True, "exact_event_identity"),
        )
        self.assertEqual(
            binder.exact_event_identity(
                f"On {yesterday}, DeepSeek launches V4.1 Flash",
                copy.deepcopy(signal),
            ),
            (False, "historical_event_context"),
        )

        invalid = "On February 30, 2026, DeepSeek launches V4.1 Flash"
        span = binder._signal_action_spans(invalid, signal)[0]
        self.assertFalse(binder._action_span_has_nonpast_full_date_prefix(invalid, span))
        self.assertFalse(binder._action_span_has_future_full_date(invalid, span))

    def test_versions_remain_compatible(self) -> None:
        self.assertEqual(binder.VERSION, 2)
        self.assertEqual(binder.EVIDENCE_VERSION, 6)


if __name__ == "__main__":
    unittest.main()
