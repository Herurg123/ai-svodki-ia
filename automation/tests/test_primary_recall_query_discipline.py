from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "automation" / "prompts" / "primary_recall_pass.md"


class PrimaryRecallQueryDisciplineTests(unittest.TestCase):
    def test_prompt_forbids_boolean_mega_queries(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("Не используй в поисковой строке `after:`, `before:`", text)
        self.assertIn("длинные\nцепочки `OR`", text)
        self.assertIn("6–18 значимых слов", text)
        self.assertIn("Wikipedia/Reddit не могут", text)
        self.assertIn("API domain filter уже ограничивает выдачу Reuters/AP/Bloomberg/FT", text)


if __name__ == "__main__":
    unittest.main()
