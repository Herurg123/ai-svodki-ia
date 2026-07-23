from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class StructuredDataTests(unittest.TestCase):
    def test_inject_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            posts = root / "posts"
            source.mkdir()
            (posts / "2026-07-24").mkdir(parents=True)
            (posts / "images").mkdir(parents=True)

            digest = {
                "status": "ok",
                "date": "2026-07-24",
                "title": "ИИ-Сводка на 24 июля 2026",
                "description": "Краткое описание выпуска.",
                "published_at": "2026-07-24T06:07:00+03:00",
                "cover_filename": "ai-svodka-2026-07-24.png",
                "topics": ["ИИ-агенты", "Инфраструктура"],
                "article_html": (
                    "<p>" + ("Содержательный текст выпуска. " * 60) + "</p>"
                    "<h2>Мировые лидеры ИИ</h2>"
                    "<h3>Сюжет</h3><p>Описание события.</p>"
                ),
            }
            stories = [{
                "organization": "OpenAI",
                "keywords": ["OpenAI", "агенты ИИ"],
            }]
            sources = [{
                "title": "Source",
                "publisher": "Publisher",
                "url": "https://example.com/source",
            }]
            for name, value in (
                ("digest.json", digest),
                ("stories.json", stories),
                ("sources.json", sources),
            ):
                (source / name).write_text(
                    json.dumps(value, ensure_ascii=False),
                    encoding="utf-8",
                )

            html = (
                "<!doctype html><html lang='ru'><head>"
                "<meta charset='utf-8'><title>x</title></head>"
                "<body><h1>x</h1></body></html>"
            )
            (posts / "2026-07-24/index.html").write_text(
                html, encoding="utf-8"
            )
            (posts / "index.html").write_text(html, encoding="utf-8")
            (posts / "rss.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
                <rss version="2.0"><channel><title>x</title>
                <link>https://rybalka.one/posts/</link>
                <item><title>x</title>
                <link>https://rybalka.one/posts/2026-07-24/</link>
                <guid>https://rybalka.one/posts/2026-07-24/</guid>
                <pubDate>Fri, 24 Jul 2026 06:07:00 +0300</pubDate>
                </item></channel></rss>""",
                encoding="utf-8",
            )
            png = (
                b"\x89PNG\r\n\x1a\n"
                + (13).to_bytes(4, "big")
                + b"IHDR"
                + (1536).to_bytes(4, "big")
                + (864).to_bytes(4, "big")
                + b"\x08\x02\x00\x00\x00"
                + b"\x00\x00\x00\x00"
            )
            (posts / "images/ai-svodka-2026-07-24.png").write_bytes(png)

            inject = subprocess.run([
                "python",
                str(ROOT / "automation/scripts/inject_blogposting_schema.py"),
                "--config",
                str(ROOT / "automation/config/structured-data.json"),
                "--source-dir",
                str(source),
                "--posts-root",
                str(posts),
                "--report",
                str(root / "inject.json"),
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(
                inject.returncode, 0, inject.stdout + inject.stderr
            )

            validate = subprocess.run([
                "python",
                str(ROOT / "automation/scripts/validate_structured_data.py"),
                "--source-dir",
                str(source),
                "--posts-root",
                str(posts),
                "--report",
                str(root / "validation.json"),
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(
                validate.returncode, 0, validate.stdout + validate.stderr
            )

            article = (
                posts / "2026-07-24/index.html"
            ).read_text(encoding="utf-8")
            self.assertIn('"@type": "BlogPosting"', article)
            self.assertIn(
                '"@id": "https://rybalka.one/#person"', article
            )
            self.assertIn(
                '"@id": "https://rybalka.one/#website"', article
            )
            self.assertIn(
                '"@id": "https://rybalka.one/posts/#blog"', article
            )
            self.assertNotIn(
                "application/ld+json",
                (posts / "rss.xml").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
