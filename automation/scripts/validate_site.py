from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
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


class IndexLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Проверить статический preview сайта и RSS."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        type=Path,
        help="Preview исходного выпуска automation/preview/YYYY-MM-DD/.",
    )
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=None,
        help="Собранный каталог posts preview.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "automation" / "preview" / "site-validation.json",
        help="JSON-отчёт проверки.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в {path}: {exc}") from exc


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


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"Файл не является PNG: {path}")
    if header[12:16] != b"IHDR":
        raise RuntimeError(f"В PNG отсутствует IHDR: {path}")
    return struct.unpack(">II", header[16:24])


def relative_page_from_link(link: str, site_base_url: str) -> str | None:
    base = site_base_url.rstrip("/") + "/"
    if not link.startswith(base):
        return None
    remainder = link[len(base):].strip("/")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", remainder):
        return remainder
    if re.fullmatch(r"dzen-test/\d{4}-\d{2}-\d{2}", remainder):
        return remainder
    return None


def local_image_from_url(site_dir: Path, image_url: str, site_base_url: str) -> Path | None:
    base_path = urlsplit(site_base_url.rstrip("/") + "/").path
    image_path = urlsplit(image_url).path
    if not image_path.startswith(base_path):
        return None
    relative = image_path[len(base_path):].lstrip("/")
    if not relative:
        return None
    return site_dir / relative


def relative_index_link(link: str, site_base_url: str) -> str | None:
    page = relative_page_from_link(link, site_base_url)
    return f"./{page}/" if page else None


