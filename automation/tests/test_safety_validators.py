from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_digest_artifact import validate_artifact  # noqa: E402
from validate_dzen_feed import validate_feed  # noqa: E402


TITLE = "ИИ-Сводка на 11 июля 2026"
SOURCE_URL = "https://example.com/news/one"
DZEN_URL = "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1"


def article_html(*, dzen_text: str = "Архив ИИ-Сводок", conclusions: int = 4) -> str:
    list_items = "".join(f"<li>Вывод {index}</li>" for index in range(1, conclusions + 1))
    return (
        "<p>День на новости выдался слабым - поэтому коротко</p>"
        "<h2>Мировые лидеры ИИ</h2>"
        "<h3>Тестовый сюжет</h3>"
        f'<p>Подтверждён факт со <a href="{SOURCE_URL}">ссылкой на источник</a>.</p>'
        "<p>Это важно для рынка и разработки, но выводы пока ограничены доступными данными.</p>"
        "<h2>Что это значит</h2>"
        f"<ol>{list_items}</ol>"
        "<h2>Все ИИ-Сводки</h2>"
        f'<p><a href="{DZEN_URL}">{dzen_text}</a></p>'
    )



def article_html_with_meta(*, repeated_star: bool = False) -> str:
    later = "Meta*" if repeated_star else "Meta"
    return (
        "<p>День на новости выдался слабым - поэтому коротко</p>"
        "<h2>Мировые лидеры ИИ</h2>"
        "<h3>Тестовый сюжет Meta*</h3>"
        f'<p>Meta объявила изменение со <a href="{SOURCE_URL}">ссылкой на источник</a>.</p>'
        f"<p>{later} уточнила ограничения продукта и сроки внедрения.</p>"
        "<h2>Что это значит</h2>"
        "<ol><li>Вывод 1</li><li>Вывод 2</li><li>Вывод 3</li><li>Вывод 4</li></ol>"
        "<h2>Все ИИ-Сводки</h2>"
        f'<p><a href="{DZEN_URL}">Архив ИИ-Сводок</a></p>'
        "<p><em>*Meta и ее сервисы - в России запрещены</em></p>"
    )



def with_rss_cover(html: str, *, src: str = "https://rybalka.one/posts/images/cover.png") -> str:
    return (
        '<figure>'
        f'<img src="{src}" alt="{TITLE}" width="1280" height="720">'
        '<figcaption>Главные новости искусственного интеллекта за 11 июля 2026 года</figcaption>'
        '</figure>'
        + html
    )

def image_prompt() -> str:
    return (
        f"Изображение 16:9: точный заголовок «{TITLE}».\n"
        "Главные визуальные темы: нейтральная вычислительная инфраструктура.\n"
        "Композиция: плотная редакционная композиция без пустой половины кадра.\n"
        "Стиль: современная аналитическая обложка, без логотипов, без дополнительного текста, "
        "без водяных знаков, без узнаваемых лиц, без стокового корпоративного клипарта."
    )


def write_rss(path: Path, html: str) -> None:
    rss = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>ИИ-сводки</title>
    <link>https://rybalka.one/posts</link>
    <description>Ежедневная сводка</description>
    <item>
      <title>{TITLE}</title>
      <link>https://rybalka.one/posts/2026-07-11/</link>
      <guid>https://rybalka.one/posts/2026-07-11/</guid>
      <pubDate>Sat, 11 Jul 2026 07:00:00 +0300</pubDate>
      <description>Тестовый выпуск</description>
      <content:encoded><![CDATA[{html}]]></content:encoded>
    </item>
  </channel>
