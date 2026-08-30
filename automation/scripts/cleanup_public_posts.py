#!/usr/bin/env python3
"""Prune expired canonical public posts and rebuild files that link to them."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from build_posts_sitemap import build_sitemap
from build_site import read_existing_items, render_index, render_rss
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
SITE_CONFIG_PATH = ROOT / "automation/config/site.json"
STRUCTURED_CONFIG_PATH = ROOT / "automation/config/structured-data.json"
DATE_NAME = re.compile(r"\d{4}-\d{2}-\d{2}")
IMAGE_NAME = re.compile(r"ai-svodka-(\d{4}-\d{2}-\d{2})\.png")
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
RETIRED_SHELL = {"index.html", "rss.xml"}


class PublicCleanupError(RuntimeError):
    """Raised when public cleanup cannot be proven safe."""


@dataclass(frozen=True)
class Publication:
    publication_date: date
    title: str
    link: str
    page_directory: Path
    primary_image: Path
    item: dict[str, Any]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() == "a":
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


def require_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise PublicCleanupError(f"{label} must be a regular file: {path}")


def require_dir(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise PublicCleanupError(f"{label} must be a regular directory: {path}")


def validate_retired_shell(posts_root: Path) -> None:
    """Permit only the two inert dzen-test shell files during stage 7A."""
    root = posts_root / "dzen-test"
    if not root.exists() and not root.is_symlink():
        return
    require_dir(root, "Retired dzen-test shell")
    entries = list(root.iterdir())
    actual = {entry.name for entry in entries}
    if actual != RETIRED_SHELL:
        raise PublicCleanupError(
            "Retired dzen-test shell must stay inert; "
            f"unexpected={sorted(actual - RETIRED_SHELL)}, "
            f"missing={sorted(RETIRED_SHELL - actual)}"
        )
    for entry in entries:
        require_file(entry, "Retired dzen-test shell file")


def classify_link(link: str, site_base_url: str) -> tuple[date, str]:
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
    if not DATE_NAME.fullmatch(relative):
        raise PublicCleanupError(
            f"RSS item has an unsupported non-canonical dated path: {link}"
        )
    if link != f"{base}/{relative}/":
        raise PublicCleanupError(
            f"RSS item must use the canonical trailing-slash URL: {link}"
        )
    try:
        return date.fromisoformat(relative), relative
    except ValueError as exc:
        raise PublicCleanupError(f"RSS item has an invalid date: {link}") from exc


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def dated_pages(posts_root: Path) -> set[Path]:
    result: set[Path] = set()
    for child in posts_root.iterdir():
        if DATE_NAME.fullmatch(child.name):
            require_dir(child, "Dated post directory")
            result.add(child)
    return result


def dated_images(posts_root: Path) -> set[Path]:
    root = posts_root / "images"
    require_dir(root, "Post images directory")
    result: set[Path] = set()
    for child in root.iterdir():
        if IMAGE_NAME.fullmatch(child.name):
            require_file(child, "Dated post image")
            result.add(child)
    return result


def parse_links(path: Path) -> list[str]:
    require_file(path, "Posts index")
    parser = LinkParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.links


def validate_index(
    path: Path, publications: list[Publication], site_base_url: str
) -> None:
    actual = [
        link for link in parse_links(path)
        if re.fullmatch(r"\./(?:dzen-test/)?\d{4}-\d{2}-\d{2}/", link)
    ]
    base = site_base_url.rstrip("/") + "/"
    expected = ["./" + publication.link.removeprefix(base) for publication in publications]
    if actual != expected:
        raise PublicCleanupError(
            "posts/index.html links do not exactly match the ordered root RSS items"
        )


def validate_sitemap(
    path: Path, publications: list[Publication], site_base_url: str
) -> None:
    require_file(path, "Posts sitemap")
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise PublicCleanupError(f"Posts sitemap is invalid XML: {exc}") from exc
    actual = [(node.text or "").strip() for node in root.findall("s:url/s:loc", SITEMAP_NS)]
    expected = [site_base_url.rstrip("/") + "/"] + [
        publication.link for publication in publications
    ]
    if actual != expected:
        raise PublicCleanupError(
            "posts/sitemap.xml URLs do not exactly match the ordered root RSS items"
        )


def inspect_site(
    posts_root: Path,
    *,
    site_config: dict[str, Any],
    timezone_name: str,
) -> list[Publication]:
    require_dir(posts_root, "Posts root")
    validate_retired_shell(posts_root)
    rss_path = posts_root / "rss.xml"
    index_path = posts_root / "index.html"
    sitemap_path = posts_root / "sitemap.xml"
    for path, label in (
        (rss_path, "Root RSS"),
        (index_path, "Root index"),
        (sitemap_path, "Root sitemap"),
    ):
        require_file(path, label)
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

    base = str(site_config["site_base_url"]).rstrip("/")
    image_template = str(
        site_config.get("image_filename_template", "ai-svodka-{date}.png")
    )
    publications: list[Publication] = []
    seen_dates: set[date] = set()
    for position, (item, node) in enumerate(zip(items, nodes), start=1):
        link = str(item["link"])
        publication_date, relative = classify_link(link, base)
        local_date = item["published_datetime"].astimezone(zone).date()
        if local_date != publication_date:
            raise PublicCleanupError(
                f"Root RSS item {position} URL date {publication_date} "
                f"does not match pubDate {local_date}"
            )
        if publication_date in seen_dates:
            raise PublicCleanupError(f"Root RSS has more than one item for {publication_date}")
        seen_dates.add(publication_date)
        if (node.findtext("guid") or "").strip() != link:
            raise PublicCleanupError(f"Root RSS guid differs from link: {link}")
        enclosure = node.find("enclosure")
        enclosure_url = enclosure.get("url", "").strip() if enclosure is not None else ""
        image_name = image_template.format(date=publication_date.isoformat())
        image_url = f"{base}/images/{image_name}"
        image_path = posts_root / "images" / image_name
        if enclosure_url != image_url or str(item["image_url"]) != image_url:
            raise PublicCleanupError(
                f"Root RSS image URL does not match {publication_date}: {enclosure_url!r}"
            )
        page = posts_root / relative
        require_dir(page, "Publication directory")
        require_file(page / "index.html", "Publication page")
        require_file(image_path, "Publication image")
        publications.append(
            Publication(
                publication_date=publication_date,
                title=str(item["title"]),
                link=link,
                page_directory=page,
                primary_image=image_path,
                item=item,
            )
        )

    if not publications:
        raise PublicCleanupError(
            "Root RSS contains no items; automatic pruning refuses to guess "
            "how production should resume"
        )
    expected_pages = {publication.page_directory for publication in publications}
    actual_pages = dated_pages(posts_root)
    if actual_pages != expected_pages:
        raise PublicCleanupError(
            "Dated post directories disagree with RSS; "
            f"missing={sorted(relative_path(p, posts_root) for p in expected_pages - actual_pages)}, "
            f"orphaned={sorted(relative_path(p, posts_root) for p in actual_pages - expected_pages)}"
        )
    expected_images = {publication.primary_image for publication in publications}
    actual_images = dated_images(posts_root)
    if actual_images != expected_images:
        raise PublicCleanupError(
            "Dated post images disagree with RSS; "
            f"missing={sorted(relative_path(p, posts_root) for p in expected_images - actual_images)}, "
            f"orphaned={sorted(relative_path(p, posts_root) for p in actual_images - expected_images)}"
        )
    validate_index(index_path, publications, base)
    validate_sitemap(sitemap_path, publications, base)
    return publications


def regular_files(path: Path) -> list[Path]:
    if path.is_symlink():
        raise PublicCleanupError(f"Cleanup target must not be a symlink: {path}")
    if path.is_file():
        return [path]
    require_dir(path, "Cleanup target")
    files: list[Path] = []
    for child in sorted(path.rglob("*")):
        if child.is_symlink():
            raise PublicCleanupError(f"Cleanup target contains a symlink: {child}")
        if child.is_file():
            files.append(child)
    return files


def tree_files(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PublicCleanupError(f"Posts tree contains a symlink: {path}")
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[relative_path(path, root)] = digest
    return result


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
        publication for publication in publications
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
    atomic_write(candidate_posts / "index.html", render_index(site_config, retained_items))
    inject(
        candidate_posts / "index.html",
        index_graph(
            config=structured_config,
            rss_path=candidate_posts / "rss.xml",
        ),
        str(structured_config["blog_url"]),
        str(structured_config["feed_url"]),
    )
    for publication in expired:
        page = candidate_posts / publication.page_directory.relative_to(live_posts)
        image = candidate_posts / publication.primary_image.relative_to(live_posts)
        require_dir(page, "Publication directory")
        shutil.rmtree(page)
        require_file(image, "Publication image")
        image.unlink()
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
    cutoff = reference_date - timedelta(days=retention_days)
    stale = [
        publication.publication_date.isoformat()
        for publication in retained_after
        if publication.publication_date < cutoff
    ]
    if stale:
        raise PublicCleanupError(f"Candidate site still contains expired publications: {stale}")


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
    cutoff = reference_date - timedelta(days=retention_days)
    expired = [
        publication for publication in publications
        if publication.publication_date < cutoff
    ]
    before = tree_files(posts_root)
    details: list[dict[str, Any]] = []
    removed_files: set[Path] = set()
    removed_bytes = 0
    for publication in expired:
        files: set[Path] = set()
        files.update(regular_files(publication.page_directory))
        files.update(regular_files(publication.primary_image))
        size = sum(path.stat().st_size for path in files)
        removed_files.update(files)
        removed_bytes += size
        details.append(
            {
                "publication_date": publication.publication_date.isoformat(),
                "link": publication.link,
                "page_directory": relative_path(publication.page_directory, posts_root),
                "images": [relative_path(publication.primary_image, posts_root)],
                "removed_files": len(files),
                "removed_bytes": size,
            }
        )

    changes: dict[str, str] = {}
    updated_files: list[str] = []
    if expired:
        with tempfile.TemporaryDirectory(
            dir=posts_root.parent, prefix=".public-cleanup-"
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
            after = tree_files(candidate)
            for path in sorted(before.keys() | after.keys()):
                if path not in after:
                    changes[path] = "D"
                elif path not in before:
                    changes[path] = "A"
                elif before[path] != after[path]:
                    changes[path] = "M"
            if any(status == "A" for status in changes.values()):
                raise PublicCleanupError(f"Public cleanup may not add files: {changes}")
            expected_deleted = {
                relative_path(path, posts_root) for path in removed_files
            }
            actual_deleted = {
                path for path, status in changes.items() if status == "D"
            }
            if actual_deleted != expected_deleted:
                raise PublicCleanupError(
                    "Candidate deleted an unexpected file set; "
                    f"expected={sorted(expected_deleted)}, actual={sorted(actual_deleted)}"
                )
            expected_modified = {"index.html", "rss.xml", "sitemap.xml"}
            actual_modified = {
                path for path, status in changes.items() if status == "M"
            }
            if actual_modified != expected_modified:
                raise PublicCleanupError(
                    "Candidate modified an unexpected file set; "
                    f"expected={sorted(expected_modified)}, actual={sorted(actual_modified)}"
                )
            updated_files = sorted(expected_modified)
            if apply:
                safe_replace_tree(candidate, posts_root)
                if tree_files(posts_root) != after:
                    raise PublicCleanupError(
                        "Applied posts tree differs from the validated candidate"
                    )

    return {
        "status": "ok",
        "mode": "apply" if apply else "dry-run",
        "timezone": timezone_name,
        "reference_date": reference_date.isoformat(),
        "retention_days": retention_days,
        "cutoff_date": cutoff.isoformat(),
        "deletion_rule": "publication_date < cutoff_date",
        "rss_items_before": len(publications),
        "rss_items_after": len(publications) - len(expired),
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
            lines + [
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
            if planned else "✅ Просроченных публичных выпусков нет."
        )
        result = "не удалено (dry-run)"
    elif not planned:
        headline, result = "✅ Публичные страницы и RSS уже актуальны.", "не требовалось"
    elif published:
        headline = (
            "✅ Публичная очистка записана в `main`; "
            "точный commit передан FTP-синхронизации."
        )
        result = "удалено из GitHub"
    elif validation_outcome == "failure":
        headline, result = (
            "❌ Просроченный контент найден, но проверка безопасности не прошла. "
            "`main` и FTP не изменены.",
            "не опубликовано",
        )
    elif commit_outcome == "failure":
        headline, result = (
            "❌ Просроченный контент найден, но commit/push не завершился. "
            "FTP-синхронизация не запущена.",
            "не опубликовано",
        )
    else:
        headline, result = (
            "⚠️ Просроченный контент найден, но изменения не опубликованы.",
            "не опубликовано",
        )
    lines.extend(
        [
            headline,
            "",
            f"- Граница: удаляются только выпуски **раньше {report['cutoff_date']}**; "
            "эта дата и всё новее сохраняются.",
            f"- RSS: **{report['rss_items_before']} → {report['rss_items_after']}** "
            "актуальных ссылок.",
            f"- Найдено к удалению: **{report['removed_directories']} "
            f"{russian_plural(int(report['removed_directories']), 'выпуск', 'выпуска', 'выпусков')}**, "
            f"**{report['removed_files']} "
            f"{russian_plural(int(report['removed_files']), 'файл', 'файла', 'файлов')}**, "
            f"**{format_bytes(int(report['removed_bytes']))}**.",
            "",
        ]
    )
    details = report["expired_releases"]
    if details:
        lines += [
            "## Что найдено",
            "",
            "| Дата | Страница | Изображения | Файлов | Объём | Итог |",
            "|---|---|---|---:|---:|---|",
        ]
        for detail in details:
            images = "<br>".join(markdown_code(path) for path in detail["images"])
            lines.append(
                "| " + " | ".join(
                    [
                        str(detail["publication_date"]),
                        markdown_code(str(detail["page_directory"]) + "/"),
                        images,
                        str(detail["removed_files"]),
                        format_bytes(int(detail["removed_bytes"])),
                        result,
                    ]
                ) + " |"
            )
        updated = ", ".join(markdown_code(path) for path in report["updated_files"])
        lines += [
            "",
            "## Что актуализировано",
            "",
            f"- Связанные файлы: {updated}.",
            "- В них остаются только ссылки на выпуски не старше "
            f"{report['retention_days']} дней.",
            "- FTP удаляет те же страницы и изображения только после успешного "
            "commit; итог синхронизации указан в финальном job.",
            "",
        ]
    else:
        lines += [
            "Удаляемых страниц и изображений нет; RSS, индекс и sitemap "
            "не переписывались.",
            "",
        ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prune canonical public posts older than the retention window and "
            "rebuild RSS, index, and sitemap. Dry-run is the default."
        )
    )
    parser.add_argument("--retention-days", type=int, default=MINIMUM_RETENTION_DAYS)
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--reference-date")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        reference_date = resolve_reference_date(args.reference_date, args.timezone)
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
