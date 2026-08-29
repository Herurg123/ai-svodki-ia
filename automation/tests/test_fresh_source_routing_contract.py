from __future__ import annotations

import sys
import unittest
from pathlib import Path

AUTOMATION = Path(__file__).resolve().parents[1]
SCRIPTS = AUTOMATION / "scripts"
sys.path.insert(0, str(SCRIPTS))

import hybrid_search_completeness as hybrid  # noqa: E402


class FreshSourceRoutingContractTests(unittest.TestCase):
    def test_primary_prompt_is_date_free_and_keeps_broad_safety_nets(self) -> None:
        text = (AUTOMATION / "prompts" / "primary_recall_pass.md").read_text(encoding="utf-8")
        self.assertIn("healing overlap", text)
        self.assertIn("latest", text)
        self.assertIn("календарные даты, годы, названия", text)
        self.assertIn("source-neutral broad discovery", text)
        self.assertIn("Reuters/AP/Bloomberg/FT", text)
        self.assertIn(
            "latest AI models research chips infrastructure financing earnings business deals policy security",
            text,
        )
        self.assertIn("source-neutral адаптивным last-mile", text)

    def test_coverage_prompt_is_date_free_but_window_strict(self) -> None:
        text = (AUTOMATION / "prompts" / "coverage_audit.md").read_text(encoding="utf-8")
        self.assertIn("healing overlap", text)
        self.assertIn("после retrieval", text)
        self.assertIn("`latest`, `recent`, `current`, `breaking`", text)
        self.assertIn("source-neutral запрос", text)
        self.assertIn("Reuters/AP/Bloomberg/Financial Times", text)

    def test_hybrid_time_hint_keeps_exact_window_only_for_validation(self) -> None:
        hint = hybrid._time_hint({
            "start_at": "2026-08-12T02:58:08+03:00",
            "end_at": "2026-08-14T02:58:31+03:00",
        })
        self.assertIn("2026-08-12T02:58:08+03:00", hint)
        self.assertIn("2026-08-14T02:58:31+03:00", hint)
        self.assertIn("date-free", hint)
        self.assertIn("latest / recent / current / breaking", hint)
        self.assertIn("строго проверяй", hint)


if __name__ == "__main__":
    unittest.main()
