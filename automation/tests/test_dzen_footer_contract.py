from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

validator = importlib.import_module("validate_dzen_feed")


class DzenFooterContractTests(unittest.TestCase):
    def article(self, *, footer_src: str | None = None, inline_image: bool = False) -> str:
        footer_src = footer_src or "https://rybalka.one/posts/_footer-scr.png"
        inline = (
            '<p><img src="https://example.com/inline.png" alt="inline"></p>'
            if inline_image
            else ""
        )
        return f'''<figure>
<img src="https://rybalka.one/posts/images/cover.png" alt="Обложка">
<figcaption>Тест</figcaption>
</figure>
<h2>Мировые лидеры ИИ</h2>
<h3>Тестовый сюжет</h3><p>Первый абзац.</p><p>Второй абзац.</p>
{inline}
<h2>Что это значит</h2><ul><li>Вывод.</li></ul>
<h2>Все ИИ-Сводки</h2><p><a href="https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1">Архив ИИ-Сводок</a></p>
<p class="digest-footer" style="text-align:center;margin:32px 0 0;"><a href="https://dzen.ru/rybv" target="_blank" rel="noopener noreferrer"><img src="{footer_src}" alt="Подписаться на канал" style="display:block;max-width:50%;width:auto;height:auto;margin:0 auto;"></a></p>'''

    def validate(self, html: str) -> dict:
        report = {"errors": [], "warnings": []}
        validator.validate_article_html(
            html,
            report=report,
            item_label="test",
            strict_editorial=False,
        )
        return report

    def test_generated_footer_is_allowed(self) -> None:
        report = self.validate(self.article())
        self.assertEqual([], report["errors"])

    def test_arbitrary_inline_image_remains_forbidden(self) -> None:
        report = self.validate(self.article(inline_image=True))
        self.assertIn("forbidden_html_tag", {issue["code"] for issue in report["errors"]})

    def test_wrong_footer_image_is_rejected(self) -> None:
        report = self.validate(self.article(footer_src="https://example.com/footer.png"))
        self.assertIn("rss_footer_src", {issue["code"] for issue in report["errors"]})

    def test_duplicate_footer_is_rejected(self) -> None:
        footer = self.article().split('<p class="digest-footer"', 1)[1]
        html = self.article() + '<p class="digest-footer"' + footer
        report = self.validate(html)
        self.assertIn("forbidden_html_tag", {issue["code"] for issue in report["errors"]})


if __name__ == "__main__":
    unittest.main()
