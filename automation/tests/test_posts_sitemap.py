from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PostsSitemapTests(unittest.TestCase):
    def test_build_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            posts = root / "posts"
            posts.mkdir()
            rss = posts / "rss.xml"
            rss.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
                <rss version="2.0"><channel><title>x</title>
                <link>https://rybalka.one/posts/</link>
                <item><title>x</title>
                <link>https://rybalka.one/posts/2026-07-24/</link>
                <guid>https://rybalka.one/posts/2026-07-24/</guid>
                <pubDate>Fri, 24 Jul 2026 06:07:00 +0300</pubDate>
                <enclosure
                  url="https://rybalka.one/posts/images/ai-svodka-2026-07-24.png"
                  type="image/png" length="100" />
                </item></channel></rss>""",
                encoding="utf-8",
            )
            sitemap = posts / "sitemap.xml"
            build = subprocess.run([
                "python",
                str(ROOT / "automation/scripts/build_posts_sitemap.py"),
                "--rss", str(rss),
                "--posts-root", str(posts),
                "--output", str(sitemap),
                "--report", str(root / "build.json"),
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)

            validate = subprocess.run([
                "python",
                str(ROOT / "automation/scripts/validate_posts_sitemap.py"),
                "--sitemap", str(sitemap),
                "--rss", str(rss),
                "--report", str(root / "validation.json"),
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(
                validate.returncode, 0, validate.stdout + validate.stderr
            )
            text = sitemap.read_text(encoding="utf-8")
            self.assertIn("https://rybalka.one/posts/2026-07-24/", text)
            self.assertIn(
                "https://rybalka.one/posts/images/ai-svodka-2026-07-24.png",
                text,
            )


if __name__ == "__main__":
    unittest.main()