</rss>
'''
    path.write_text(rss, encoding="utf-8")


def write_artifact(root: Path, *, story_id: str = "candidate-1", service_meta_star: bool = False) -> None:
    html = article_html()
    prompt = image_prompt()
    meta = {
        "date": "2026-07-11",
        "slug": "ii-svodka-2026-07-11",
        "title": TITLE,
        "published_at": "2026-07-11T07:00:00+03:00",
        "author": "ИИ-сводки",
        "cover_filename": "ai-svodka-2026-07-11.png",
        "short_digest": True,
        "editorial_notes": ["low_news_volume"],
    }
    candidates = {
        "candidates": [
            {
                "candidate_id": "candidate-1",
                "headline": "Тестовый сюжет",
                "organization": "Example",
                "primary_source": {"url": SOURCE_URL},
            }
        ]
    }
    selection = {"selected_candidate_ids": ["candidate-1"]}
    stories = {
        "stories": [
            {
                "candidate_id": story_id,
                "headline": "Тестовый сюжет",
                "organization": "Meta*" if service_meta_star else "Example",
                "sources": [SOURCE_URL],
            }
        ]
    }
    sources = {"sources": [{"url": SOURCE_URL, "publisher": "Example"}]}
    digest = {**meta, "article_html": html, "image_prompt": prompt}
    run_info = {
        "status": "ok",
        "mode": "editorial_only",
        "pipeline": "editorial_from_saved_research",
        "web_search_calls": 0,
    }

    payloads = {
        "run-info.json": run_info,
        "candidates.json": candidates,
        "selection.json": selection,
        "digest.json": digest,
        "stories.json": stories,
        "sources.json": sources,
        "meta.json": meta,
        "editorial-output-raw.json": {"article_html": html, "image_prompt": prompt},
        "metadata-normalization.json": {"normalized": meta},
        "editorial-output.json": digest,
    }
    for name, payload in payloads.items():
        (root / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "article.html").write_text(html, encoding="utf-8")


class DzenFeedValidatorTests(unittest.TestCase):
    def test_valid_preview_feed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            write_rss(rss_path, article_html())
            report = validate_feed(
                rss_path,
                site_base_url="https://rybalka.one/posts",
                latest_only=True,
                strict_editorial=True,
            )
            self.assertEqual(report["status"], "ok", report["errors"])


    def test_accepts_build_site_cover_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            write_rss(rss_path, with_rss_cover(article_html()))
            report = validate_feed(
                rss_path,
                site_base_url="https://rybalka.one/posts",
                latest_only=True,
                strict_editorial=True,
            )
            self.assertEqual(report["status"], "ok", report["errors"])

    def test_rejects_image_inside_article_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            body = article_html().replace(
                "<h2>Что это значит</h2>",
                '<img src="https://example.com/inline.png" alt="inline">'
                "<h2>Что это значит</h2>",
            )
            write_rss(rss_path, with_rss_cover(body))
            report = validate_feed(
                rss_path,
                site_base_url="https://rybalka.one/posts",
                latest_only=True,
                strict_editorial=True,
            )
            codes = {row["code"] for row in report["errors"]}
            self.assertIn("forbidden_html_tag", codes)

    def test_rejects_non_https_cover(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            write_rss(
                rss_path,
                with_rss_cover(article_html(), src="http://rybalka.one/posts/images/cover.png"),
            )
            report = validate_feed(
                rss_path,
                site_base_url="https://rybalka.one/posts",
                latest_only=True,
                strict_editorial=True,
            )
            codes = {row["code"] for row in report["errors"]}
            self.assertIn("rss_cover_src", codes)

    def test_rejects_changed_dzen_block_and_too_many_conclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            write_rss(rss_path, article_html(dzen_text="Все выпуски", conclusions=8))
            report = validate_feed(
                rss_path,
                site_base_url="https://rybalka.one/posts",
                latest_only=True,
                strict_editorial=True,
            )
            codes = {row["code"] for row in report["errors"]}
            self.assertIn("dzen_archive_link", codes)
            self.assertIn("dzen_block_exact", codes)
            self.assertIn("conclusion_count", codes)

    def test_accepts_single_meta_star_and_footer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            write_rss(rss_path, article_html_with_meta())
            report = validate_feed(
                rss_path,
                site_base_url="https://rybalka.one/posts",
                latest_only=True,
                strict_editorial=True,
            )
            self.assertEqual(report["status"], "ok", report["errors"])

    def test_rejects_repeated_meta_star(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            rss_path = Path(temp) / "rss.xml"
            write_rss(rss_path, article_html_with_meta(repeated_star=True))
            report = validate_feed(
                rss_path,
                site_base_url="https://rybalka.one/posts",
                latest_only=True,
                strict_editorial=True,
            )
            codes = {row["code"] for row in report["errors"]}
            self.assertIn("meta_later_mentions", codes)


class ArtifactValidatorTests(unittest.TestCase):
    def test_valid_editorial_only_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_artifact(root)
            report = validate_artifact(root, root / "artifact-validation.json")
            self.assertEqual(report["status"], "ok", report["errors"])
            self.assertGreaterEqual(len(report["manifest"]), 10)

    def test_rejects_story_order_and_meta_star_in_service_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_artifact(root, story_id="wrong-candidate", service_meta_star=True)
            report = validate_artifact(root, root / "artifact-validation.json")
            codes = {row["code"] for row in report["errors"]}
            self.assertIn("story_order", codes)
            self.assertIn("meta_star_service_field", codes)

    def test_rejects_web_search_in_editorial_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_artifact(root)
            run_info_path = root / "run-info.json"
            run_info = json.loads(run_info_path.read_text(encoding="utf-8"))
            run_info["web_search_calls"] = 1
            run_info_path.write_text(json.dumps(run_info, ensure_ascii=False), encoding="utf-8")
            report = validate_artifact(root, root / "artifact-validation.json")
            codes = {row["code"] for row in report["errors"]}
            self.assertIn("web_search_calls_nonzero", codes)


if __name__ == "__main__":
    unittest.main()
