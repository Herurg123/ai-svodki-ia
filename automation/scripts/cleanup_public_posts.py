#!/usr/bin/env python3
"""Prune expired public posts and rebuild every file that links to them."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from build_posts_sitemap import build_sitemap
from build_site import (
    read_existing_items,
    render_index,
    render_rss,
)
from cleanup_repository_content import (
    MINIMUM_RETENTION_DAYS,
    format_bytes,
    markdown_code,
    resolve_reference_date,
    russian_plural,
)
from inject_blogposting_schema import index_graph, inject
from production_daily_common import safe_replace_tree

ROOT = Path(__file__).resolve().parents[2]
POSTS_ROOT = ROOT / "posts"
SITE_CONFIG_PATH = ROOT / "automation" / "config" / "site.json"
STRUCTURED_CONFIG_PATH = ROOT / "automation" / "config" / "structured-data.json"

DATE_NAME = re.compile(r"\d{4}-\d{2}-\d{2}")
IMAGE_NAME = re.compile(r"ai-svodka-(\d{4}-\d{2}-\d{2})\.png")
ITEM_BLOCK = re.compile(r"<item>.*?</item>", re.DOTALL)
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class PublicCleanupError(RuntimeError):
    """Raised when the public cleanup cannot be proven safe."""


@dataclass(frozen=True)
class Publication:
    publication_date: date
    kind: str
    title: str
    link: str
    page_directory: Path
    primary_image: Path
    mirrored_images: tuple[Path, ...]
    item: dict[str, Any]

    @property
    def all_images(self) -> tuple[Path, ...]:
        return (self.primary_image, *self.mirrored_images)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href.strip())


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PublicCleanupError(f"Required JSON file is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicCleanupError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicCleanupError(f"{path} must contain a JSON object")
    return value


def atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def require_regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise PublicCleanupError(f"{label} must be a regular file: {path}")


def require_regular_directory(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise PublicCleanupError(f"{label} must be a regular directory: {path}")


def classify_link(link: str, site_base_url: str) -> tuple[str, date, str]:
    base = site_base_url.rstrip("/")
    parsed_base = urlsplit(base + "/")
    parsed = urlsplit(link)
    if (
        parsed.scheme != parsed_base.scheme
        or parsed.netloc != parsed_base.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise PublicCleanupError(f"RSS item points outside the public posts tree: {link}")

    base_path = parsed_base.path.rstrip("/") + "/"
    if not parsed.path.startswith(base_path):
        raise PublicCleanupError(f"RSS item points outside the public posts path: {link}")
    relative = parsed.path[len(base_path):].strip("/")

    kind = "canonical"
    date_text = relative
    if relative.startswith("dzen-test/"):
        kind = "legacy"
        date_text = relative.removeprefix("dzen-test/")
    if not DATE_NAME.fullmatch(date_text):
        raise PublicCleanupError(f"RSS item has an unsupported dated path: {link}")

    expected = f"{base}/{relative}/"
    if link != expected:
        raise PublicCleanupError(
            f"RSS item must use the canonical trailing-slash URL: {link}"
        )
    try:
        publication_date = date.fromisoformat(date_text)
    except ValueError as exc:
        raise PublicCleanupError(f"RSS item has an invalid date: {link}") from exc
    return kind, publication_date, relative


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def dated_page_directories(posts_root: Path) -> set[Path]:
    result: set[Path] = set()
    for parent in (posts_root, posts_root / "dzen-test"):
        require_regular_directory(parent, "Dated posts parent")
        for child in parent.iterdir():
            if not DATE_NAME.fullmatch(child.name):
                continue
            require_regular_directory(child, "Dated post directory")
            result.add(child)
    return result


def dated_images(posts_root: Path) -> set[Path]:
    result: set[Path] = set()
    for parent in (posts_root / "images", posts_root / "dzen-test" / "images"):
        require_regular_directory(parent, "Post images directory")
        for child in parent.iterdir():
            if not IMAGE_NAME.fullmatch(child.name):
                continue
            require_regular_file(child, "Dated post image")
            result.add(child)
    return result


def parse_index_links(path: Path) -> list[str]:
    require_regular_file(path, "Posts index")
    parser = LinkParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.links


def validate_root_index(
    path: Path,
    publications: list[Publication],
    site_base_url: str,
) -> None:
    article_links = [
        value
        for value in parse_index_links(path)
        if re.fullmatch(
            r"\./(?:dzen-test/)?\d{4}-\d{2}-\d{2}/",
            value,
        )
    ]
    base = site_base_url.rstrip("/") + "/"
    expected = ["./" + publication.link.removeprefix(base) for publication in publications]
    if article_links != expected:
        raise PublicCleanupError(
            "posts/index.html links do not exactly match the ordered root RSS items"
        )


def validate_sitemap(
    path: Path,
    publications: list[Publication],
    site_base_url: str,
) -> None:
    require_regular_file(path, "Posts sitemap")
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise PublicCleanupError(f"Posts sitemap is invalid XML: {exc}") from exc
    actual = [
        (node.text or "").strip()
        for node in root.findall("s:url/s:loc", SITEMAP_NS)
    ]
    expected = [site_base_url.rstrip("/") + "/"] + [
        publication.link for publication in publications
    ]
    if actual != expected:
        raise PublicCleanupError(
            "posts/sitemap.xml URLs do not exactly match the ordered root RSS items"
        )


def validate_dzen_package(
    posts_root: Path,
    publications: list[Publication],
    site_base_url: str,
) -> None:
    dzen_root = posts_root / "dzen-test"
    rss_path = dzen_root / "rss.xml"
    index_path = dzen_root / "index.html"
    require_regular_file(rss_path, "Legacy RSS")
    require_regular_file(index_path, "Legacy index")

    try:
        channel = ET.parse(rss_path).getroot().find("channel")
    except ET.ParseError as exc:
        raise PublicCleanupError(f"Legacy RSS is invalid XML: {exc}") from exc
    if channel is None:
        raise PublicCleanupError("Legacy RSS channel is missing")

    legacy = [publication for publication in publications if publication.kind == "legacy"]
    expected_links = [publication.link for publication in legacy]
    actual_links: list[str] = []
    for position, item in enumerate(channel.findall("item"), start=1):
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        enclosure = item.find("enclosure")
        image_url = enclosure.get("url", "").strip() if enclosure is not None else ""
        if not link or guid != link or not pub_date or not image_url:
            raise PublicCleanupError(f"Legacy RSS item {position} is incomplete")
        kind, item_date, _ = classify_link(link, site_base_url)
        if kind != "legacy":
            raise PublicCleanupError(f"Legacy RSS contains a canonical item: {link}")
        if item_date.isoformat() not in image_url:
            raise PublicCleanupError(
                f"Legacy RSS image does not match its publication date: {link}"
            )
        actual_links.append(link)
    if actual_links != expected_links:
        raise PublicCleanupError(
            "posts/dzen-test/rss.xml does not exactly match legacy items in root RSS"
        )

    index_links = [
        link
        for link in parse_index_links(index_path)
        if re.fullmatch(
            re.escape(site_base_url.rstrip("/"))
            + r"/dzen-test/\d{4}-\d{2}-\d{2}/",
            link,
        )
    ]
    if index_links != expected_links:
        raise PublicCleanupError(
            "posts/dzen-test/index.html does not exactly match legacy RSS items"
        )


def inspect_site(
    posts_root: Path,
    *,
    site_config: dict[str, Any],
    timezone_name: str,
) -> list[Publication]:
    require_regular_directory(posts_root, "Posts root")
    rss_path = posts_root / "rss.xml"
    index_path = posts_root / "index.html"
    sitemap_path = posts_root / "sitemap.xml"
    for path, label in (
        (rss_path, "Root RSS"),
        (index_path, "Root index"),
        (sitemap_path, "Root sitemap"),
    ):
        require_regular_file(path, label)

    try:
        zone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise PublicCleanupError(f"Unknown timezone: {timezone_name!r}") from exc

    try:
        items, _ = read_existing_items(rss_path)
        root = ET.parse(rss_path).getroot()
    except (RuntimeError, ET.ParseError) as exc:
        raise PublicCleanupError(f"Cannot parse root RSS: {exc}") from exc
    channel = root.find("channel")
    if channel is None:
        raise PublicCleanupError("Root RSS channel is missing")
    nodes = channel.findall("item")
    if len(nodes) != len(items):
        raise PublicCleanupError("Root RSS parser produced inconsistent item counts")

    site_base_url = str(site_config["site_base_url"]).rstrip("/")
    image_template = str(
        site_config.get("image_filename_template", "ai-svodka-{date}.png")
    )
    publications: list[Publication] = []
    seen_dates: set[date] = set()

    for position, (item, node) in enumerate(zip(items, nodes), start=1):
        link = str(item["link"])
        kind, publication_date, relative = classify_link(link, site_base_url)
        local_date = item["published_datetime"].astimezone(zone).date()
        if local_date != publication_date:
            raise PublicCleanupError(
                f"Root RSS item {position} URL date {publication_date} "
                f"does not match pubDate {local_date}"
            )
        if publication_date in seen_dates:
            raise PublicCleanupError(
                f"Root RSS has more than one item for {publication_date}"
            )
        seen_dates.add(publication_date)

        guid = (node.findtext("guid") or "").strip()
        if guid != link:
            raise PublicCleanupError(f"Root RSS guid differs from link: {link}")
        enclosure = node.find("enclosure")
        enclosure_url = (
            enclosure.get("url", "").strip()
            if enclosure is not None
            else ""
        )

        image_name = image_template.format(date=publication_date.isoformat())
        if kind == "legacy":
            expected_image_url = (
                f"{site_base_url}/dzen-test/images/{image_name}"
            )
            primary_image = posts_root / "dzen-test" / "images" / image_name
            mirrored_images = (posts_root / "images" / image_name,)
        else:
            expected_image_url = f"{site_base_url}/images/{image_name}"
            primary_image = posts_root / "images" / image_name
            mirrored_images = ()
        if enclosure_url != expected_image_url or str(item["image_url"]) != expected_image_url:
            raise PublicCleanupError(
                f"Root RSS image URL does not match {publication_date}: "
                f"{enclosure_url!r}"
            )

        page_directory = posts_root / relative
        require_regular_directory(page_directory, "Publication directory")
        require_regular_file(page_directory / "index.html", "Publication page")
        require_regular_file(primary_image, "Publication image")
        for mirror in mirrored_images:
            require_regular_file(mirror, "Mirrored legacy image")

        publications.append(
            Publication(
                publication_date=publication_date,
                kind=kind,
                title=str(item["title"]),
                link=link,
                page_directory=page_directory,
                primary_image=primary_image,
                mirrored_images=mirrored_images,
                item=item,
            )
        )

    if not publications:
        raise PublicCleanupError(
            "Root RSS contains no items; automatic pruning refuses to guess "
            "how production should resume"
        )

    expected_pages = {publication.page_directory for publication in publications}
    actual_pages = dated_page_directories(posts_root)
    if actual_pages != expected_pages:
        missing = sorted(relative_path(path, posts_root) for path in expected_pages - actual_pages)
        orphaned = sorted(relative_path(path, posts_root) for path in actual_pages - expected_pages)
        raise PublicCleanupError(
            f"Dated post directories disagree with RSS; missing={missing}, "
            f"orphaned={orphaned}"
        )

    expected_images = {
        image
        for publication in publications
        for image in publication.all_images
    }
    actual_images = dated_images(posts_root)
    if actual_images != expected_images:
        missing = sorted(relative_path(path, posts_root) for path in expected_images - actual_images)
        orphaned = sorted(relative_path(path, posts_root) for path in actual_images - expected_images)
        raise PublicCleanupError(
            f"Dated post images disagree with RSS; missing={missing}, "
            f"orphaned={orphaned}"
        )

    validate_root_index(index_path, publications, site_base_url)
    validate_sitemap(sitemap_path, publications, site_base_url)
    validate_dzen_package(posts_root, publications, site_base_url)
    return publications


def regular_files(path: Path) -> list[Path]:
    if path.is_symlink():
        raise PublicCleanupError(f"Cleanup target must not be a symlink: {path}")
    if path.is_file():
        return [path]
    require_regular_directory(path, "Cleanup target")
    files: list[Path] = []
    for child in sorted(path.rglob("*")):
        if child.is_symlink():
            raise PublicCleanupError(f"Cleanup target contains a symlink: {child}")
        if child.is_file():
            files.append(child)
    return files


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_files(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PublicCleanupError(f"Posts tree contains a symlink: {path}")
        if path.is_file():
            result[relative_path(path, root)] = file_digest(path)
    return result


def tree_changes(before: dict[str, str], after: dict[str, str]) -> dict[str, str]:
    changes: dict[str, str] = {}
    for path in sorted(before.keys() | after.keys()):
        if path not in after:
            changes[path] = "D"
        elif path not in before:
            changes[path] = "A"
        elif before[path] != after[path]:
            changes[path] = "M"
    return changes


def remove_publication(publication: Publication, posts_root: Path) -> None:
    page = publication.page_directory
    require_regular_directory(page, "Publication directory")
    shutil.rmtree(page)
    for image in publication.all_images:
        require_regular_file(image, "Publication image")
        image.unlink()


def filter_legacy_rss(
    path: Path,
    *,
    retained_links: set[str],
    reference_date: date,
    retention_days: int,
    timezone_name: str,
) -> None:
    text_value = path.read_text(encoding="utf-8")
    matches = list(ITEM_BLOCK.finditer(text_value))
    try:
        channel = ET.fromstring(text_value).find("channel")
    except ET.ParseError as exc:
        raise PublicCleanupError(f"Legacy RSS is invalid XML: {exc}") from exc
    if channel is None:
        raise PublicCleanupError("Legacy RSS channel is missing")
    nodes = channel.findall("item")
    if len(matches) != len(nodes):
        raise PublicCleanupError(
            "Legacy RSS item blocks cannot be mapped safely to parsed items"
        )

    links = [(node.findtext("link") or "").strip() for node in nodes]
    retained_blocks = [
        match.group(0)
        for link, match in zip(links, matches)
        if link in retained_links
    ]
    retained_nodes = [
        node for link, node in zip(links, nodes)
        if link in retained_links
    ]

    if matches:
        prefix = text_value[:matches[0].start()]
        suffix = text_value[matches[-1].end():]
    else:
        prefix = text_value
        suffix = ""

    description = (
        "Полнотекстовые аналитические статьи об искусственном интеллекте "
        f"не старше {retention_days} дней."
    )
    prefix, replaced = re.subn(
        r"<description>.*?</description>",
        f"<description>{html.escape(description)}</description>",
        prefix,
        count=1,
        flags=re.DOTALL,
    )
    if replaced != 1:
        raise PublicCleanupError("Legacy RSS channel description is missing")

    if retained_nodes:
        latest_pub_date = (
            retained_nodes[0].findtext("pubDate") or ""
        ).strip()
        latest_enclosure = retained_nodes[0].find("enclosure")
        latest_image = (
            latest_enclosure.get("url", "").strip()
            if latest_enclosure is not None
            else ""
        )
        if not latest_pub_date or not latest_image:
            raise PublicCleanupError("Latest retained legacy RSS item is incomplete")
        image_block = (
            f"<image><url>{html.escape(latest_image)}</url>"
            "<title>ИИ-Сводки</title>"
            "<link>https://rybalka.one/posts/dzen-test/</link></image>"
        )
    else:
        zone = ZoneInfo(timezone_name)
        latest_pub_date = format_datetime(
            datetime.combine(reference_date, time.min, tzinfo=zone)
        )
        image_block = ""

    prefix, replaced = re.subn(
        r"<lastBuildDate>.*?</lastBuildDate>",
        f"<lastBuildDate>{html.escape(latest_pub_date)}</lastBuildDate>",
        prefix,
        count=1,
        flags=re.DOTALL,
    )
    if replaced != 1:
        raise PublicCleanupError("Legacy RSS lastBuildDate is missing")
    prefix, replaced = re.subn(
        r"<image>.*?</image>",
        image_block,
        prefix,
        count=1,
        flags=re.DOTALL,
    )
    if replaced != 1:
        raise PublicCleanupError("Legacy RSS channel image block is missing")

    rendered = prefix + "".join(retained_blocks) + suffix
    try:
        ET.fromstring(rendered)
    except ET.ParseError as exc:
        raise PublicCleanupError(
            f"Filtered legacy RSS would be invalid XML: {exc}"
        ) from exc
    atomic_write(path, rendered)


def render_legacy_index(
    publications: list[Publication],
    *,
    retention_days: int,
) -> str:
    items = "".join(
        "<li>"
        f'<a href="{html.escape(publication.link, quote=True)}">'
        f"{html.escape(publication.title)}</a>"
        "</li>"
        for publication in publications
    )
    count = len(publications)
    if count:
        status = (
            f"<strong>{count} "
            f"{russian_plural(count, 'актуальная статья', 'актуальные статьи', 'актуальных статей')}"
            f":</strong> публикации не старше {retention_days} дней."
        )
        listing = f"<ul>{items}</ul>"
    else:
        status = (
            f"Актуальных статей не старше {retention_days} дней сейчас нет."
        )
        listing = ""
    return (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="index,follow,max-image-preview:large">'
        '<link rel="canonical" href="https://rybalka.one/posts/dzen-test/">'
        "<title>ИИ-Сводки для Дзена</title>"
        "<style>body{font-family:Arial,sans-serif;line-height:1.65;"
        "max-width:920px;margin:auto;padding:24px;background:#0f172a;"
        "color:#e5e7eb}article{background:#111827;padding:30px;"
        "border-radius:16px}a{color:#7dd3fc}</style></head><body><article>"
        f"<h1>ИИ-Сводки для Дзена</h1><p>{status}</p>{listing}"
        '<p><a href="https://rybalka.one/posts/dzen-test/rss.xml">'
        "RSS-лента</a></p></article></body></html>\n"
    )


def build_candidate(
    live_posts: Path,
    candidate_posts: Path,
    *,
    publications: list[Publication],
    expired: list[Publication],
    reference_date: date,
    retention_days: int,
    timezone_name: str,
    site_config: dict[str, Any],
    structured_config: dict[str, Any],
) -> None:
    shutil.copytree(live_posts, candidate_posts)
    expired_dates = {publication.publication_date for publication in expired}
    retained = [
        publication
        for publication in publications
        if publication.publication_date not in expired_dates
    ]
    if not retained:
        raise PublicCleanupError(
            "Retention would remove every root RSS item; refusing to break "
            "the production restart path"
        )

    retained_items = [publication.item for publication in retained]
    _, channel_data = read_existing_items(live_posts / "rss.xml")
    atomic_write(
        candidate_posts / "rss.xml",
        render_rss(site_config, channel_data, retained_items, candidate_posts),
    )
    atomic_write(
        candidate_posts / "index.html",
        render_index(site_config, retained_items),
    )
    inject(
        candidate_posts / "index.html",
        index_graph(
            config=structured_config,
            rss_path=candidate_posts / "rss.xml",
        ),
        str(structured_config["blog_url"]),
        str(structured_config["feed_url"]),
    )

    expired_legacy = [
        publication for publication in expired
        if publication.kind == "legacy"
    ]
    if expired_legacy:
        retained_legacy = [
            publication for publication in retained
            if publication.kind == "legacy"
        ]
        filter_legacy_rss(
            candidate_posts / "dzen-test" / "rss.xml",
            retained_links={publication.link for publication in retained_legacy},
            reference_date=reference_date,
            retention_days=retention_days,
            timezone_name=timezone_name,
        )
        atomic_write(
            candidate_posts / "dzen-test" / "index.html",
            render_legacy_index(
                retained_legacy,
                retention_days=retention_days,
            ),
        )

    for publication in expired:
        candidate_publication = Publication(
            publication_date=publication.publication_date,
            kind=publication.kind,
            title=publication.title,
            link=publication.link,
            page_directory=(
                candidate_posts
                / publication.page_directory.relative_to(live_posts)
            ),
            primary_image=(
                candidate_posts
                / publication.primary_image.relative_to(live_posts)
            ),
            mirrored_images=tuple(
                candidate_posts / image.relative_to(live_posts)
                for image in publication.mirrored_images
            ),
            item=publication.item,
        )
        remove_publication(candidate_publication, candidate_posts)

    build_sitemap(
        rss=candidate_posts / "rss.xml",
        posts_root=candidate_posts,
        output=candidate_posts / "sitemap.xml",
        base_url=str(site_config["site_base_url"]),
        reference_date=reference_date,
    )
    retained_after = inspect_site(
        candidate_posts,
        site_config=site_config,
        timezone_name=timezone_name,
    )
    cutoff_date = reference_date - timedelta(days=retention_days)
    stale = [
        publication.publication_date.isoformat()
        for publication in retained_after
        if publication.publication_date < cutoff_date
    ]
    if stale:
        raise PublicCleanupError(
            f"Candidate site still contains expired publications: {stale}"
        )


def run_cleanup(
    posts_root: Path,
    *,
    site_config: dict[str, Any],
    structured_config: dict[str, Any],
    reference_date: date,
    retention_days: int,
    timezone_name: str,
    apply: bool,
) -> dict[str, Any]:
    if retention_days < MINIMUM_RETENTION_DAYS:
        raise PublicCleanupError(
            f"retention_days must be at least {MINIMUM_RETENTION_DAYS}"
        )
    publications = inspect_site(
        posts_root,
        site_config=site_config,
        timezone_name=timezone_name,
    )
    cutoff_date = reference_date - timedelta(days=retention_days)
    expired = [
        publication
        for publication in publications
        if publication.publication_date < cutoff_date
    ]
    before_files = tree_files(posts_root)

    details: list[dict[str, Any]] = []
    removed_files: set[Path] = set()
    removed_bytes = 0
    for publication in expired:
        publication_files: set[Path] = set()
        for target in (publication.page_directory, *publication.all_images):
            publication_files.update(regular_files(target))
        files_size = sum(path.stat().st_size for path in publication_files)
        removed_files.update(publication_files)
        removed_bytes += files_size
        details.append(
            {
                "publication_date": publication.publication_date.isoformat(),
                "kind": publication.kind,
                "link": publication.link,
                "page_directory": relative_path(
                    publication.page_directory,
                    posts_root,
                ),
                "images": [
                    relative_path(image, posts_root)
                    for image in publication.all_images
                ],
                "removed_files": len(publication_files),
                "removed_bytes": files_size,
            }
        )

    changes: dict[str, str] = {}
    updated_files: list[str] = []
    if expired:
        with tempfile.TemporaryDirectory(
            dir=posts_root.parent,
            prefix=".public-cleanup-",
        ) as temp:
            candidate = Path(temp) / "posts"
            build_candidate(
                posts_root,
                candidate,
                publications=publications,
                expired=expired,
                reference_date=reference_date,
                retention_days=retention_days,
                timezone_name=timezone_name,
                site_config=site_config,
                structured_config=structured_config,
            )
            after_files = tree_files(candidate)
            changes = tree_changes(before_files, after_files)
            if any(status == "A" for status in changes.values()):
                raise PublicCleanupError(
                    f"Public cleanup may not add files: {changes}"
                )

            expected_deleted = {
                relative_path(path, posts_root)
                for path in removed_files
            }
            actual_deleted = {
                path for path, status in changes.items()
                if status == "D"
            }
            if actual_deleted != expected_deleted:
                raise PublicCleanupError(
                    "Candidate deleted an unexpected file set; "
                    f"expected={sorted(expected_deleted)}, "
                    f"actual={sorted(actual_deleted)}"
                )

            expected_modified = {
                "index.html",
                "rss.xml",
                "sitemap.xml",
            }
            if any(publication.kind == "legacy" for publication in expired):
                expected_modified.update(
                    {
                        "dzen-test/index.html",
                        "dzen-test/rss.xml",
                    }
                )
            actual_modified = {
                path for path, status in changes.items()
                if status == "M"
            }
            if actual_modified != expected_modified:
                raise PublicCleanupError(
                    "Candidate modified an unexpected file set; "
                    f"expected={sorted(expected_modified)}, "
                    f"actual={sorted(actual_modified)}"
                )
            updated_files = sorted(expected_modified)

            if apply:
                safe_replace_tree(candidate, posts_root)
                applied_files = tree_files(posts_root)
                if applied_files != after_files:
                    raise PublicCleanupError(
                        "Applied posts tree differs from the validated candidate"
                    )

    legacy_before = sum(
        1 for publication in publications
        if publication.kind == "legacy"
    )
    legacy_expired = sum(
        1 for publication in expired
        if publication.kind == "legacy"
    )
    return {
        "status": "ok",
        "mode": "apply" if apply else "dry-run",
        "timezone": timezone_name,
        "reference_date": reference_date.isoformat(),
        "retention_days": retention_days,
        "cutoff_date": cutoff_date.isoformat(),
        "deletion_rule": "publication_date < cutoff_date",
        "rss_items_before": len(publications),
        "rss_items_after": len(publications) - len(expired),
        "legacy_items_before": legacy_before,
        "legacy_items_after": legacy_before - legacy_expired,
        "expired_releases": details,
        "removed_directories": len(expired),
        "removed_files": len(removed_files),
        "removed_bytes": removed_bytes,
        "updated_files": updated_files,
        "expected_git_changes": [
            {"path": path, "status": status}
            for path, status in sorted(changes.items())
        ],
        "changes_planned": bool(expired),
        "changes_applied": bool(expired) and apply,
    }


def render_github_summary(
    report: dict[str, Any] | None,
    *,
    cleanup_outcome: str,
    validation_outcome: str,
    commit_outcome: str,
) -> str:
    lines = ["# Публичные страницы, RSS и FTP", ""]
    if cleanup_outcome != "success" or report is None:
        return "\n".join(
            lines
            + [
                "❌ Проверка публичного контента не завершилась.",
                "",
                "RSS, `index.html` и FTP этим запуском не актуализированы. "
                "Причину смотри в шагах workflow.",
                "",
            ]
        )

    mode = str(report["mode"])
    planned = bool(report["changes_planned"])
    published = (
        mode == "apply"
        and planned
        and validation_outcome == "success"
        and commit_outcome == "success"
    )
    if mode == "dry-run":
        headline = (
            "🟡 Найдены просроченные публичные выпуски, но это ручной dry-run."
            if planned
            else "✅ Просроченных публичных выпусков нет."
        )
        result = "не удалено (dry-run)"
    elif not planned:
        headline = "✅ Публичные страницы и RSS уже актуальны."
        result = "не требовалось"
    elif published:
        headline = (
            "✅ Публичная очистка записана в `main`; "
            "точный commit передан FTP-синхронизации."
        )
        result = "удалено из GitHub"
    elif validation_outcome == "failure":
        headline = (
            "❌ Просроченный контент найден, но проверка безопасности не прошла. "
            "`main` и FTP не изменены."
        )
        result = "не опубликовано"
    elif commit_outcome == "failure":
        headline = (
            "❌ Просроченный контент найден, но commit/push не завершился. "
            "FTP-синхронизация не запущена."
        )
        result = "не опубликовано"
    else:
        headline = (
            "⚠️ Просроченный контент найден, но изменения не опубликованы."
        )
        result = "не опубликовано"

    lines.extend(
        [
            headline,
            "",
            (
                f"- Граница: удаляются только выпуски **раньше "
                f"{report['cutoff_date']}**; эта дата и всё новее сохраняются."
            ),
            (
                f"- RSS: **{report['rss_items_before']} → "
                f"{report['rss_items_after']}** актуальных ссылок."
            ),
            (
                f"- Legacy RSS: **{report['legacy_items_before']} → "
                f"{report['legacy_items_after']}** ссылок."
            ),
            (
                f"- Найдено к удалению: **{report['removed_directories']} "
                f"{russian_plural(int(report['removed_directories']), 'выпуск', 'выпуска', 'выпусков')}**, "
                f"**{report['removed_files']} "
                f"{russian_plural(int(report['removed_files']), 'файл', 'файла', 'файлов')}**, "
                f"**{format_bytes(int(report['removed_bytes']))}**."
            ),
            "",
        ]
    )

    details = report["expired_releases"]
    if details:
        lines.extend(
            [
                "## Что найдено",
                "",
                "| Дата | Тип | Страница | Изображения | Файлов | Объём | Итог |",
                "|---|---|---|---|---:|---:|---|",
            ]
        )
        for detail in details:
            images = "<br>".join(
                markdown_code(path) for path in detail["images"]
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(detail["publication_date"]),
                        (
                            "legacy"
                            if detail["kind"] == "legacy"
                            else "обычный"
                        ),
                        markdown_code(str(detail["page_directory"]) + "/"),
                        images,
                        str(detail["removed_files"]),
                        format_bytes(int(detail["removed_bytes"])),
                        result,
                    ]
                )
                + " |"
            )
        lines.append("")
        updated = ", ".join(
            markdown_code(path) for path in report["updated_files"]
        )
        lines.extend(
            [
                "## Что актуализировано",
                "",
                f"- Связанные файлы: {updated}.",
                "- В них остаются только ссылки на выпуски не старше "
                f"{report['retention_days']} дней.",
                "- FTP удаляет те же страницы и изображения только после "
                "успешного commit; итог синхронизации указан в финальном job.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Удаляемых страниц и изображений нет; RSS, индексы и sitemap "
                "не переписывались.",
                "",
            ]
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prune public posts older than the retention window and rebuild "
            "RSS, indexes, and sitemap. Dry-run is the default."
        )
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=MINIMUM_RETENTION_DAYS,
    )
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--reference-date")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        reference_date = resolve_reference_date(
            args.reference_date,
            args.timezone,
        )
        report = run_cleanup(
            POSTS_ROOT,
            site_config=read_json(SITE_CONFIG_PATH),
            structured_config=read_json(STRUCTURED_CONFIG_PATH),
            reference_date=reference_date,
            retention_days=args.retention_days,
            timezone_name=args.timezone,
            apply=args.apply,
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"Public posts cleanup failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
