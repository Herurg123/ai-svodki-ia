from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import format_datetime
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
    Publication,
    render_github_summary,
    render_legacy_index,
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

    def item(self, value: str, kind: str) -> dict:
        image_name = f"ai-svodka-{value}.png"
        base = "https://rybalka.one/posts"
        if kind == "legacy":
            link = f"{base}/dzen-test/{value}/"
            image_url = f"{base}/dzen-test/images/{image_name}"
        else:
            link = f"{base}/{value}/"
            image_url = f"{base}/images/{image_name}"
        return {
            "title": f"ИИ-Сводка на {value}",
            "link": link,
            "guid": link,
            "published_datetime": datetime.fromisoformat(value).replace(
                hour=6,
                tzinfo=self.zone,
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

    def write_site(
        self,
        posts: Path,
        rows: list[tuple[str, str]],
    ) -> None:
        (posts / "images").mkdir(parents=True)
        (posts / "dzen-test" / "images").mkdir(parents=True)
        items = [self.item(value, kind) for value, kind in rows]
        items.sort(key=lambda row: row["published_datetime"], reverse=True)

        for item in items:
            value = item["published_datetime"].date().isoformat()
            legacy = "/dzen-test/" in item["link"]
            page = (
                posts / "dzen-test" / value
                if legacy
                else posts / value
            )
            page.mkdir(parents=True)
            (page / "index.html").write_text(
                f"<html><body>{value}</body></html>\n",
                encoding="utf-8",
            )
            image_name = item["image_filename"]
            primary = (
                posts / "dzen-test" / "images" / image_name
                if legacy
                else posts / "images" / image_name
            )
            primary.write_bytes(f"image-{value}-{legacy}".encode())
            if legacy:
                (posts / "images" / image_name).write_bytes(
                    f"mirror-{value}".encode()
                )

        channel = {
            "title": "ИИ-Сводки",
            "description": "Актуальные выпуски",
        }
        (posts / "rss.xml").write_text(
            render_rss(self.site_config, channel, items, posts),
            encoding="utf-8",
        )
        (posts / "index.html").write_text(
            render_index(self.site_config, items),
            encoding="utf-8",
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

        legacy_items = [
            item for item in items
            if "/dzen-test/" in item["link"]
        ]
        dzen_blocks = []
        for item in legacy_items:
            image_path = (
                posts / "dzen-test" / "images" / item["image_filename"]
            )
            dzen_blocks.append(
                "<item>"
                f"<title>{item['title']}</title>"
                f"<link>{item['link']}</link>"
                f'<guid isPermaLink="true">{item["link"]}</guid>'
                f"<pubDate>{format_datetime(item['published_datetime'])}</pubDate>"
                f'<enclosure url="{item["image_url"]}" '
                f'length="{image_path.stat().st_size}" type="image/png" />'
                f"<description>Описание {item['title']}</description>"
                "</item>"
            )
        if legacy_items:
            newest = legacy_items[0]
            header_image = (
                "<image>"
                f"<url>{newest['image_url']}</url>"
                "<title>ИИ-Сводки</title>"
                "<link>https://rybalka.one/posts/dzen-test/</link>"
                "</image>"
            )
            last_build = format_datetime(newest["published_datetime"])
        else:
            header_image = ""
            last_build = format_datetime(
                datetime(2026, 8, 8, tzinfo=self.zone)
            )
        dzen_rss = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<rss version="2.0"><channel>'
            "<title>ИИ-Сводки — полнотекстовые статьи для Дзена</title>"
            "<link>https://rybalka.one/posts/dzen-test/</link>"
            "<description>Полнотекстовые статьи.</description>"
            "<language>ru-RU</language>"
            f"<lastBuildDate>{last_build}</lastBuildDate>"
            f"{header_image}{''.join(dzen_blocks)}"
            "</channel></rss>"
        )
        (posts / "dzen-test" / "rss.xml").write_text(
            dzen_rss,
            encoding="utf-8",
        )
        publications = []
        for item in legacy_items:
            value = item["published_datetime"].date()
            image_name = item["image_filename"]
            publications.append(
                Publication(
                    publication_date=value,
                    kind="legacy",
                    title=item["title"],
                    link=item["link"],
                    page_directory=posts / "dzen-test" / value.isoformat(),
                    primary_image=posts / "dzen-test" / "images" / image_name,
                    mirrored_images=(posts / "images" / image_name,),
                    item=item,
                )
            )
        (posts / "dzen-test" / "index.html").write_text(
            render_legacy_index(publications, retention_days=32),
            encoding="utf-8",
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
            self.write_site(
                posts,
                [
                    ("2026-07-07", "canonical"),
                    ("2026-07-06", "legacy"),
                ],
            )
            before = tree_files(posts)

            report = self.cleanup(
                posts,
                reference_date=date(2026, 8, 8),
                apply=False,
            )

            self.assertEqual(report["cutoff_date"], "2026-07-07")
            self.assertEqual(
                [row["publication_date"] for row in report["expired_releases"]],
                ["2026-07-06"],
            )
            self.assertEqual(report["rss_items_after"], 1)
            self.assertFalse(report["changes_applied"])
            self.assertEqual(tree_files(posts), before)

    def test_apply_removes_legacy_page_both_images_and_all_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(
                posts,
                [
                    ("2026-07-07", "canonical"),
                    ("2026-07-06", "legacy"),
                ],
            )

            report = self.cleanup(
                posts,
                reference_date=date(2026, 8, 8),
                apply=True,
            )

            self.assertTrue(report["changes_applied"])
            self.assertEqual(report["removed_files"], 3)
            self.assertFalse((posts / "dzen-test/2026-07-06").exists())
            self.assertFalse(
                (posts / "dzen-test/images/ai-svodka-2026-07-06.png").exists()
            )
            self.assertFalse(
                (posts / "images/ai-svodka-2026-07-06.png").exists()
            )
            for path in (
                posts / "rss.xml",
                posts / "index.html",
                posts / "sitemap.xml",
                posts / "dzen-test/rss.xml",
                posts / "dzen-test/index.html",
            ):
                self.assertNotIn(
                    "2026-07-06",
                    path.read_text(encoding="utf-8"),
                )
            root_items = ET.parse(posts / "rss.xml").getroot().findall(
                "./channel/item"
            )
            legacy_items = ET.parse(
                posts / "dzen-test/rss.xml"
            ).getroot().findall("./channel/item")
            self.assertEqual(len(root_items), 1)
            self.assertEqual(len(legacy_items), 0)

    def test_apply_canonical_cleanup_does_not_rewrite_empty_legacy_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(
                posts,
                [
                    ("2026-08-25", "canonical"),
                    ("2026-07-23", "canonical"),
                ],
            )
            legacy_before = {
                path.name: path.read_bytes()
                for path in (
                    posts / "dzen-test/index.html",
                    posts / "dzen-test/rss.xml",
                )
            }

            report = self.cleanup(
                posts,
                reference_date=date(2026, 8, 25),
                apply=True,
            )

            self.assertEqual(
                [row["publication_date"] for row in report["expired_releases"]],
                ["2026-07-23"],
            )
            self.assertNotIn("dzen-test/index.html", report["updated_files"])
            self.assertNotIn("dzen-test/rss.xml", report["updated_files"])
            for path in (
                posts / "dzen-test/index.html",
                posts / "dzen-test/rss.xml",
            ):
                self.assertEqual(path.read_bytes(), legacy_before[path.name])

    def test_mismatched_rss_date_is_rejected_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, [("2026-07-07", "canonical")])
            rss = posts / "rss.xml"
            rss.write_text(
                rss.read_text(encoding="utf-8").replace(
                    "Tue, 07 Jul 2026",
                    "Mon, 06 Jul 2026",
                ),
                encoding="utf-8",
            )
            before = tree_files(posts)

            with self.assertRaisesRegex(
                PublicCleanupError,
                "does not match pubDate",
            ):
                self.cleanup(
                    posts,
                    reference_date=date(2026, 8, 8),
                    apply=True,
                )
            self.assertEqual(tree_files(posts), before)

    def test_orphaned_dated_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, [("2026-07-07", "canonical")])
            orphan = posts / "2026-06-01"
            orphan.mkdir()
            (orphan / "index.html").write_text("orphan", encoding="utf-8")

            with self.assertRaisesRegex(PublicCleanupError, "orphaned"):
                self.cleanup(
                    posts,
                    reference_date=date(2026, 8, 8),
                    apply=True,
                )

    def test_minimum_retention_cannot_be_bypassed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(posts, [("2026-07-07", "canonical")])

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
            self.write_site(posts, [("2026-07-06", "legacy")])
            before = tree_files(posts)

            with self.assertRaisesRegex(PublicCleanupError, "every root RSS item"):
                self.cleanup(
                    posts,
                    reference_date=date(2026, 8, 8),
                    apply=True,
                )
            self.assertEqual(tree_files(posts), before)

    def test_russian_summary_distinguishes_dry_run_and_published_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            posts = Path(temp) / "posts"
            self.write_site(
                posts,
                [
                    ("2026-07-07", "canonical"),
                    ("2026-07-06", "legacy"),
                ],
            )
            report = self.cleanup(
                posts,
                reference_date=date(2026, 8, 8),
                apply=False,
            )

            dry_summary = render_github_summary(
                report,
                cleanup_outcome="success",
                validation_outcome="skipped",
                commit_outcome="skipped",
            )
            self.assertIn("ручной dry-run", dry_summary)
            self.assertIn("не удалено (dry-run)", dry_summary)
            self.assertNotIn("передан FTP-синхронизации", dry_summary)

            report["mode"] = "apply"
            report["changes_applied"] = True
            published_summary = render_github_summary(
                report,
                cleanup_outcome="success",
                validation_outcome="success",
                commit_outcome="success",
            )
            self.assertIn("передан FTP-синхронизации", published_summary)
            self.assertIn("RSS: **2 → 1**", published_summary)
            self.assertIn("dzen-test/rss.xml", published_summary)
            self.assertIn("удалено из GitHub", published_summary)


if __name__ == "__main__":
    unittest.main()
