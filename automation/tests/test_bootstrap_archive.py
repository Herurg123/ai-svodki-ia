from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

import bootstrap_archive
from bootstrap_archive import ArticleParser, normalize_meta_marker


class BootstrapArchiveTests(unittest.TestCase):
    def test_meta_markers_are_removed_from_service_data(self) -> None:
        self.assertEqual(normalize_meta_marker("Meta*"), "Meta")
        self.assertEqual(normalize_meta_marker("Meta**"), "Meta")
        parser = ArticleParser()
        parser.feed("<h3>Meta** обновила продукт</h3><p>Meta* и Meta работают.</p>")
        self.assertEqual(parser.headings, [("h3", "Meta обновила продукт")])
        self.assertNotIn("Meta*", " ".join(parser.text_parts))

    def test_content_only_date_is_added_when_absent_from_rss(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config_path = root / "automation" / "config" / "site.json"
            rss_path = root / "posts" / "rss.xml"
            content_dir = root / "automation" / "content" / "2026-07-22"
            config_path.parent.mkdir(parents=True)
            rss_path.parent.mkdir(parents=True)
            content_dir.mkdir(parents=True)

            config_path.write_text(
                json.dumps(
                    {
                        "content_directory": "automation/content",
                        "site_base_url": "https://rybalka.one/posts",
                    }
                ),
                encoding="utf-8",
            )
            rss_path.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>ИИ-Сводки</title>
    <item>
      <title>ИИ-Сводка на 23 июля 2026</title>
      <link>https://rybalka.one/posts/2026-07-23/</link>
      <pubDate>Thu, 23 Jul 2026 07:00:00 +0300</pubDate>
      <content:encoded><![CDATA[<h2>Мировые лидеры ИИ</h2><h3>Сюжет RSS</h3>]]></content:encoded>
    </item>
  </channel>
</rss>
""",
                encoding="utf-8",
            )
            (content_dir / "meta.json").write_text(
                json.dumps(
                    {
                        "published_at": "2026-07-22T07:00:00+03:00",
                        "title": "ИИ-Сводка на 22 июля 2026",
                        "description": "Архивный выпуск.",
                        "topics": ["архив"],
                    }
                ),
                encoding="utf-8",
            )
            (content_dir / "stories.json").write_text(
                json.dumps(
                    [
                        {
                            "candidate_id": "archive-001",
                            "section": "world",
                            "headline": "Архивный сюжет",
                            "organization": "Организация",
                            "topic": "архив",
                            "event_type": "публикация",
                            "status": "new",
                            "summary": "Сюжет отсутствует в RSS, но должен войти в архив.",
                            "published_at": None,
                            "published_date": "2026-07-22",
                            "time_precision": "date",
                            "sources": [
                                {
                                    "title": "Источник",
                                    "publisher": "Издание",
                                    "url": "https://example.com/source",
                                }
                            ],
                            "keywords": ["архив"],
                            "geography": "world",
                            "category": "other",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with (
                patch.object(bootstrap_archive, "ROOT", root),
                patch.object(bootstrap_archive, "CONFIG_PATH", config_path),
                patch.object(bootstrap_archive, "RSS_PATH", rss_path),
            ):
                archive = bootstrap_archive.build_archive()

            items_by_date = {item["date"]: item for item in archive["items"]}
            self.assertEqual(set(items_by_date), {"2026-07-22", "2026-07-23"})
            self.assertEqual(
                items_by_date["2026-07-22"]["link"],
                "https://rybalka.one/posts/2026-07-22/",
            )
            self.assertEqual(
                items_by_date["2026-07-22"]["stories"][0]["headline"],
                "Архивный сюжет",
            )


if __name__ == "__main__":
    unittest.main()
