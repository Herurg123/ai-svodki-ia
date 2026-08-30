from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_posts_sitemap import build_sitemap  # noqa: E402
from build_site import render_index, render_rss  # noqa: E402
from cleanup_public_posts import (  # noqa: E402
    PublicCleanupError,
    render_github_summary,
    run_cleanup,
    tree_files,
)
from inject_blogposting_schema import index_graph, inject  # noqa: E402


class PublicPostsCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.site_config = json.loads(
            (ROOT / "automation/config/site.json").read_text(encoding="utf-8")
        )
        self.structured_config = json.loads(
            (ROOT / "automation/config/structured-data.json").read_text(
                encoding="utf-8"
            )
        )
        self.zone = ZoneInfo("Europe/Moscow")

    def item(self, value: str) -> dict:
        image_name = f"ai-svodka-{value}.png"
        base = "https://rybalka.one/posts"
        link = f"{base}/{value}/"
        image_url = f"{base}/images/{image_name}"
        return {
            "title": f"ИИ-Сводка на {value}",
            "link": link,
            "guid": link,
            "published_datetime": datetime.fromisoformat(value).replace(
                hour=6, tzinfo=self.zone
            ),
            "author": "ИИ-сводки",
            "description_html": f"<p>Описание {value}</p>",
            "article_html": (
                f'<figure><img src="{image_url}" alt="{value}"></figure>'
                f"<h2>Выпуск {value}</h2><p>Текст</p>"
            ),
            "image_url": image_url,
            "image_filename": image_name,
            "categories": ["Статья", "ИИ", "Технологии", "native-yes"],
        }

    def write_site(self, posts: Path, values: list[str]) -> None:
        (posts / "images").mkdir(parents=True)
        dzen = posts / "dzen-test"
        dzen.mkdir()
        (dzen / "index.html").write_text(
            "<!doctype html><title>Retired Dzen shell</title>\n",
            encoding="utf-8",
        )
        (dzen / "rss.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<rss version="2.0"><channel>'
            '<title>Retired Dzen shell</title>'
            '<link>https://rybalka.one/posts/dzen-test/</link>'
            '<description>Retired.</description>'
            '</channel></rss>\n',
            encoding="utf-8",
        )

        items = [self.item(value) for value in values]
        items.sort(key=lambda row: row["published_datetime"], reverse=True)
        for item in items:
            value = item["published_datetime"].date().isoformat()
            page = posts / value
            page.mkdir()
            (page / "index.html").write_text(
                f"<html><body>{value}</body></html>\n", encoding="utf-8"
            )
            (posts / "images" / item["image_filename"]).write_bytes(
                f"image-{value}".encode()
            )

        channel = {"title": "ИИ-Сводки", "description": "Актуальные выпуски"}
        (posts / "rss.xml").write_text(
            render_rss(self.site_config, channel, items, posts), encoding="utf-8"
        )
        (posts / "index.html").write_text(
            render_index(self.site_config, items), encoding="utf-8"
        )
        inject(
            posts / "index.html",
            index_graph(
                config=self.structured_config,
                rss_path=posts / "rss.xml",
            ),
            self.structured_config["blog_url"],
            self.structured_config["feed_url"],
        )
        build_sitemap(
            rss=posts / "rss.xml",
            posts_root=posts,
            output=posts / "sitemap.xml",
            reference_date=date(2026, 8, 8),
        )

    def cleanup(
        self,
        posts: Path,
        *,
        reference_date: date,
        apply: bool,
        retention_days: int = 32,
    ) -> dict:
        return run_cleanup(
            posts,
            site_config=self.site_config,
            structured_config=self.structured_config,
            reference_date=reference_date,
            retention_days=retention_days,
            timezone_name="Europe/Moscow",
            apply=apply,
        )

    def test_dry_run_finds_only_items_strictly_older_than_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-07", "2026-07-06"])
            before = tree_files(posts)
            report = self.cleanup(
                posts, reference_date=date(2026, 8, 8), apply=False
            )
            self.assertEqual(report["cutoff_date"], "2026-07-07")
            self.assertEqual(
                [row["publication_date"] for row in report["expired_releases"]],
                ["2026-07-06"],
            )
            self.assertEqual(report["rss_items_after"], 1)
            self.assertNotIn("legacy_items_before", report)
            self.assertFalse(report["changes_applied"])
            self.assertEqual(tree_files(posts), before)

    def test_apply_removes_canonical_page_and_image_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-07", "2026-07-06"])
            shell_before = {
                path.name: path.read_bytes()
                for path in (
                    posts / "dzen-test/index.html",
                    posts / "dzen-test/rss.xml",
                )
            }
            report = self.cleanup(
                posts, reference_date=date(2026, 8, 8), apply=True
            )
            self.assertTrue(report["changes_applied"])
            self.assertEqual(report["removed_files"], 2)
            self.assertFalse((posts / "2026-07-06").exists())
            self.assertFalse(
                (posts / "images/ai-svodka-2026-07-06.png").exists()
            )
            self.assertEqual(
                report["updated_files"], ["index.html", "rss.xml", "sitemap.xml"]
            )
            for path in (
                posts / "rss.xml",
                posts / "index.html",
                posts / "sitemap.xml",
            ):
                self.assertNotIn("2026-07-06", path.read_text(encoding="utf-8"))
            for path in (
                posts / "dzen-test/index.html",
                posts / "dzen-test/rss.xml",
            ):
                self.assertEqual(path.read_bytes(), shell_before[path.name])
            items = ET.parse(posts / "rss.xml").getroot().findall("./channel/item")
            self.assertEqual(len(items), 1)

    def test_canonical_cleanup_never_rewrites_retired_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-08-25", "2026-07-23"])
            before = {
                path.name: path.read_bytes()
                for path in (
                    posts / "dzen-test/index.html",
                    posts / "dzen-test/rss.xml",
                )
            }
            report = self.cleanup(
                posts, reference_date=date(2026, 8, 25), apply=True
            )
            self.assertNotIn("dzen-test/index.html", report["updated_files"])
            self.assertNotIn("dzen-test/rss.xml", report["updated_files"])
            for path in (
                posts / "dzen-test/index.html",
                posts / "dzen-test/rss.xml",
            ):
                self.assertEqual(path.read_bytes(), before[path.name])

    def test_mismatched_rss_date_is_rejected_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-07"])
            rss = posts / "rss.xml"
            rss.write_text(
                rss.read_text(encoding="utf-8").replace(
                    "Tue, 07 Jul 2026", "Mon, 06 Jul 2026"
                ),
                encoding="utf-8",
            )
            before = tree_files(posts)
            with self.assertRaisesRegex(PublicCleanupError, "does not match pubDate"):
                self.cleanup(
                    posts, reference_date=date(2026, 8, 8), apply=True
                )
            self.assertEqual(tree_files(posts), before)

    def test_orphaned_canonical_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-07"])
            orphan = posts / "2026-06-01"
            orphan.mkdir()
            (orphan / "index.html").write_text("orphan", encoding="utf-8")
            with self.assertRaisesRegex(PublicCleanupError, "orphaned"):
                self.cleanup(
                    posts, reference_date=date(2026, 8, 8), apply=True
                )

    def test_retired_shell_rejects_dated_legacy_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-07"])
            legacy = posts / "dzen-test/2026-07-06"
            legacy.mkdir()
            (legacy / "index.html").write_text("legacy", encoding="utf-8")
            before = tree_files(posts)
            with self.assertRaisesRegex(PublicCleanupError, "must stay inert"):
                self.cleanup(
                    posts, reference_date=date(2026, 8, 8), apply=True
                )
            self.assertEqual(tree_files(posts), before)

    def test_root_rss_rejects_legacy_dated_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-07"])
            rss = posts / "rss.xml"
            canonical = "https://rybalka.one/posts/2026-07-07/"
            legacy = "https://rybalka.one/posts/dzen-test/2026-07-07/"
            rss.write_text(
                rss.read_text(encoding="utf-8").replace(canonical, legacy),
                encoding="utf-8",
            )
            before = tree_files(posts)
            with self.assertRaisesRegex(PublicCleanupError, "non-canonical dated path"):
                self.cleanup(
                    posts, reference_date=date(2026, 8, 8), apply=True
                )
            self.assertEqual(tree_files(posts), before)

    def test_minimum_retention_cannot_be_bypassed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-07"])
            with self.assertRaisesRegex(PublicCleanupError, "at least 32"):
                self.cleanup(
                    posts,
                    reference_date=date(2026, 8, 8),
                    retention_days=31,
                    apply=False,
                )

    def test_cleanup_refuses_to_remove_the_last_root_rss_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-06"])
            before = tree_files(posts)
            with self.assertRaisesRegex(PublicCleanupError, "every root RSS item"):
                self.cleanup(
                    posts, reference_date=date(2026, 8, 8), apply=True
                )
            self.assertEqual(tree_files(posts), before)

    def test_russian_summary_is_canonical_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, ["2026-07-07", "2026-07-06"])
            report = self.cleanup(
                posts, reference_date=date(2026, 8, 8), apply=False
            )
            dry = render_github_summary(
                report,
                cleanup_outcome="success",
                validation_outcome="skipped",
                commit_outcome="skipped",
            )
            self.assertIn("ручной dry-run", dry)
            self.assertIn("RSS: **2 → 1**", dry)
            self.assertNotIn("Legacy RSS", dry)
            self.assertNotIn("dzen-test", dry)
            report["mode"] = "apply"
            report["changes_applied"] = True
            published = render_github_summary(
                report,
                cleanup_outcome="success",
                validation_outcome="success",
                commit_outcome="success",
            )
            self.assertIn("передан FTP-синхронизации", published)
            self.assertIn("удалено из GitHub", published)


if __name__ == "__main__":
    unittest.main()
