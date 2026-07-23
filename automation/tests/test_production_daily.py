from __future__ import annotations
import json, tempfile, unittest
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

from production_daily_common import parse_rss, runtime_context, tree_digest
import promote_production_site as promote

ATOM = "http://www.w3.org/2005/Atom"

def write_rss(path: Path, dates: list[str], prefix: str = "https://rybalka.one/posts/dzen-test/") -> None:
    ET.register_namespace("atom", ATOM)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "ИИ-Сводки"
    ET.SubElement(channel, "link").text = "https://rybalka.one/posts/"
    ET.SubElement(channel, f"{{{ATOM}}}link", {
        "href": "https://rybalka.one/posts/rss.xml",
        "rel": "self",
        "type": "application/rss+xml",
    })
    for value in dates:
        item = ET.SubElement(channel, "item")
        link = prefix + value + "/"
        ET.SubElement(item, "title").text = value
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid").text = link
        dt = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        ET.SubElement(item, "pubDate").text = format_datetime(dt)
        ET.SubElement(item, "category").text = "Статья"
        ET.SubElement(item, "category").text = "native-yes"
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(rss).write(path, encoding="utf-8", xml_declaration=True)

class ProductionDailyTests(unittest.TestCase):
    def config(self):
        return {
            "timezone": "Europe/Moscow",
            "first_publication_date": "2026-07-24",
            "feed_url": "https://rybalka.one/posts/rss.xml",
            "site_base_url": "https://rybalka.one/posts",
            "legacy_prefix": "https://rybalka.one/posts/dzen-test/",
            "minimum_legacy_items": 10,
            "require_previous_day_in_rss": True,
            "publication_hour_local": 6,
            "content_root": "automation/content",
        }

    def test_runtime_accepts_previous_day(self):
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            dates = [f"2026-07-{day:02d}" for day in range(14, 24)]
            write_rss(rss_path, dates)
            context = runtime_context(
                config=self.config(),
                rss=parse_rss(rss_path),
                now_iso="2026-07-24T06:00:00+03:00",
            )
            self.assertEqual(context["publication_date"], "2026-07-24")
            self.assertEqual(context["rss_latest_date"], "2026-07-23")

    def test_runtime_rejects_stale_rss(self):
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            dates = [f"2026-07-{day:02d}" for day in range(6, 16)]
            write_rss(rss_path, dates)
            with self.assertRaisesRegex(RuntimeError, "previous calendar day"):
                runtime_context(
                    config=self.config(),
                    rss=parse_rss(rss_path),
                    now_iso="2026-07-24T06:00:00+03:00",
                )

    def test_runtime_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            dates = [f"2026-07-{day:02d}" for day in range(14, 24)]
            write_rss(rss_path, dates)
            tree = ET.parse(rss_path)
            channel = tree.getroot().find("channel")
            item = ET.SubElement(channel, "item")
            link = "https://rybalka.one/posts/2026-07-24/"
            ET.SubElement(item, "title").text = "duplicate"
            ET.SubElement(item, "link").text = link
            ET.SubElement(item, "guid").text = link
            ET.SubElement(item, "pubDate").text = format_datetime(
                datetime(2026, 7, 23, tzinfo=timezone.utc)
            )
            tree.write(rss_path, encoding="utf-8", xml_declaration=True)
            config = self.config()
            with self.assertRaisesRegex(RuntimeError, "already contains"):
                runtime_context(
                    config=config,
                    rss=parse_rss(rss_path),
                    publication_date_override="2026-07-24",
                )

    def test_tree_digest_is_stable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a").write_text("x")
            first = tree_digest(root)
            second = tree_digest(root)
            self.assertEqual(first, second)
            (root / "a").write_text("y")
            self.assertNotEqual(first, tree_digest(root))

if __name__ == "__main__":
    unittest.main()