def normalise_html(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def validate() -> tuple[list[str], list[str], dict[str, Any]]:
    args = parse_args()
    errors: list[str] = []
    warnings: list[str] = []

    config = read_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise RuntimeError("site.json должен содержать JSON-объект.")

    source_dir = resolve_from_root(args.source_dir)
    assert_inside(source_dir, ROOT / "automation" / "preview", "source-dir")

    site_dir = (
        resolve_from_root(args.site_dir)
        if args.site_dir is not None
        else resolve_from_root(config["preview_posts_directory"])
    )
    assert_inside(site_dir, ROOT / "automation" / "preview", "site-dir")

    report_path = resolve_from_root(args.report)
    assert_inside(report_path, ROOT / "automation" / "preview", "report")

    digest = read_json(source_dir / "digest.json")
    if not isinstance(digest, dict):
        raise RuntimeError("digest.json должен содержать JSON-объект.")
    source_article = (source_dir / "article.html").read_text(encoding="utf-8").strip()

    policy = read_policy(EDITORIAL_CONFIG_PATH)
    stories = read_json(source_dir / "stories.json")
    if not isinstance(stories, list) or not stories:
        errors.append("stories.json должен содержать непустой массив.")
        stories = []

    selected_candidates: list[dict[str, Any]] = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        sources = story.get("sources")
        primary_source = sources[0] if isinstance(sources, list) and sources else {}
        selected_candidates.append(
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

    errors.extend(validate_stories(stories, selected_candidates))
    policy_errors, policy_warnings, policy_analysis = validate_article_policy(
        source_article,
        selected_candidates,
        bool(digest.get("short_digest")),
        policy,
    )
    errors.extend(policy_errors)
    warnings.extend(policy_warnings)

    meta = read_json(source_dir / "meta.json")
    if not isinstance(meta, dict):
        errors.append("meta.json должен содержать JSON-объект.")
        meta = {}
    for key in ("short_digest", "editorial_notes"):
        if meta.get(key) != digest.get(key):
            errors.append(f"meta.json не совпадает с digest.json по полю {key}.")

    index_path = site_dir / "index.html"
    rss_path = site_dir / "rss.xml"
    new_page_path = site_dir / str(digest["slug"]) / "index.html"
    new_image_path = site_dir / "images" / str(digest["cover_filename"])

    for path in (index_path, rss_path, new_page_path, new_image_path):
        if not path.is_file():
            errors.append(f"Отсутствует обязательный файл: {path.relative_to(ROOT)}")

    if errors:
        context = {
            "source_dir": str(source_dir.relative_to(ROOT)),
            "site_dir": str(site_dir.relative_to(ROOT)),
            "report_path": str(report_path.relative_to(ROOT)),
        }
        return errors, warnings, context

    index_html = index_path.read_text(encoding="utf-8")
    page_html = new_page_path.read_text(encoding="utf-8")
    rss_text = rss_path.read_text(encoding="utf-8")

    lowered_rss = rss_text.lower()
    if "<pdalink" in lowered_rss:
        errors.append("RSS содержит запрещённый элемент pdalink.")
    for forbidden_domain in ("blogspot.com", ".github.io"):
        if forbidden_domain in lowered_rss:
            errors.append(f"RSS содержит запрещённый домен: {forbidden_domain}")

    try:
        tree = ET.parse(rss_path)
    except ET.ParseError as exc:
        errors.append(f"RSS не является корректным XML: {exc}")
        context = {
            "source_dir": str(source_dir.relative_to(ROOT)),
            "site_dir": str(site_dir.relative_to(ROOT)),
            "report_path": str(report_path.relative_to(ROOT)),
        }
        return errors, warnings, context

    root = tree.getroot()
    if root.tag != "rss" or root.get("version") != "2.0":
        errors.append("Корневой элемент должен быть rss version=2.0.")

    channel = root.find("channel")
    if channel is None:
        errors.append("RSS не содержит channel.")
        context = {
            "source_dir": str(source_dir.relative_to(ROOT)),
            "site_dir": str(site_dir.relative_to(ROOT)),
            "report_path": str(report_path.relative_to(ROOT)),
        }
        return errors, warnings, context

    expected_feed_url = str(config["feed_url"])
    self_link = channel.find(f"{{{ATOM_NS}}}link")
    if self_link is None:
        errors.append("RSS не содержит atom:link rel=self.")
    else:
        if self_link.get("href") != expected_feed_url:
            errors.append(
                "atom:link href не совпадает с feed_url: "
                f"{self_link.get('href')!r} != {expected_feed_url!r}"
            )
        if self_link.get("rel") != "self":
            errors.append("atom:link должен иметь rel=self.")

    items = channel.findall("item")
    if len(items) < 4:
        errors.append(f"В preview RSS только {len(items)} item; ожидалось не менее 4.")

    seen_links: set[str] = set()
    seen_guids: set[str] = set()
    seen_dates: set[str] = set()
    parsed_dates: list[datetime] = []
    expected_new_link = f"{str(config['site_base_url']).rstrip('/')}/{digest['slug']}/"
    new_item_found = False

    for position, item in enumerate(items, start=1):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        creator = (item.findtext(f"{{{DC_NS}}}creator") or "").strip()
        description = item.findtext("description") or ""
        content = item.findtext(f"{{{CONTENT_NS}}}encoded") or ""

        if not title:
            errors.append(f"Item {position}: пустой title.")
        if not creator:
            errors.append(f"Item {position}: отсутствует dc:creator.")
        if not description.strip():
            errors.append(f"Item {position}: пустой description.")
        if not content.strip():
            errors.append(f"Item {position}: пустой content:encoded.")
        if "<figure" not in content.lower() or "<img" not in content.lower():
            errors.append(f"Item {position}: content:encoded не содержит figure/img.")

        relative_page = relative_page_from_link(link, str(config["site_base_url"]))
        if relative_page is None:
            errors.append(f"Item {position}: неожиданный link {link!r}.")
        else:
            page_path = site_dir / relative_page / "index.html"
            if not page_path.is_file():
                errors.append(
                    f"Item {position}: отсутствует страница {page_path.relative_to(ROOT)}."
                )
            if relative_page in seen_dates:
                errors.append(f"Повторный путь выпуска: {relative_page}.")
            seen_dates.add(relative_page)

        if guid != link:
            errors.append(f"Item {position}: guid должен совпадать с link.")
        if link in seen_links:
            errors.append(f"Повторный link: {link}.")
        if guid in seen_guids:
            errors.append(f"Повторный guid: {guid}.")
        seen_links.add(link)
        seen_guids.add(guid)

        try:
            parsed = parsedate_to_datetime(pub_date)
            if parsed.tzinfo is None:
                raise ValueError("timezone missing")
            parsed_dates.append(parsed)
        except (TypeError, ValueError) as exc:
            errors.append(f"Item {position}: некорректный pubDate {pub_date!r}: {exc}")

        categories = {
            (element.text or "").strip() for element in item.findall("category")
        }
        if "native-yes" not in categories:
            errors.append(f"Item {position}: отсутствует category native-yes.")

        rating = item.find(f"{{{MEDIA_NS}}}rating")
        if rating is None or (rating.text or "").strip() != "nonadult":
            errors.append(f"Item {position}: media:rating должен быть nonadult.")

        enclosure = item.find("enclosure")
        media_content = item.find(f"{{{MEDIA_NS}}}content")
        thumbnail = item.find(f"{{{MEDIA_NS}}}thumbnail")
        if enclosure is None:
            errors.append(f"Item {position}: отсутствует enclosure.")
            continue

        image_url = (enclosure.get("url") or "").strip()
        image_path = local_image_from_url(
            site_dir, image_url, str(config["site_base_url"])
        )
        if image_path is None or not image_path.is_file():
            errors.append(f"Item {position}: изображение не найдено: {image_url}")
            continue

        if enclosure.get("type") != "image/png":
            errors.append(f"Item {position}: enclosure type должен быть image/png.")
        try:
            declared_length = int(enclosure.get("length", ""))
        except ValueError:
            errors.append(f"Item {position}: enclosure length не является числом.")
            declared_length = -1
        actual_length = image_path.stat().st_size
        if declared_length != actual_length:
            errors.append(
                f"Item {position}: enclosure length={declared_length}, "
                f"фактический размер={actual_length}."
            )

        for label, element in (
            ("media:content", media_content),
            ("media:thumbnail", thumbnail),
        ):
            if element is None or element.get("url") != image_url:
                errors.append(f"Item {position}: {label} URL не совпадает с enclosure.")

        try:
            width, height = png_dimensions(image_path)
            if width < int(config["image_width_minimum"]):
                errors.append(
                    f"Item {position}: ширина изображения {width}px меньше минимума."
                )
            if height <= 0:
                errors.append(f"Item {position}: некорректная высота изображения.")
        except RuntimeError as exc:
            errors.append(f"Item {position}: {exc}")

        if link == expected_new_link:
            new_item_found = True
            if title != digest["title"]:
                errors.append("Новый RSS item имеет неверный title.")
            if creator != digest["author"]:
                errors.append("Новый RSS item имеет неверного dc:creator.")
            if normalise_html(source_article) not in normalise_html(content):
                errors.append(
                    "content:encoded нового item не содержит исходный article.html."
                )

    if not new_item_found:
        errors.append("Новый выпуск не найден в RSS.")

    if parsed_dates and parsed_dates != sorted(parsed_dates, reverse=True):
        errors.append("RSS items расположены не по убыванию даты.")

    if f"<h1>{digest['title']}</h1>" not in page_html:
        errors.append("Страница нового выпуска не содержит точный H1.")
    expected_img = f'../images/{digest["cover_filename"]}'
    if expected_img not in page_html:
        errors.append("Страница нового выпуска содержит неверный путь к обложке.")
    if page_html.count(source_article) != 1:
        errors.append(
            "Исходный article.html должен встречаться на странице ровно один раз."
        )

    index_parser = IndexLinkParser()
    index_parser.feed(index_html)
    expected_index_links = [
        relative_index_link(
            (item.findtext("link") or "").strip(),
            str(config["site_base_url"]),
        )
        for item in items
    ]
    if index_parser.links != expected_index_links:
        errors.append(
            "Ссылки index.html не совпадают с порядком RSS: "
            f"actual={index_parser.links}, expected={expected_index_links}"
        )

    try:
        width, height = png_dimensions(new_image_path)
        aspect = width / height
        if abs(aspect - 16 / 9) > 0.03:
            errors.append(
                f"Новая обложка имеет соотношение {aspect:.3f}, ожидалось 16:9."
            )
    except RuntimeError as exc:
        errors.append(str(exc))

    context = {
        "source_dir": str(source_dir.relative_to(ROOT)),
        "site_dir": str(site_dir.relative_to(ROOT)),
        "report_path": str(report_path.relative_to(ROOT)),
        "rss_items": len(items),
        "new_item_link": expected_new_link,
        "new_image": str(new_image_path.relative_to(ROOT)),
        "stories": len(stories),
        "short_digest": bool(digest.get("short_digest")),
        "policy_analysis": policy_analysis,
    }
    return errors, warnings, context


def main() -> int:
    started_at = datetime.now().astimezone()
    try:
        errors, warnings, context = validate()
        report_path = ROOT / context["report_path"]
        report = {
            "status": "ok" if not errors else "error",
            "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "started_at": started_at.isoformat(timespec="seconds"),
            "errors": errors,
            "warnings": warnings,
            **{key: value for key, value in context.items() if key != "report_path"},
        }
        atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")

        if errors:
            print("Site validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1

        print("Site validation passed")
        print(f"RSS items: {context.get('rss_items')}")
        print(f"New item: {context.get('new_item_link')}")
        return 0
    except Exception as exc:
        print(f"Site validation failed unexpectedly: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
