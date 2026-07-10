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
RSS_PATH = ROOT / "posts" / "rss.xml"
OUTPUT_PATH = ROOT / "automation" / "archive" / "index.json"

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


class ArticleParser(HTMLParser):
    """Extract headings, links and readable text from article HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.current_heading: str | None = None
        self.heading_buffer: list[str] = []
        self.topics: list[str] = []
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
            attributes = dict(attrs)
            href = attributes.get("href")

            if href and href.startswith(("http://", "https://")):
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self.current_heading == tag:
            heading = " ".join(self.heading_buffer)
            heading = re.sub(r"\s+", " ", heading).strip()

            if heading:
                self.topics.append(heading)

            self.current_heading = None
            self.heading_buffer = []

    def handle_data(self, data: str) -> None:
        cleaned = re.sub(r"\s+", " ", data).strip()

        if not cleaned:
            return

        self.text_parts.append(cleaned)

        if self.current_heading:
            self.heading_buffer.append(cleaned)


def normalise_date(pub_date: str) -> str:
    parsed = parsedate_to_datetime(pub_date)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.date().isoformat()


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


def build_archive() -> dict[str, Any]:
    if not RSS_PATH.exists():
        raise FileNotFoundError(f"RSS file not found: {RSS_PATH}")

    tree = ET.parse(RSS_PATH)
    root = tree.getroot()
    channel = root.find("channel")

    if channel is None:
        raise ValueError("RSS channel element was not found")

    items: list[dict[str, Any]] = []

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        encoded = item.findtext(f"{{{CONTENT_NS}}}encoded") or ""

        parser = ArticleParser()
        parser.feed(encoded)

        readable_text = " ".join(parser.text_parts)
        readable_text = re.sub(r"\s+", " ", readable_text).strip()

        topics = [
            topic
            for topic in unique(parser.topics)
            if topic.lower() not in {
                "мировые лидеры ии",
                "российские лидеры ии",
                "что это значит",
                "источники",
            }
        ]

        source_urls = [
            url
            for url in unique(parser.links)
            if not url.startswith("https://rybalka.one/")
        ]

        if not title:
            raise ValueError("An RSS item has no title")

        if not link:
            raise ValueError(f"RSS item '{title}' has no link")

        if not pub_date:
            raise ValueError(f"RSS item '{title}' has no pubDate")

        items.append(
            {
                "date": normalise_date(pub_date),
                "title": title,
                "link": link,
                "summary": readable_text[:500],
                "topics": topics,
                "source_urls": source_urls,
            }
        )

    items.sort(key=lambda entry: entry["date"], reverse=True)

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "posts/rss.xml",
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
        return 0

    except Exception as exc:
        print(f"Archive generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
