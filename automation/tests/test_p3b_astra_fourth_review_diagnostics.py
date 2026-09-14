from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
TESTS = ROOT / "automation" / "tests"
sys.path[:0] = [str(SCRIPTS), str(TESTS)]

import ensure_story_coverage as coverage
import test_p3b_astra_second_review as second
import weak_source_exact_binding_v4 as binder


class AstraFourthReviewDiagnostics(unittest.TestCase):
    def test_claim_split_and_states(self) -> None:
        signal = second.launch_signal()
        surface = (
            "DeepSeek launched V4.1 Flash today. "
            "DeepSeek launched V4.1 Flash in 2025."
        )
        claims = binder._v3._v2._event_claims(surface)
        states = [
            binder._v3._claim_lifecycle_matches(
                claim,
                copy.deepcopy(signal),
                require_current_lifecycle=True,
            )
            for claim in claims
        ]
        strict = [binder._strict_claim_reason(claim, copy.deepcopy(signal)) for claim in claims]
        self.assertEqual(
            claims,
            [
                "DeepSeek launched V4.1 Flash today.",
                "DeepSeek launched V4.1 Flash in 2025.",
            ],
            msg=repr((claims, states, strict)),
        )
        self.assertEqual(
            states,
            [
                (True, "exact_event_identity"),
                (False, "historical_event_context"),
            ],
            msg=repr((claims, states, strict)),
        )
        self.assertEqual(strict, [None, None], msg=repr((claims, states, strict)))

        historical_controls = (
            "DeepSeek launched V4.1 Flash on September 1, 2025",
            "DeepSeek launched V4.1 Flash in 2025 and now discusses it",
            "DeepSeek launched V4.1 Flash for developers last year",
        )
        observed = []
        for text in historical_controls:
            rows = binder._v3._v2._event_claims(text)
            observed.append(
                (
                    text,
                    rows,
                    [
                        binder._v3._claim_lifecycle_matches(
                            row,
                            copy.deepcopy(signal),
                            require_current_lifecycle=True,
                        )
                        for row in rows
                    ],
                )
            )
        self.assertTrue(False, msg=repr(observed))


if __name__ == "__main__":
    unittest.main()
