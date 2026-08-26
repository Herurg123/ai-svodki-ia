from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
WORKFLOW = ROOT / ".github" / "workflows" / "video-rss-enrichment.yml"
sys.path.insert(0, str(SCRIPTS))

import video_rss_enrichment as video  # noqa: E402


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>ИИ-Сводки</title>
  <link>https://rybalka.one/posts/</link>
  <lastBuildDate>Thu, 27 Aug 2026 06:00:00 +0300</lastBuildDate>
  <item>
    <title>ИИ-Сводка на 27 августа 2026</title>
    <link>https://rybalka.one/posts/2026-08-27/</link>
    <guid isPermaLink="true">https://rybalka.one/posts/2026-08-27/</guid>
    <pubDate>Thu, 27 Aug 2026 06:00:00 +0300</pubDate>
    <media:content url="https://rybalka.one/posts/images/ai-svodka-2026-08-27.png" medium="image" type="image/png" />
    <media:thumbnail url="https://rybalka.one/posts/images/ai-svodka-2026-08-27.png" />
    <description><![CDATA[<p>Краткое описание.</p>]]></description>
    <content:encoded><![CDATA[<figure><img src="https://rybalka.one/posts/images/ai-svodka-2026-08-27.png" alt="cover"><figcaption>Обложка</figcaption></figure><h2>Мировые лидеры ИИ</h2><h3>Тест</h3><p>Абзац.</p><p>Абзац.</p><h2>Что это значит</h2><ol><li>1</li><li>2</li><li>3</li><li>4</li></ol><h2>Все ИИ-Сводки</h2><p><a href="https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1">Архив ИИ-Сводок</a></p>]]></content:encoded>
  </item>
</channel>
</rss>
"""


class VideoRssEnrichmentTests(unittest.TestCase):
    def test_insert_is_exact_and_idempotent(self) -> None:
        stamp = date(2026, 8, 27)
        updated, changed = video.enrich_rss_text(
            SAMPLE_RSS,
            publication_date=stamp,
            site_base_url="https://rybalka.one/posts",
            updated_at=datetime(2026, 8, 27, 12, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )
        self.assertTrue(changed)
        self.assertIn(
            'url="https://rybalka.one/posts/video/ai-svodka-2026-08-27.mp4" medium="video" type="video/mp4"',
            updated,
        )
        self.assertIn(
            'url="https://rybalka.one/posts/video/ai-svodka-2026-08-27.png"',
            updated,
        )
        again, changed_again = video.enrich_rss_text(
            updated,
            publication_date=stamp,
            site_base_url="https://rybalka.one/posts",
            updated_at=datetime(2026, 8, 27, 12, 5, tzinfo=ZoneInfo("Europe/Moscow")),
        )
        self.assertFalse(changed_again)
        self.assertEqual(again, updated)

    def test_protected_article_fields_and_content_are_unchanged(self) -> None:
        before = ET.fromstring(SAMPLE_RSS).find("./channel/item")
        self.assertIsNotNone(before)
        updated, _ = video.enrich_rss_text(
            SAMPLE_RSS,
            publication_date=date(2026, 8, 27),
            site_base_url="https://rybalka.one/posts",
            updated_at=datetime(2026, 8, 27, 13, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )
        after = ET.fromstring(updated).find("./channel/item")
        self.assertIsNotNone(after)
        assert before is not None and after is not None
        for tag in ("title", "link", "guid", "pubDate"):
            self.assertEqual(before.findtext(tag), after.findtext(tag))
        self.assertEqual(
            before.findtext(f"{{{video.CONTENT_NS}}}encoded"),
            after.findtext(f"{{{video.CONTENT_NS}}}encoded"),
        )

    def test_missing_target_fails_closed(self) -> None:
        with self.assertRaises(video.VideoRssError):
            video.enrich_rss_text(
                SAMPLE_RSS,
                publication_date=date(2026, 8, 28),
                site_base_url="https://rybalka.one/posts",
                updated_at=datetime(2026, 8, 28, 12, 0, tzinfo=ZoneInfo("Europe/Moscow")),
            )

    def test_png_dimensions_contract(self) -> None:
        header = (
            b"\x89PNG\r\n\x1a\n"
            + b"\x00\x00\x00\x0dIHDR"
            + (1280).to_bytes(4, "big")
            + (720).to_bytes(4, "big")
            + b"\x08\x06\x00\x00\x00"
        )
        self.assertEqual(video.parse_png_dimensions(header), (1280, 720))
        with self.assertRaises(video.VideoRssError):
            video.parse_png_dimensions(b"not-a-png")

    def test_cli_offline_apply_and_workflow_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rss = root / "rss.xml"
            rss.write_text(SAMPLE_RSS, encoding="utf-8")
            config = root / "site.json"
            config.write_text(
                '{"site_base_url":"https://rybalka.one/posts"}\n',
                encoding="utf-8",
            )
            report = root / "report.json"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "video_rss_enrichment.py"),
                    "--rss",
                    str(rss),
                    "--site-config",
                    str(config),
                    "--publication-date",
                    "2026-08-27",
                    "--report",
                    str(report),
                    "--skip-remote-check",
                    "--apply",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("<media:group>", rss.read_text(encoding="utf-8"))

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "*/5 21-23 26 8 *"', workflow)
        self.assertIn('cron: "*/5 * 27 8 *"', workflow)
        self.assertIn('VIDEO_RSS_TEST_DATE: "2026-08-27"', workflow)
        self.assertIn("python automation/scripts/video_rss_enrichment.py", workflow)
        self.assertNotIn("--skip-remote-check", workflow)
        self.assertNotIn("OPENAI_API_KEY", workflow)
        self.assertNotIn("automation/notebooklm-video/", workflow)
        self.assertIn("automation/scripts/push_protected_main.sh HEAD:main", workflow)


if __name__ == "__main__":
    unittest.main()
