from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "automation" / "prompts" / "primary_recall_pass.md"


class PrimaryRecallQueryDisciplineTests(unittest.TestCase):
    def test_prompt_uses_relative_freshness_without_calendar_dates_in_query(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("latest", text)
        self.assertIn("recent", text)
        self.assertIn("Не используй в поисковой строке календарные даты", text)
        self.assertIn("6–18 значимых слов", text)
        self.assertIn("relative-freshness", text)
        self.assertIn("Wikipedia/Reddit не могут", text)

    def test_broad_safety_nets_are_source_neutral(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("`global_breaking` теперь снова является **source-neutral broad discovery**", text)
        self.assertIn("`major_agencies` остаётся", text)
        self.assertIn("`bloomberg.com` + `ft.com`", text)
        self.assertIn("`independent_missing_events` становится source-neutral", text)
        self.assertIn("latest major artificial intelligence", text)


if __name__ == "__main__":
    unittest.main()
