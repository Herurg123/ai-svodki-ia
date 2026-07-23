from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "automation" / "config" / "site.json"
RSS_PATH = ROOT / "posts" / "rss.xml"
OUTPUT_PATH = ROOT / "automation" / "archive" / "index.json"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


def normalize_meta_marker(value: str) -> str:
    return re.sub(r"(?<!\w)Meta\*+(?!\w)", "Meta", value)


class ArticleParser(HTMLParser):
    """Extract story headings, links and readable text from article HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_heading: str | None = None
        self.heading_buffer: list[str] = []
        self.headings: list[tuple[str, str]] = []
        self.links: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        if tag in {"h2", "h3"}:
            self.current_heading = tag
            self.heading_buffer = []
        if tag == "a":
            href = dict(attrs).get("href")
            if href and href.startswith(("http://", "https://")):
                self.links.append(href.strip())

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.current_heading == tag:
            heading = re.sub(
                r"\s+", " ", " ".join(self.heading_buffer)
            ).strip()
            if heading:
                self.headings.append((tag, normalize_meta_marker(heading)))
            self.current_heading = None
            self.heading_buffer = []

    def handle_data(self, data: str) -> None:
        cleaned = re.sub(r"\s+", " ", data).strip()
        if not cleaned:
            return
        self.text_parts.append(normalize_meta_marker(cleaned))
        if self.current_heading:
            self.heading_buffer.append(cleaned)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в {path}: {exc}") from exc


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def parse_rss_datetime(value: str) -> datetime:
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def source_urls_from_stories(stories: list[dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        sources = story.get("sources")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                urls.append(url)
    return unique(urls)


def load_content_record(
    content_directory: Path,
    publication_date: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    content_dir = content_directory / publication_date
    if not content_dir.is_dir():
        return None, []

    meta_path = content_dir / "meta.json"
    stories_path = content_dir / "stories.json"
    meta: dict[str, Any] | None = None
    stories: list[dict[str, Any]] = []

    if meta_path.is_file():
        value = read_json(meta_path)
        if isinstance(value, dict):
            meta = value

    if stories_path.is_file():
        value = read_json(stories_path)
        if not isinstance(value, list):
            raise RuntimeError(f"{stories_path} должен содержать массив.")
        stories = [item for item in value if isinstance(item, dict)]

    return meta, stories


def fallback_story_records(parser: ArticleParser) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    section = "world"
    ignored_h2 = {
        "мировые лидеры ии",
        "российские лидеры ии",
        "что это значит",
        "все ии-сводки",
        "источники",
    }

    for tag, heading in parser.headings:
        if tag == "h2":
            if heading == "Российские лидеры ИИ":
                section = "russia"
            elif heading == "Мировые лидеры ИИ":
                section = "world"
            continue
        if heading.casefold() in ignored_h2:
            continue
        records.append(
            {
                "candidate_id": f"legacy-{len(records) + 1:03d}",
                "section": section,
                "headline": heading,
                "organization": "unknown",
                "topic": "legacy",
                "event_type": "legacy",
                "status": (
                    "update" if heading.startswith("Обновление:") else "new"
                ),
                "summary": "",
                "published_at": None,
                "published_date": "",
                "time_precision": "date",
                "sources": [],
                "keywords": [],
                "geography": section,
                "category": "other",
                "legacy": True,
            }
        )
    return records


def build_archive() -> dict[str, Any]:
    config = read_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise RuntimeError("site.json должен содержать JSON-объект.")
    if not RSS_PATH.exists():
        raise FileNotFoundError(f"RSS file not found: {RSS_PATH}")

    content_directory = ROOT / str(config["content_directory"])
    dzen_url = "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1"

    tree = ET.parse(RSS_PATH)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS channel element was not found")

    items: list[dict[str, Any]] = []
    seen_dates: set[str] = set()

    for rss_item in channel.findall("item"):
        title = (rss_item.findtext("title") or "").strip()
        link = (rss_item.findtext("link") or "").strip()
        pub_date = (rss_item.findtext("pubDate") or "").strip()
        encoded = rss_item.findtext(f"{{{CONTENT_NS}}}encoded") or ""

        if not title or not link or not pub_date:
            raise ValueError("RSS item has missing title, link or pubDate")

        published_datetime = parse_rss_datetime(pub_date)
        publication_date = published_datetime.date().isoformat()
        parser = ArticleParser()
        parser.feed(encoded)
        readable_text = re.sub(
            r"\s+", " ", " ".join(parser.text_parts)
        ).strip()

        meta, stories = load_content_record(content_directory, publication_date)
        if not stories:
            stories = fallback_story_records(parser)
            for story in stories:
                story["published_date"] = publication_date

        source_urls = source_urls_from_stories(stories)
        if not source_urls:
            source_urls = [
                url
                for url in unique(parser.links)
                if not url.startswith("https://rybalka.one/") and url != dzen_url
            ]

        topics = []
        if meta and isinstance(meta.get("topics"), list):
            topics = [str(item).strip() for item in meta["topics"] if str(item).strip()]
        if not topics:
            topics = [
                heading
                for tag, heading in parser.headings
                if tag == "h3"
            ]

        published_at = (
            str(meta.get("published_at"))
            if meta and isinstance(meta.get("published_at"), str)
            else published_datetime.isoformat(timespec="seconds")
        )

        items.append(
            {
                "date": publication_date,
                "published_at": published_at,
                "title": title,
                "link": link,
                "summary": readable_text[:500],
                "topics": unique(topics),
                "source_urls": unique(source_urls),
                "stories": stories,
            }
        )
        seen_dates.add(publication_date)

    # Preserve content records that are not yet present in the live RSS.
    if content_directory.is_dir():
        for content_dir in sorted(content_directory.iterdir()):
            if not content_dir.is_dir() or content_dir.name in seen_dates:
                continue
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", content_dir.name):
                continue
            meta, stories = load_content_record(content_directory, content_dir.name)
            if not meta or not stories:
                continue
            site_base = str(config["site_base_url"]).rstrip("/")
            items.append(
                {
                    "date": content_dir.name,
                    "published_at": str(meta.get("published_at", "")),
                    "title": str(meta.get("title", "")),
                    "link": f"{site_base}/{content_dir.name}/",
                    "summary": str(meta.get("description", ""))[:500],
                    "topics": meta.get("topics", []),
                    "source_urls": source_urls_from_stories(stories),
                    "stories": stories,
                }
            )

    items.sort(key=lambda entry: str(entry.get("published_at", entry["date"])), reverse=True)
    return {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "automation/content + posts/rss.xml",
        "items": items,
    }


def main() -> int:
    try:
        archive = build_archive()
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(
            json.dumps(archive, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Archive written to: {OUTPUT_PATH}")
        print(f"Items found: {len(archive['items'])}")
        print(
            "Structured stories: "
            + str(sum(len(item.get("stories", [])) for item in archive["items"]))
        )
        return 0
    except Exception as exc:
        print(f"Archive generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
