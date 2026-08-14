from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "automation" / "prompts" / "coverage_audit.md"


class CoverageQueryDisciplineTests(unittest.TestCase):
    def test_coverage_prompt_uses_relative_freshness_and_forbids_date_terms(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("6–18 значимых", text)
        self.assertIn("`latest`, `recent`, `current`, `breaking`", text)
        self.assertIn("Не используй календарные даты, годы, названия", text)
        self.assertIn("`after:`", text)
        self.assertIn("`before:`", text)
        self.assertIn("`site:`", text)
        self.assertIn("`OR`-цепочки", text)

    def test_last_mile_uses_relative_source_neutral_query(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("general_coverage_gaps", text)
        self.assertIn("latest major AI news products business", text)
        self.assertIn("API сам ограничит выдачу", text)


if __name__ == "__main__":
    unittest.main()
