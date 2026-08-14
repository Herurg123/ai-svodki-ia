from __future__ import annotations

import sys
import unittest
from pathlib import Path

AUTOMATION = Path(__file__).resolve().parents[1]
SCRIPTS = AUTOMATION / "scripts"
sys.path.insert(0, str(SCRIPTS))

import hybrid_search_completeness as hybrid  # noqa: E402


class FreshSourceRoutingContractTests(unittest.TestCase):
    def test_primary_prompt_uses_continuity_first_and_diverse_high_signal_roles(self) -> None:
        text = (AUTOMATION / "prompts" / "primary_recall_pass.md").read_text(encoding="utf-8")

        self.assertIn("healing overlap", text)
        self.assertIn("начинается ровно через 24 часа", text)
        self.assertIn("Reuters-focused query", text)
        self.assertIn("direction_id=major_agencies", text)
        self.assertIn("не якори query на Reuters", text)
        self.assertIn("Reuters, Associated Press,\n  Bloomberg и Financial Times", text)
        self.assertIn("Associated Press-focused sweep", text)

    def test_coverage_prompt_prioritizes_continuity_period_not_healing_overlap(self) -> None:
        text = (AUTOMATION / "prompts" / "coverage_audit.md").read_text(encoding="utf-8")

        self.assertIn("Первые 24 часа effective window являются healing overlap", text)
        self.assertIn("основного continuity-периода", text)
        self.assertIn("source-neutral запрос", text)
        self.assertIn("Reuters/AP/Bloomberg/Financial Times", text)

    def test_hybrid_time_hint_shifts_query_start_by_exactly_24_hours(self) -> None:
        hint = hybrid._time_hint(
            {
                "start_at": "2026-08-12T02:58:08+03:00",
                "end_at": "2026-08-14T02:58:31+03:00",
            }
        )

        self.assertIn("2026-08-13T02:58:08+03:00", hint)
        self.assertIn("2026-08-14T02:58:31+03:00", hint)
        self.assertIn("2026-08-13 и 2026-08-14", hint)
        self.assertNotIn("2026-08-12 и 2026-08-14", hint)

    def test_hybrid_time_hint_preserves_long_continuity_window_after_overlap(self) -> None:
        hint = hybrid._time_hint(
            {
                "start_at": "2026-08-10T02:00:00+03:00",
                "end_at": "2026-08-14T02:00:00+03:00",
            }
        )

        self.assertIn("2026-08-11T02:00:00+03:00", hint)
        self.assertIn("2026-08-14T02:00:00+03:00", hint)


if __name__ == "__main__":
    unittest.main()
