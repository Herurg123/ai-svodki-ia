#!/usr/bin/env python3
"""Validate an isolated RSS feed against the editorial/Dzen contract.

The validator uses only the Python standard library and is intended for free
CI checks. It never performs network requests and never modifies production
files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
DZEN_ARCHIVE_URL = "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1"
DZEN_ARCHIVE_TEXT = "Архив ИИ-Сводок"
META_FOOTNOTE = "*Meta и ее сервисы - в России запрещены"
REQUIRED_H2 = ("Мировые лидеры ИИ", "Что это значит", "Все ИИ-Сводки")
FORBIDDEN_TAGS = {"html", "head", "body", "script", "style", "iframe", "h1", "img"}
INTERNAL_MARKERS = ("editorial_notes", "stories.json", "sources.json", "metadata-normalization")


@dataclass
class StoryBlock:
    headline: str
    paragraphs: int = 0
    links: list[str] = field(default_factory=list)


class ArticleInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture_tag: str | None = None
        self._capture_parts: list[str] = []
        self.current_h2: str | None = None
        self.current_story: StoryBlock | None = None
        self.h2_values: list[str] = []
        self.stories: list[StoryBlock] = []
        self.what_it_means_items = 0
        self.visible_parts: list[str] = []
        self.forbidden_tags: list[str] = []
        self.anchor_stack: list[dict[str, Any]] = []
        self.anchors: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in FORBIDDEN_TAGS:
            self.forbidden_tags.append(tag)
        if tag in {"h2", "h3"}:
            self._capture_tag = tag
            self._capture_parts = []
        elif tag == "p" and self.current_story is not None:
            self.current_story.paragraphs += 1
        elif tag == "li" and self.current_h2 == "Что это значит":
            self.what_it_means_items += 1
        elif tag == "a":
            attr_map = {name.lower(): value or "" for name, value in attrs}
            self.anchor_stack.append({"href": attr_map.get("href", ""), "text": []})

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"h2", "h3"} and self._capture_tag == tag:
            text = normalize_space("".join(self._capture_parts))
            if tag == "h2":
                self.current_h2 = text
                self.current_story = None
                self.h2_values.append(text)
            else:
                story = StoryBlock(headline=text)
                self.stories.append(story)
                self.current_story = story
            self._capture_tag = None
            self._capture_parts = []
        elif tag == "a" and self.anchor_stack:
            anchor = self.anchor_stack.pop()
            rendered = normalize_space("".join(anchor["text"]))
            self.anchors.append({"href": str(anchor["href"]), "text": rendered})
            if self.current_story is not None and anchor["href"]:
                self.current_story.links.append(str(anchor["href"]))

    def handle_data(self, data: str) -> None:
        self.visible_parts.append(data)
        if self._capture_tag is not None:
            self._capture_parts.append(data)
        for anchor in self.anchor_stack:
            anchor["text"].append(data)

    @property
    def visible_text(self) -> str:
        return normalize_space(" ".join(self.visible_parts))


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def add_issue(report: dict[str, Any], level: str, code: str, message: str, item: str | None = None) -> None:
    payload: dict[str, str] = {"code": code, "message": message}
    if item:
        payload["item"] = item
    report[level].append(payload)


def is_absolute_https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def is_under_base(url: str, base_url: str) -> bool:
    return url.rstrip("/").startswith(base_url.rstrip("/") + "/") or url.rstrip("/") == base_url.rstrip("/")


def item_text(item: ET.Element, tag: str) -> str:
    node = item.find(tag)
    return (node.text or "").strip() if node is not None else ""


def validate_article_html(
    html: str,
    *,
    report: dict[str, Any],
    item_label: str,
    strict_editorial: bool,
) -> None:
    inspector = ArticleInspector()
    try:
        inspector.feed(html)
        inspector.close()
    except Exception as exc:  # HTMLParser is lenient, but keep deterministic diagnostics.
        add_issue(report, "errors", "html_parse", f"Не удалось разобрать article HTML: {exc}", item_label)
        return

    for tag in sorted(set(inspector.forbidden_tags)):
        add_issue(report, "errors", "forbidden_html_tag", f"В article HTML запрещён тег <{tag}>.", item_label)

    if "```" in html or re.search(r"(?m)^\s{0,3}#{1,6}\s+", html):
        add_issue(report, "errors", "markdown_detected", "В RSS-контенте обнаружен Markdown.", item_label)

    lower_html = html.lower()
    for marker in ("localhost", "127.0.0.1", "file://", "automation/preview"):
        if marker in lower_html:
            add_issue(report, "errors", "preview_reference", f"В RSS-контенте обнаружена тестовая ссылка/путь: {marker}.", item_label)

    for marker in INTERNAL_MARKERS:
        if marker.lower() in lower_html:
            add_issue(report, "errors", "internal_marker", f"В опубликованный контент попал служебный маркер: {marker}.", item_label)

    for required in REQUIRED_H2:
        count = inspector.h2_values.count(required)
        if count != 1:
            add_issue(
                report,
                "errors",
                "section_count",
                f"Раздел «{required}» должен встречаться ровно один раз, найдено: {count}.",
                item_label,
            )

    dzen_anchors = [
        anchor
        for anchor in inspector.anchors
        if anchor["href"] == DZEN_ARCHIVE_URL and anchor["text"] == DZEN_ARCHIVE_TEXT
    ]
    if len(dzen_anchors) != 1:
        add_issue(
            report,
            "errors",
            "dzen_archive_link",
            "Нужна ровно одна ссылка на архив Дзена с точным URL и текстом «Архив ИИ-Сводок».",
            item_label,
        )

    dzen_block_pattern = re.compile(
        r"<h2>\s*Все ИИ-Сводки\s*</h2>\s*"
        r"<p>\s*<a\s+href=(['\"])"
        + re.escape(DZEN_ARCHIVE_URL)
        + r"\1\s*>\s*"
        + re.escape(DZEN_ARCHIVE_TEXT)
        + r"\s*</a>\s*</p>",
        re.IGNORECASE,
    )
    dzen_match = dzen_block_pattern.search(html)
    if dzen_match is None:
        add_issue(report, "errors", "dzen_block_exact", "Точный блок Дзена не найден или изменён.", item_label)

    visible_without_footnote = inspector.visible_text.replace(META_FOOTNOTE, "")
    meta_mentions = re.findall(r"(?<![\w])Meta\*?(?![\w])", visible_without_footnote)
    footnote_count = inspector.visible_text.count(META_FOOTNOTE)
    if meta_mentions:
        if meta_mentions[0] != "Meta*":
            add_issue(report, "errors", "meta_first_mention", "Первое видимое упоминание Meta должно быть «Meta*».", item_label)
        if any(value != "Meta" for value in meta_mentions[1:]):
            add_issue(report, "errors", "meta_later_mentions", "Последующие видимые упоминания должны быть «Meta» без звёздочки.", item_label)
        if footnote_count != 1:
            add_issue(report, "errors", "meta_footnote_count", f"Для статьи с Meta нужна ровно одна сноска, найдено: {footnote_count}.", item_label)
        elif dzen_match is not None and html.find(META_FOOTNOTE) < dzen_match.end():
            add_issue(report, "errors", "meta_footnote_position", "Сноска Meta должна находиться после блока Дзена.", item_label)
    elif footnote_count:
        add_issue(report, "errors", "meta_footnote_without_meta", "Сноска Meta присутствует без упоминания Meta в статье.", item_label)

    if strict_editorial:
        if not 4 <= inspector.what_it_means_items <= 6:
            add_issue(
                report,
                "errors",
                "conclusion_count",
                f"В разделе «Что это значит» должно быть 4–6 пунктов, найдено: {inspector.what_it_means_items}.",
                item_label,
            )

        if not inspector.stories:
            add_issue(report, "errors", "missing_stories", "В статье не найдено ни одного сюжета <h3>.", item_label)
        for story in inspector.stories:
            if not 2 <= story.paragraphs <= 3:
                add_issue(
                    report,
                    "errors",
                    "story_paragraph_count",
                    f"Сюжет «{story.headline}» должен содержать 2–3 абзаца, найдено: {story.paragraphs}.",
                    item_label,
                )


def validate_feed(
    rss_path: Path,
    *,
    site_base_url: str,
    latest_only: bool,
    strict_editorial: bool,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "validator": "dzen-rss-contract",
        "rss": str(rss_path),
        "site_base_url": site_base_url,
        "latest_only": latest_only,
        "strict_editorial": strict_editorial,
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "error",
        "items_total": 0,
        "items_checked": 0,
        "errors": [],
        "warnings": [],
    }

    if not rss_path.is_file():
        add_issue(report, "errors", "rss_missing", f"RSS-файл не найден: {rss_path}")
        return report

    try:
        raw = rss_path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        add_issue(report, "errors", "utf8", f"RSS должен быть корректным UTF-8: {exc}")
        return report
    except OSError as exc:
        add_issue(report, "errors", "rss_read", f"Не удалось прочитать RSS: {exc}")
        return report

    if "<?xml" not in text[:200]:
        add_issue(report, "warnings", "xml_declaration", "В начале RSS отсутствует XML declaration.")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        add_issue(report, "errors", "xml_parse", f"Некорректный XML: {exc}")
        return report

    if root.tag.lower().split("}")[-1] != "rss":
        add_issue(report, "errors", "rss_root", "Корневой элемент должен быть <rss>.")
        return report

    channel = root.find("channel")
    if channel is None:
        add_issue(report, "errors", "channel_missing", "В RSS отсутствует <channel>.")
        return report

    channel_link = item_text(channel, "link")
    if not is_absolute_https(channel_link):
        add_issue(report, "errors", "channel_link", "Ссылка канала должна быть абсолютным HTTPS URL.")

    items = channel.findall("item")
    report["items_total"] = len(items)
    if not items:
        add_issue(report, "errors", "items_missing", "RSS не содержит ни одного <item>.")
        return report

    seen_links: set[str] = set()
    seen_guids: set[str] = set()
    dates: list[datetime] = []

    for index, item in enumerate(items):
        label = item_text(item, "title") or f"item[{index}]"
        link = item_text(item, "link")
        guid = item_text(item, "guid")
        pub_date = item_text(item, "pubDate")
        description = item_text(item, "description")

        for field_name, value in (("title", label), ("link", link), ("guid", guid), ("pubDate", pub_date)):
            if not value:
                add_issue(report, "errors", "required_item_field", f"У item отсутствует обязательное поле {field_name}.", label)

        if not description:
            add_issue(report, "warnings", "description_missing", "У item отсутствует description.", label)

        if link:
            if not is_absolute_https(link):
                add_issue(report, "errors", "item_link_https", "Ссылка item должна быть абсолютным HTTPS URL.", label)
            elif not is_under_base(link, site_base_url):
                add_issue(report, "errors", "item_link_base", f"Ссылка item должна находиться под {site_base_url}.", label)
            if link in seen_links:
                add_issue(report, "errors", "duplicate_link", f"Повторяющийся link: {link}", label)
            seen_links.add(link)

        if guid:
            if not is_absolute_https(guid):
                add_issue(report, "errors", "guid_https", "GUID должен быть абсолютным HTTPS URL.", label)
            if guid in seen_guids:
                add_issue(report, "errors", "duplicate_guid", f"Повторяющийся guid: {guid}", label)
            seen_guids.add(guid)

        if pub_date:
            try:
                parsed = parsedate_to_datetime(pub_date)
                if parsed.tzinfo is None:
                    raise ValueError("timezone is missing")
                dates.append(parsed)
            except (TypeError, ValueError, OverflowError) as exc:
                add_issue(report, "errors", "pubdate", f"Некорректный timezone-aware RFC 2822 pubDate: {pub_date} ({exc}).", label)

    if len(dates) == len(items):
        for previous, current in zip(dates, dates[1:]):
            if previous < current:
                add_issue(report, "errors", "item_order", "RSS items должны идти от нового к старому.")
                break

    selected_items = items[:1] if latest_only else items
    report["items_checked"] = len(selected_items)
    for index, item in enumerate(selected_items):
        label = item_text(item, "title") or f"item[{index}]"
        content_node = item.find(f"{{{CONTENT_NS}}}encoded")
        content = (content_node.text or "").strip() if content_node is not None else ""
        if not content:
            add_issue(report, "errors", "content_encoded", "У item отсутствует непустой content:encoded.", label)
            continue
        validate_article_html(
            content,
            report=report,
            item_label=label,
            strict_editorial=strict_editorial,
        )

    report["status"] = "ok" if not report["errors"] else "error"
    return report


def load_site_base_url(config_path: Path) -> str:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Не удалось прочитать site config {config_path}: {exc}") from exc
    value = payload.get("site_base_url")
    if not isinstance(value, str) or not is_absolute_https(value):
        raise ValueError("site_base_url в site config должен быть абсолютным HTTPS URL")
    return value.rstrip("/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rss", type=Path, default=Path("automation/preview/posts/rss.xml"))
    parser.add_argument("--report", type=Path, default=Path("automation/preview/dzen-feed-validation.json"))
    parser.add_argument("--site-config", type=Path, default=Path("automation/config/site.json"))
    parser.add_argument("--site-base-url", default=None)
    parser.add_argument("--all-items", action="store_true", help="Проверять HTML-контракт у всех items, а не только у последнего выпуска.")
    parser.add_argument(
        "--legacy-compatible",
        action="store_true",
        help="Не применять новые нормы 2–3 абзаца и 4–6 выводов к старым production-выпускам.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        site_base_url = (args.site_base_url or load_site_base_url(args.site_config)).rstrip("/")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report = validate_feed(
        args.rss,
        site_base_url=site_base_url,
        latest_only=not args.all_items,
        strict_editorial=not args.legacy_compatible,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Dzen RSS validation: {report['status']}")
    print(f"Items: total={report['items_total']}, checked={report['items_checked']}")
    print(f"Errors: {len(report['errors'])}; warnings: {len(report['warnings'])}")
    for issue in report["errors"]:
        item_suffix = f" [{issue['item']}]" if "item" in issue else ""
        print(f"ERROR {issue['code']}{item_suffix}: {issue['message']}")
    for issue in report["warnings"]:
        item_suffix = f" [{issue['item']}]" if "item" in issue else ""
        print(f"WARN {issue['code']}{item_suffix}: {issue['message']}")
    print(f"Report: {args.report}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
