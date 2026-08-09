from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

from build_site import render_article_page, render_footer_banner
from cleanup_public_posts import DATE_NAME, IMAGE_NAME


class FooterContractTests(unittest.TestCase):
    def config(self) -> dict:
        return {"site_base_url": "https://rybalka.one/posts"}

    def test_footer_markup_contract(self) -> None:
        footer = render_footer_banner(self.config())
        self.assertIn('href="https://dzen.ru/rybv"', footer)
        self.assertIn('src="https://rybalka.one/posts/_footer-scr.png"', footer)
        self.assertIn('max-width:50%', footer)

    def test_footer_is_last_content_on_article_page(self) -> None:
        page = render_article_page(
            self.config(),
            {
                "title": "Test digest",
                "description": "Description",
                "cover_filename": "cover.png",
                "article_html": "<p id=\"article-end\">END</p>",
            },
        )
        footer_at = page.index('class="digest-footer"')
        self.assertGreater(footer_at, page.index('id="article-end"'))
        self.assertLess(footer_at, page.index("</body>"))
        self.assertEqual(page.count('_footer-scr.png'), 1)

    def test_footer_asset_exists_and_is_png(self) -> None:
        asset = ROOT / "posts" / "_footer-scr.png"
        self.assertTrue(asset.is_file())
        self.assertEqual(asset.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_cleanup_date_classifiers_cannot_select_footer(self) -> None:
        self.assertIsNone(DATE_NAME.fullmatch("_footer-scr.png"))
        self.assertIsNone(IMAGE_NAME.fullmatch("_footer-scr.png"))

    def test_deploy_has_remote_self_heal_contract(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "deploy-posts.yml").read_text(encoding="utf-8")
        self.assertIn('posts/_footer-scr.png', workflow)
        self.assertIn('remote_url="ftp://${FTP_SERVER}:21/_footer-scr.png"', workflow)
        self.assertIn('--upload-file "posts/_footer-scr.png"', workflow)

    def test_new_rss_item_carries_footer_markup(self) -> None:
        source = (ROOT / "automation" / "scripts" / "build_site.py").read_text(encoding="utf-8")
        self.assertIn('"article_html": f"{source[\'article_html\']}\\n{render_footer_banner(config)}"', source)


if __name__ == "__main__":
    unittest.main()
