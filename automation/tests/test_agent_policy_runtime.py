from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy_runtime import (  # noqa: E402
    AGENT_ERROR,
    actual_prohibited_agent_form,
    wrap_validator,
)


class AgentPolicyRuntimeTests(unittest.TestCase):
    def test_actual_noun_forms_are_rejected(self) -> None:
        for value in (
            "AI agent выполняет задачу",
            "AI agents выполняют задачу",
            "AI-агент выполняет задачу",
            "AI агента подключили к системе",
            "AI-агентами управляет оператор",
        ):
            with self.subTest(value=value):
                self.assertTrue(actual_prohibited_agent_form(value))

    def test_product_name_before_adjective_is_not_rejected(self) -> None:
        for value in (
            "Meta AI агентные функции",
            "Meta AI агентная система",
            "Meta AI агентного режима",
        ):
            with self.subTest(value=value):
                self.assertFalse(actual_prohibited_agent_form(value))

    def test_wrapper_removes_only_false_positive(self) -> None:
        def original(article_html: str, *args, **kwargs):
            return [AGENT_ERROR, "other"], [], {"article": article_html}

        wrapped = wrap_validator(original)
        errors, warnings, _ = wrapped("Meta AI агентные функции")
        self.assertEqual(errors, ["other"])
        self.assertTrue(warnings)

        errors, _, _ = wrapped("Новый AI-агент выпущен")
        self.assertIn(AGENT_ERROR, errors)


if __name__ == "__main__":
    unittest.main()
