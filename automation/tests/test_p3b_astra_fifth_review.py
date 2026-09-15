from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
TESTS = ROOT / "automation" / "tests"
sys.path[:0] = [str(SCRIPTS), str(TESTS)]

import test_p3b_astra_regressions as controls
import test_p3b_astra_second_review as second
import weak_source_exact_binding_v4 as binder


class AstraFifthReviewRegressions(unittest.TestCase):
    def test_current_cancellation_is_not_hidden_by_unrelated_past_year(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        surface = (
            "DeepSeek launches V4.1 Flash | "
            "DeepSeek V4.1 Flash launch cancelled today due to a 2025 incident"
        )

        ok, reason = binder.exact_event_identity(surface, copy.deepcopy(signal))
        self.assertFalse(ok)
        self.assertEqual(reason, "lifecycle_noncurrent")

        result = second.process_candidate(
            signal=copy.deepcopy(signal),
            candidate=copy.deepcopy(item),
            surface=surface,
        )
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["weak_source_exact_binding"]["candidate_count"], 0)
        self.assertNotEqual(
            result["weak_source_exact_binding"]["status"],
            "bound_candidate",
        )

    def test_replacement_foreign_agent_cannot_hide_in_quotes_or_curly_braces(self) -> None:
        signal = copy.deepcopy(controls.SIGNAL)
        item = controls.candidate()
        surfaces = (
            'DeepSeek says V4 Pro was replaced by V4.1 Flash {by OpenAI}',
            'DeepSeek says V4 Pro was replaced by V4.1 Flash "by OpenAI"',
            'DeepSeek says V4 Pro was replaced by V4.1 Flash ({by OpenAI})',
        )

        for surface in surfaces:
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
                self.assertNotEqual(
                    result["weak_source_exact_binding"]["status"],
                    "bound_candidate",
                    msg=surface,
                )

        for surface in (
            'DeepSeek says V4 Pro was replaced by V4.1 Flash {by DeepSeek}',
            'DeepSeek says V4 Pro was replaced by V4.1 Flash "by deepseek"',
            'DeepSeek says V4 Pro was replaced by V4.1 Flash ({by DeepSeek})',
        ):
            with self.subTest(positive_surface=surface):
                self.assertEqual(
                    binder.exact_event_identity(surface, copy.deepcopy(signal)),
                    (True, "exact_event_identity"),
                )

    def test_historical_passive_launch_does_not_veto_separate_current_claim(self) -> None:
        signal = second.launch_signal()
        item = second.launch_candidate()
        surface = (
            "DeepSeek launches V4.1 Flash | "
            "DeepSeek says V4.1 Flash was launched by OpenAI on September 1, 2025"
        )

        self.assertEqual(
            binder.exact_event_identity(surface, copy.deepcopy(signal)),
            (True, "exact_event_identity"),
        )
        result = second.process_candidate(
            signal=copy.deepcopy(signal),
            candidate=copy.deepcopy(item),
            surface=surface,
        )
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(
            result["weak_source_exact_binding"]["status"],
            "bound_candidate",
        )

        historical_only = (
            "DeepSeek says V4.1 Flash was launched by OpenAI on September 1, 2025"
        )
        self.assertEqual(
            binder.exact_event_identity(historical_only, copy.deepcopy(signal)),
            (False, "historical_event_context"),
        )
        historical_result = second.process_candidate(
            signal=copy.deepcopy(signal),
            candidate=copy.deepcopy(item),
            surface=historical_only,
        )
        self.assertEqual(historical_result["candidates"], [])
        self.assertEqual(
            historical_result["weak_source_exact_binding"]["candidate_count"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
