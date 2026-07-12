from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from editorial_policy import (
    read_policy,
    validate_article_policy,
    validate_stories,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "automation" / "config" / "site.json"
EDITORIAL_CONFIG_PATH = ROOT / "automation" / "config" / "editorial.json"

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
DC_NS = "http://purl.org/dc/elements/1.1/"
MEDIA_NS = "http://search.yahoo.com/mrss/"
ATOM_NS = "http://www.w3.org/2005/Atom"

RUSSIAN_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Собрать статический preview сайта, индекса и RSS, не изменяя posts/."
        )
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        type=Path,
        help="Preview выпуска: automation/preview/YYYY-MM-DD/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Каталог результата. По умолчанию используется "
            "preview_posts_directory из site.json."
        ),
    )
    parser.add_argument(
        "--build-info",
        type=Path,
        default=ROOT / "automation" / "preview" / "build-info.json",
        help="Путь к отчёту сборки.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в {path}: {exc}") from exc


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def resolve_from_root(path: Path | str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


def assert_inside(path: Path, parent: Path, label: str) -> None:
    resolved = path.resolve()
    allowed = parent.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise RuntimeError(f"{label} должен находиться внутри {allowed}.")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return "missing"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def cdata(value: str) -> str:
    cleaned = value.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{cleaned}]]>"


def xml_text(value: str) -> str:
    return html.escape(value, quote=False)


def xml_attr(value: str) -> str:
    return html.escape(value, quote=True)


def normalise_base_url(value: str) -> str:
    return value.rstrip("/")


def parse_iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(f"Некорректный published_at: {value!r}") from exc
    if parsed.tzinfo is None:
        raise RuntimeError("published_at должен содержать часовой пояс.")
    return parsed


def parse_rss_datetime(value: str) -> datetime:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Некорректный pubDate в RSS: {value!r}") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"pubDate не содержит часовой пояс: {value!r}")
    return parsed


def image_filename_from_url(url: str) -> str:
    filename = Path(urlsplit(url).path).name
    if not filename:
        raise RuntimeError(f"Невозможно определить имя изображения из URL: {url}")
    return filename


