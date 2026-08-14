from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "automation" / "prompts" / "primary_recall_pass.md"


class PrimaryRecallQueryDisciplineTests(unittest.TestCase):
    def test_prompt_forbids_boolean_mega_queries(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("Не используй в поисковой строке `after:`, `before:`", text)
        self.assertIn("длинные цепочки `OR`", text)
        self.assertIn("`site:`", text)
        self.assertIn("6–18 значимых слов", text)
        self.assertIn("Wikipedia/Reddit не могут", text)

    def test_broad_passes_have_distinct_source_focused_recipes(self):
        text = PROMPT.read_text(encoding="utf-8")
        self.assertIn("direction_id=global_breaking", text)
        self.assertIn("API filter ограничен `reuters.com`", text)
        self.assertIn("AI funding acquisition business", text)
        self.assertIn("direction_id=major_agencies", text)
        self.assertIn("API filter ограничен `bloomberg.com`", text)
        self.assertIn("`ft.com`", text)
        self.assertIn("direction_id=independent_missing_events", text)
        self.assertIn("`apnews.com` и `ap.org`", text)
        self.assertIn("consumer products / major technology", text)


if __name__ == "__main__":
    unittest.main()
