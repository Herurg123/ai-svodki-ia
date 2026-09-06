import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prompt_context import compact_json, editorial_input
from ensure_story_coverage_policy import build_prompt


class PromptContextTests(unittest.TestCase):
    def test_compaction_preserves_strings_order_and_nested_values(self):
        value = {"ru": "Строка  с пробелами\nи }} скобками", "url": "https://x.test/a?q=x%20y",
                 "nested": {"empty": {}, "list": [None, False, 1.25, "\\"]}}
        result = compact_json(value)
        self.assertEqual(json.loads(result), value)
        self.assertEqual(list(json.loads(result)), list(value))
        self.assertLess(len(result), len(json.dumps(value, ensure_ascii=False, indent=2)))

    def test_editorial_keeps_one_user_message_and_identical_text_order(self):
        prefix = "Архив {\"a\":1}\n=== ARCHIVE_CONTEXT_END ==="
        a = editorial_input(prefix + "\nКандидаты A", "gpt-5.6-terra")
        b = editorial_input(prefix + "\nКандидаты B", "gpt-5.6-terra")
        self.assertEqual(a["input"][0]["content"][0], b["input"][0]["content"][0])
        self.assertEqual(a["input"][0]["role"], "user")
        self.assertEqual("".join(x["text"] for x in a["input"][0]["content"]), prefix + "\nКандидаты A")
        self.assertEqual(a["extra_body"], {"prompt_cache_options": {"mode": "implicit"}})
        self.assertNotIn("prompt_cache_breakpoint", a["input"][0]["content"][1])

    def test_unsupported_model_and_ambiguous_marker_keep_original_request(self):
        for model, prompt in [("other", "=== ARCHIVE_CONTEXT_END ==="),
                              ("gpt-5.6-terra", "no marker"),
                              ("gpt-5.6-terra", "=== ARCHIVE_CONTEXT_END ====== ARCHIVE_CONTEXT_END ===")]:
            self.assertEqual(editorial_input(prompt, model), {"input": prompt})

    def test_coverage_nested_braces_are_data_and_unresolved_variable_still_fails(self):
        kwargs = dict(publication_date="2026-09-06", search_window={}, missing_total=1,
                      maximum_web_search_calls=7, existing_candidates=[{"source": {"a": {}}}],
                      archive={"items": []})
        self.assertEqual(json.loads(build_prompt("{{EXISTING_CANDIDATES}}", **kwargs)), kwargs["existing_candidates"])
        with self.assertRaises(RuntimeError):
            build_prompt("{{UNKNOWN_VARIABLE}}", **kwargs)