def candidates_from_stories(stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for story in stories:
        sources = story.get("sources")
        primary_source = sources[0] if isinstance(sources, list) and sources else {}
        candidates.append(
            {
                "id": str(story.get("candidate_id", "")),
                "archive_status": (
                    "update" if story.get("status") == "update" else "none"
                ),
                "geography": str(story.get("geography", "world")),
                "organization": str(story.get("organization", "")),
                "primary_source": primary_source,
            }
        )
    return candidates


def load_source(source_dir: Path, policy: dict[str, Any]) -> dict[str, Any]:
    digest_path = source_dir / "digest.json"
    article_path = source_dir / "article.html"
    meta_path = source_dir / "meta.json"
    sources_path = source_dir / "sources.json"
    stories_path = source_dir / "stories.json"
    cover_path = source_dir / "cover.png"

    digest = read_json(digest_path)
    if not isinstance(digest, dict):
        raise RuntimeError("digest.json должен содержать JSON-объект.")
    if digest.get("status") != "ok":
        raise RuntimeError("Сборка разрешена только для digest со status=ok.")

    required = {
        "date",
        "slug",
        "title",
        "description",
        "published_at",
        "author",
        "cover_filename",
        "article_html",
        "topics",
        "sources",
        "short_digest",
        "editorial_notes",
    }
    missing = sorted(required.difference(digest))
    if missing:
        raise RuntimeError("В digest.json отсутствуют поля: " + ", ".join(missing))

    if not isinstance(digest.get("short_digest"), bool):
        raise RuntimeError("short_digest должен быть boolean.")
    if not isinstance(digest.get("editorial_notes"), list):
        raise RuntimeError("editorial_notes должен быть массивом.")

    article_html = article_path.read_text(encoding="utf-8").strip()
    if article_html != str(digest["article_html"]).strip():
        raise RuntimeError("article.html не совпадает с article_html из digest.json.")

    meta = read_json(meta_path)
    if not isinstance(meta, dict):
        raise RuntimeError("meta.json должен содержать JSON-объект.")
    for key in (
        "status",
        "error_message",
        "date",
        "slug",
        "title",
        "description",
        "published_at",
        "author",
        "cover_filename",
        "topics",
        "short_digest",
        "editorial_notes",
    ):
        if meta.get(key) != digest.get(key):
            raise RuntimeError(f"meta.json не совпадает с digest.json по полю {key}.")

    sources = read_json(sources_path)
    if sources != digest["sources"]:
        raise RuntimeError("sources.json не совпадает с sources из digest.json.")

    stories = read_json(stories_path)
    if not isinstance(stories, list) or not stories:
        raise RuntimeError("stories.json должен содержать непустой массив.")
    selected_candidates = candidates_from_stories(stories)
    story_errors = validate_stories(stories, selected_candidates)
    if story_errors:
        raise RuntimeError("Проверка stories.json завершилась ошибками:\n- " + "\n- ".join(story_errors))

    policy_errors, policy_warnings, policy_analysis = validate_article_policy(
        article_html,
        selected_candidates,
        bool(digest["short_digest"]),
        policy,
    )
    if policy_errors:
        raise RuntimeError("Редакционная проверка article.html завершилась ошибками:\n- " + "\n- ".join(policy_errors))

    if not cover_path.is_file():
        raise RuntimeError(f"Не найдено изображение preview: {cover_path}")

    try:
        publication_date = date.fromisoformat(str(digest["date"]))
    except ValueError as exc:
        raise RuntimeError("Поле date имеет неверный формат.") from exc

    if digest["slug"] != digest["date"]:
        raise RuntimeError("slug должен совпадать с date.")

    cover_filename = str(digest["cover_filename"])
    if Path(cover_filename).name != cover_filename or not cover_filename.endswith(".png"):
        raise RuntimeError("cover_filename должен быть простым именем PNG-файла.")

    lowered = article_html.lower()
    for forbidden in ("<h1", "<img", "<html", "<head", "<body", "<script"):
        if forbidden in lowered:
            raise RuntimeError(f"article.html содержит запрещённый фрагмент {forbidden}.")

    return {
        **digest,
        "article_html": article_html,
        "publication_date": publication_date,
        "published_datetime": parse_iso_datetime(str(digest["published_at"])),
        "cover_path": cover_path,
        "stories": stories,
        "policy_warnings": policy_warnings,
        "policy_analysis": policy_analysis,
    }


def read_existing_items(rss_path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    try:
        tree = ET.parse(rss_path)
    except ET.ParseError as exc:
        raise RuntimeError(f"Рабочий RSS не разбирается как XML: {exc}") from exc

    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("В рабочем RSS отсутствует channel.")

    channel_data = {
        "title": (channel.findtext("title") or "").strip(),
        "description": (channel.findtext("description") or "").strip(),
    }

    items: list[dict[str, Any]] = []
    for position, item in enumerate(channel.findall("item"), start=1):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        author = (item.findtext(f"{{{DC_NS}}}creator") or "").strip()
        description = item.findtext("description") or ""
        article_html = item.findtext(f"{{{CONTENT_NS}}}encoded") or ""
        enclosure = item.find("enclosure")
        image_url = enclosure.get("url", "").strip() if enclosure is not None else ""

        if not all((title, link, guid, pub_date, article_html, image_url)):
            raise RuntimeError(f"RSS item {position} неполон и не может быть перенесён.")

        categories = [
            (category.text or "").strip()
            for category in item.findall("category")
            if (category.text or "").strip()
        ]

        items.append(
            {
                "title": title,
                "link": link,
                "guid": guid,
                "published_datetime": parse_rss_datetime(pub_date),
                "author": author,
                "description_html": description.strip(),
                "article_html": article_html.strip(),
                "image_url": image_url,
                "image_filename": image_filename_from_url(image_url),
                "categories": categories,
            }
        )

    if not items:
        raise RuntimeError("Рабочий RSS не содержит ни одного item.")
    return items, channel_data


def render_article_page(config: dict[str, Any], source: dict[str, Any]) -> str:
    prefix = str(
        config.get("page_title_prefix", "Виталий Рыбалка | Vitaly Rybalka")
    ).strip()
    title = str(source["title"])
    image_filename = str(source["cover_filename"])
    return f"""<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <meta name=\"description\" content=\"{xml_attr(str(source['description']))}\">
  <title>{xml_text(prefix)} | {xml_text(title)}</title>
</head>
<body>
<h1>{xml_text(title)}</h1>
<img src=\"../images/{xml_attr(image_filename)}\" alt=\"{xml_attr(title)}\">
{source['article_html']}
</body>
</html>
"""


def render_index(config: dict[str, Any], items: list[dict[str, Any]]) -> str:
    prefix = str(
        config.get("page_title_prefix", "Виталий Рыбалка | Vitaly Rybalka")
    ).strip()
    site_title = str(config["site_title"])
    entries = []
    for item in items:
        slug = item["published_datetime"].date().isoformat()
        entries.append(
            "<article>\n"
            f"  <h2><a href=\"./{slug}/\">{xml_text(item['title'])}</a></h2>\n"
            "</article>"
        )
    entries_html = "\n\n".join(entries)
    return f"""<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{xml_text(prefix)} | {xml_text(site_title)}</title>
</head>
<body>
<h1>{xml_text(site_title)}</h1>
<p>Главные события в сфере искусственного интеллекта за каждые сутки.</p>
{entries_html}
</body>
</html>
"""


def figure_caption(publication_date: date) -> str:
    return (
        "Главные новости искусственного интеллекта за "
        f"{publication_date.day} {RUSSIAN_MONTHS[publication_date.month]} "
        f"{publication_date.year} года"
    )


def render_rss(
    config: dict[str, Any],
    channel_data: dict[str, str],
    items: list[dict[str, Any]],
    output_dir: Path,
) -> str:
    site_base_url = normalise_base_url(str(config["site_base_url"]))
    feed_url = str(config["feed_url"])
    site_title = str(config["site_title"])
    language = str(config["language"])
    author_default = str(config["author"])
    description = channel_data.get("description") or (
        "Ежедневные обзоры главных событий в сфере искусственного интеллекта, "
        "нейросетей, технологий и автоматизации"
    )

    newest = max(item["published_datetime"] for item in items)
    item_blocks: list[str] = []

    for item in items:
        image_filename = str(item["image_filename"])
        image_path = output_dir / "images" / image_filename
        if not image_path.is_file():
            raise RuntimeError(f"Для RSS отсутствует изображение: {image_path}")
        image_size = image_path.stat().st_size
        image_url = f"{site_base_url}/images/{image_filename}"
        title = str(item["title"])
        link = str(item["link"])
        author = str(item.get("author") or author_default)
        publication_date = item["published_datetime"].date()
        description_html = str(item["description_html"]).strip()
        if not description_html:
            description_html = f"<p>{xml_text(title)}</p>"
        article_html = str(item["article_html"]).strip()

        if item.get("is_new"):
            content_html = (
                "<figure>\n"
                f'<img src="{xml_attr(image_url)}" alt="{xml_attr(title)}">\n'
                f"<figcaption>{xml_text(figure_caption(publication_date))}</figcaption>\n"
                "</figure>\n"
                f"{article_html}"
            )
        else:
            content_html = article_html
            # Existing content normally already has the figure. If not, add it.
            if "<figure" not in content_html.lower():
                content_html = (
                    "<figure>\n"
                    f'<img src="{xml_attr(image_url)}" alt="{xml_attr(title)}">\n'
                    f"<figcaption>{xml_text(figure_caption(publication_date))}</figcaption>\n"
                    "</figure>\n"
                    f"{content_html}"
                )

        categories = ["native-yes", "Технологии", "Искусственный интеллект"]
        category_xml = "\n".join(
            f"    <category>{xml_text(category)}</category>" for category in categories
        )

        block = f"""  <item>
    <title>{xml_text(title)}</title>
    <link>{xml_text(link)}</link>
    <guid isPermaLink=\"true\">{xml_text(link)}</guid>
    <pubDate>{format_datetime(item['published_datetime'])}</pubDate>
    <dc:creator>{xml_text(author)}</dc:creator>
{category_xml}
    <media:rating scheme=\"urn:simple\">nonadult</media:rating>
    <enclosure url=\"{xml_attr(image_url)}\" type=\"image/png\" length=\"{image_size}\" />
    <media:content url=\"{xml_attr(image_url)}\" medium=\"image\" type=\"image/png\" />
    <media:thumbnail url=\"{xml_attr(image_url)}\" />
    <description>{cdata(description_html)}</description>
    <content:encoded>{cdata(content_html)}</content:encoded>
  </item>"""
        item_blocks.append(block)

    items_xml = "\n\n".join(item_blocks)
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\"
  xmlns:content=\"{CONTENT_NS}\"
  xmlns:dc=\"{DC_NS}\"
  xmlns:media=\"{MEDIA_NS}\"
  xmlns:atom=\"{ATOM_NS}\">
<channel>
  <title>{xml_text(site_title)}</title>
  <link>{xml_text(site_base_url + '/')}</link>
  <description>{xml_text(description)}</description>
  <language>{xml_text(language)}</language>
  <lastBuildDate>{format_datetime(newest)}</lastBuildDate>
  <dc:creator>{xml_text(author_default)}</dc:creator>
  <atom:link href=\"{xml_attr(feed_url)}\" rel=\"self\" type=\"application/rss+xml\" />

{items_xml}
</channel>
</rss>
"""


def main() -> int:
    args = parse_args()
    started_at = datetime.now().astimezone()

    try:
        config = read_json(CONFIG_PATH)
        if not isinstance(config, dict):
            raise RuntimeError("site.json должен содержать JSON-объект.")

        source_dir = resolve_from_root(args.source_dir)
        assert_inside(source_dir, ROOT / "automation" / "preview", "source-dir")

        output_dir = (
            resolve_from_root(args.output_dir)
            if args.output_dir is not None
            else resolve_from_root(config["preview_posts_directory"])
        )
        assert_inside(output_dir, ROOT / "automation" / "preview", "output-dir")
        if output_dir == source_dir or source_dir in output_dir.parents:
            raise RuntimeError("output-dir не должен совпадать с source-dir или быть внутри него.")

        live_posts = resolve_from_root(config["live_posts_directory"])
        if live_posts != (ROOT / "posts").resolve():
            raise RuntimeError("live_posts_directory должен указывать на posts/.")
        if not live_posts.is_dir():
            raise RuntimeError(f"Рабочий каталог posts не найден: {live_posts}")

        live_digest_before = tree_digest(live_posts)
        policy = read_policy(EDITORIAL_CONFIG_PATH)
        source = load_source(source_dir, policy)

        temporary = output_dir.parent / f".{output_dir.name}.tmp-{os.getpid()}"
        assert_inside(temporary, ROOT / "automation" / "preview", "temporary")
        if temporary.exists():
            shutil.rmtree(temporary)
        shutil.copytree(live_posts, temporary)

        items, channel_data = read_existing_items(live_posts / "rss.xml")
        site_base_url = normalise_base_url(str(config["site_base_url"]))
        article_link = f"{site_base_url}/{source['slug']}/"
        if any(item["link"] == article_link for item in items):
            raise RuntimeError(
                f"В рабочем RSS уже существует выпуск {source['date']}; "
                "dry run должен использовать новую дату."
            )

        destination_image = temporary / "images" / source["cover_filename"]
        destination_image.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source["cover_path"], destination_image)

        article_dir = temporary / source["slug"]
        article_dir.mkdir(parents=True, exist_ok=False)
        atomic_write(article_dir / "index.html", render_article_page(config, source))

        new_item = {
            "title": source["title"],
            "link": article_link,
            "guid": article_link,
            "published_datetime": source["published_datetime"],
            "author": source["author"],
            "description_html": f"<p>{xml_text(str(source['description']))}</p>",
            "article_html": source["article_html"],
            "image_url": f"{site_base_url}/images/{source['cover_filename']}",
            "image_filename": source["cover_filename"],
            "categories": ["native-yes", "Технологии", "Искусственный интеллект"],
            "is_new": True,
        }
        items.append(new_item)
        items.sort(key=lambda item: item["published_datetime"], reverse=True)

        atomic_write(temporary / "index.html", render_index(config, items))
        atomic_write(
            temporary / "rss.xml",
            render_rss(config, channel_data, items, temporary),
        )

        if output_dir.exists():
            shutil.rmtree(output_dir)
        temporary.replace(output_dir)

        live_digest_after = tree_digest(live_posts)
        if live_digest_before != live_digest_after:
            raise RuntimeError("Защитная проверка: рабочий каталог posts/ изменился.")

        build_info_path = resolve_from_root(args.build_info)
        assert_inside(
            build_info_path,
            ROOT / "automation" / "preview",
            "build-info",
        )
        build_info = {
            "status": "ok",
            "mode": "preview",
            "source_dir": str(source_dir.relative_to(ROOT)),
            "output_dir": str(output_dir.relative_to(ROOT)),
            "publication_date": source["date"],
            "items": len(items),
            "stories": len(source["stories"]),
            "short_digest": bool(source["short_digest"]),
            "policy_warnings": source["policy_warnings"],
            "live_posts_sha256_before": live_digest_before,
            "live_posts_sha256_after": live_digest_after,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        atomic_write(build_info_path, pretty_json(build_info))

        print(f"Preview сайта собран: {output_dir.relative_to(ROOT)}")
        print(f"Выпусков в RSS: {len(items)}")
        print("Рабочий posts/: не изменён")
        return 0
    except Exception as exc:
        print(f"Site build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
