from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "automation" / "prompts" / "coverage_audit.md"


class CoverageQueryDisciplineTests(unittest.TestCase):
    def test_coverage_prompt_forbids_search_operator_mega_queries(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("6–18 значимых", text)
        self.assertIn("Не используй `after:`", text)
        self.assertIn("`before:`", text)
        self.assertIn("`site:`", text)
        self.assertIn("длинные `OR`-цепочки", text)
        self.assertIn("не дублируй разрешённые домены в query", text)

    def test_last_mile_uses_api_filter_instead_of_site_chain(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("general_coverage_gaps", text)
        self.assertIn("не пытайся вручную превратить весь список", text)
        self.assertIn("API сам ограничит выдачу", text)


if __name__ == "__main__":
    unittest.main()
