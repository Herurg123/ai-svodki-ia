from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

from build_site import render_index, render_rss
from validate_site import local_image_from_url, relative_index_link, relative_page_from_link


class BuildSiteLegacyTests(unittest.TestCase):
    def config(self) -> dict:
        return {
            "page_title_prefix": "Виталий Рыбалка",
            "site_title": "ИИ-Сводки",
            "site_base_url": "https://rybalka.one/posts",
            "feed_url": "https://rybalka.one/posts/rss.xml",
            "language": "ru-RU",
            "author": "ИИ-сводки",
        }

    def legacy_item(self) -> dict:
        return {
            "title": "ИИ-Сводка на 15 июля 2026",
            "link": "https://rybalka.one/posts/dzen-test/2026-07-15/",
            "guid": "https://rybalka.one/posts/dzen-test/2026-07-15/",
            "published_datetime": datetime(2026, 7, 15, 7, tzinfo=timezone.utc),
            "author": "ИИ-сводки",
            "description_html": "<p>Описание</p>",
            "article_html": "<figure><img src=\"https://rybalka.one/posts/dzen-test/images/ai-svodka-2026-07-15.png\" alt=\"cover\"><figcaption>cover</figcaption></figure><h2>Мировые лидеры ИИ</h2>",
            "image_url": "https://rybalka.one/posts/dzen-test/images/ai-svodka-2026-07-15.png",
            "image_filename": "ai-svodka-2026-07-15.png",
            "categories": ["Статья", "ИИ", "Технологии", "native-yes"],
        }

    def test_index_uses_real_legacy_link(self) -> None:
        html = render_index(self.config(), [self.legacy_item()])
        self.assertIn('href="./dzen-test/2026-07-15/"', html)
        self.assertNotIn('href="./2026-07-15/"', html)

    def test_rss_preserves_legacy_image_url_and_categories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            image = output / "dzen-test" / "images" / "ai-svodka-2026-07-15.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"png")
            rss = render_rss(
                self.config(),
                {"title": "Принятый заголовок ленты", "description": "Описание"},
                [self.legacy_item()],
                output,
            )
            self.assertIn("<title>Принятый заголовок ленты</title>", rss)
            self.assertIn(
                'enclosure url="https://rybalka.one/posts/dzen-test/images/ai-svodka-2026-07-15.png"',
                rss,
            )
            for category in ("Статья", "ИИ", "Технологии", "native-yes"):
                self.assertIn(f"<category>{category}</category>", rss)

    def test_site_validator_resolves_legacy_paths(self) -> None:
        base = "https://rybalka.one/posts"
        link = "https://rybalka.one/posts/dzen-test/2026-07-15/"
        self.assertEqual(relative_page_from_link(link, base), "dzen-test/2026-07-15")
        self.assertEqual(relative_index_link(link, base), "./dzen-test/2026-07-15/")
        root = Path("/tmp/posts")
        image = local_image_from_url(
            root,
            "https://rybalka.one/posts/dzen-test/images/cover.png",
            base,
        )
        self.assertEqual(image, root / "dzen-test" / "images" / "cover.png")


if __name__ == "__main__":
    unittest.main()
