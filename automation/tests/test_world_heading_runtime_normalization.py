from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from editorial_policy_runtime import (  # noqa: E402
    WORLD_HEADING,
    normalize_editorial_structure,
)


RUSSIA_ONLY_HTML = (
    "<p>За сутки подтверждён один значимый российский сюжет. "
    "Остальные кандидаты не прошли проверку свежести.</p>"
    "<h2>Российские лидеры ИИ</h2>"
    "<h3>VK обновила инструменты для медиа</h3>"
    "<p>VK представила обновление продукта.</p>"
    "<p>Источник подтверждает дату и основные факты.</p>"
    "<h2>Что это значит</h2>"
    "<ol><li>Вывод 1</li><li>Вывод 2</li><li>Вывод 3</li><li>Вывод 4</li></ol>"
    "<h2>Все ИИ-Сводки</h2>"
)


class WorldHeadingRuntimeNormalizationTests(unittest.TestCase):
    def test_inserts_missing_world_heading_before_first_section(self) -> None:
        editorial = {"digest": {"article_html": RUSSIA_ONLY_HTML}}

        changes = normalize_editorial_structure(editorial)

        normalized = editorial["digest"]["article_html"]
        self.assertEqual(normalized.count(f"<h2>{WORLD_HEADING}</h2>"), 1)
        self.assertLess(
            normalized.index(f"<h2>{WORLD_HEADING}</h2>"),
            normalized.index("<h2>Российские лидеры ИИ</h2>"),
        )
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["field"], "digest.article_html.world_heading")

    def test_does_not_duplicate_existing_world_heading(self) -> None:
        article = RUSSIA_ONLY_HTML.replace(
            "<h2>Российские лидеры ИИ</h2>",
            f"<h2>{WORLD_HEADING}</h2><h2>Российские лидеры ИИ</h2>",
            1,
        )
        editorial = {"digest": {"article_html": article}}

        changes = normalize_editorial_structure(editorial)

        self.assertEqual(editorial["digest"]["article_html"], article)
        self.assertEqual(changes, [])

    def test_does_not_hide_completely_missing_section_structure(self) -> None:
        article = "<p>Текст без единого тематического раздела.</p>"
        editorial = {"digest": {"article_html": article}}

        changes = normalize_editorial_structure(editorial)

        self.assertEqual(editorial["digest"]["article_html"], article)
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()
