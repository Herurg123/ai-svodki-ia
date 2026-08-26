#!/usr/bin/env python3
"""Attach an already published NotebookLM MP4 to an existing digest RSS item.

The module provides a production CLI that probes the public MP4/PNG pair and,
only when both are ready, inserts a Media RSS group into the existing item
without changing the item's title/link/guid/pubDate/content:encoded.

No paid APIs are used. Missing remote assets are a successful waiting/no-op
state.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import struct
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

MEDIA_NS = "http://search.yahoo.com/mrss/"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ITEM_BLOCK = re.compile(r"<item>.*?</item>", re.DOTALL)
LAST_BUILD_DATE = re.compile(r"<lastBuildDate>.*?</lastBuildDate>", re.DOTALL)
MIN_PREVIEW_WIDTH = 800
MIN_PREVIEW_HEIGHT = 400
USER_AGENT = "ai-svodki-video-rss-enrichment/1.0"


class VideoRssError(RuntimeError):
    """Raised when enrichment cannot be proven safe."""


@dataclass(frozen=True)
class VideoMedia:
    url: str
    thumbnail_url: str
    content_type: str = "video/mp4"
    medium: str = "video"


def is_https(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def extract_video_media(item: ET.Element) -> VideoMedia | None:
    """Return the one supported video media group from an RSS item, if present."""
    videos: list[VideoMedia] = []
    for group in item.findall(f"{{{MEDIA_NS}}}group"):
        contents = [
            node
            for node in group.findall(f"{{{MEDIA_NS}}}content")
            if (node.get("medium") or "").strip().casefold() == "video"
            or (node.get("type") or "").strip().casefold().startswith("video/")
        ]
        if not contents:
            continue
        if len(contents) != 1:
            raise VideoRssError(
                "RSS item contains more than one video media:content in a group"
            )
        thumbnails = group.findall(f"{{{MEDIA_NS}}}thumbnail")
        if len(thumbnails) != 1:
            raise VideoRssError(
                "Video media:group must contain exactly one media:thumbnail"
            )
        content = contents[0]
        thumbnail = thumbnails[0]
        url = (content.get("url") or "").strip()
        thumbnail_url = (thumbnail.get("url") or "").strip()
        content_type = (content.get("type") or "video/mp4").strip()
        medium = (content.get("medium") or "video").strip()
        if not url or not thumbnail_url:
            raise VideoRssError("Video media:group contains an empty URL")
        videos.append(
            VideoMedia(
                url=url,
                thumbnail_url=thumbnail_url,
                content_type=content_type,
                medium=medium,
            )
        )
    if len(videos) > 1:
        raise VideoRssError("RSS item contains more than one video media:group")
    return videos[0] if videos else None


def render_video_media_group(media: VideoMedia, *, indent: str = "    ") -> str:
    child = indent + "  "
    return (
        f"{indent}<media:group>\n"
        f'{child}<media:content url="{html.escape(media.url, quote=True)}" '
        f'medium="{html.escape(media.medium, quote=True)}" '
        f'type="{html.escape(media.content_type, quote=True)}" />\n'
        f'{child}<media:thumbnail url="{html.escape(media.thumbnail_url, quote=True)}" />\n'
        f"{indent}</media:group>"
    )


def expected_media(site_base_url: str, publication_date: date) -> VideoMedia:
    base = site_base_url.rstrip("/")
    stamp = publication_date.isoformat()
    return VideoMedia(
        url=f"{base}/video/ai-svodka-{stamp}.mp4",
        thumbnail_url=f"{base}/video/ai-svodka-{stamp}.png",
    )


def _parse_rss(text: str) -> tuple[ET.Element, ET.Element, list[ET.Element]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise VideoRssError(f"RSS is invalid XML: {exc}") from exc
    channel = root.find("channel")
    if channel is None:
        raise VideoRssError("RSS channel is missing")
    items = channel.findall("item")
    if not items:
        raise VideoRssError("RSS contains no items")
    return root, channel, items


def find_target_item(
    text: str,
    *,
    publication_date: date,
    site_base_url: str,
) -> tuple[ET.Element | None, int | None, list[re.Match[str]]]:
    _root, _channel, items = _parse_rss(text)
    target_link = f"{site_base_url.rstrip('/')}/{publication_date.isoformat()}/"
    indexes = [
        index
        for index, item in enumerate(items)
        if (item.findtext("link") or "").strip() == target_link
    ]
    if len(indexes) > 1:
        raise VideoRssError(f"RSS contains duplicate target item: {target_link}")
    blocks = list(ITEM_BLOCK.finditer(text))
    if len(blocks) != len(items):
        raise VideoRssError("RSS item blocks cannot be mapped safely to parsed items")
    if not indexes:
        return None, None, blocks
    index = indexes[0]
    return items[index], index, blocks


def enrich_rss_text(
    text: str,
    *,
    publication_date: date,
    site_base_url: str,
    updated_at: datetime,
) -> tuple[str, bool]:
    """Insert the expected video group while preserving the target item payload."""
    item, index, blocks = find_target_item(
        text,
        publication_date=publication_date,
        site_base_url=site_base_url,
    )
    if item is None or index is None:
        raise VideoRssError(
            f"Target article is not present in RSS: {publication_date.isoformat()}"
        )

    expected = expected_media(site_base_url, publication_date)
    existing = extract_video_media(item)
    if existing is not None:
        if existing == expected:
            return text, False
        raise VideoRssError(
            "Target item already contains a different video media group; "
            "refusing to overwrite it"
        )

    if not is_https(expected.url) or not is_https(expected.thumbnail_url):
        raise VideoRssError("Video and thumbnail URLs must be absolute HTTPS URLs")

    block_match = blocks[index]
    block = block_match.group(0)
    description_match = re.search(
        r"(?m)^(?P<indent>[ \t]*)<description(?:\s|>)",
        block,
    )
    if description_match is None:
        raise VideoRssError("Target RSS item has no description insertion point")
    indent = description_match.group("indent")
    video_xml = render_video_media_group(expected, indent=indent)
    updated_block = (
        block[: description_match.start()]
        + video_xml
        + "\n"
        + block[description_match.start() :]
    )
    updated = text[: block_match.start()] + updated_block + text[block_match.end() :]

    if updated_at.tzinfo is None:
        raise VideoRssError("updated_at must be timezone-aware")
    replacement = f"<lastBuildDate>{format_datetime(updated_at)}</lastBuildDate>"
    updated, count = LAST_BUILD_DATE.subn(replacement, updated, count=1)
    if count != 1:
        raise VideoRssError("RSS channel lastBuildDate is missing")

    new_item, _new_index, _new_blocks = find_target_item(
        updated,
        publication_date=publication_date,
        site_base_url=site_base_url,
    )
    if new_item is None:
        raise VideoRssError("Target item disappeared after enrichment")
    for tag in ("title", "link", "guid", "pubDate"):
        before = (item.findtext(tag) or "").strip()
        after = (new_item.findtext(tag) or "").strip()
        if before != after:
            raise VideoRssError(f"Protected item field changed during enrichment: {tag}")
    before_content = item.findtext(f"{{{CONTENT_NS}}}encoded") or ""
    after_content = new_item.findtext(f"{{{CONTENT_NS}}}encoded") or ""
    if before_content != after_content:
        raise VideoRssError("content:encoded changed during video enrichment")
    if extract_video_media(new_item) != expected:
        raise VideoRssError("Expected video media group is missing after enrichment")
    return updated, True


def _request(
    url: str,
    *,
    method: str,
    timeout: int,
    headers: dict[str, str] | None = None,
):
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, method=method, headers=request_headers)
    return urllib.request.urlopen(request, timeout=timeout)


def _remote_missing(exc: Exception) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code in {404, 410}


def probe_mp4(url: str, *, timeout: int) -> dict[str, Any]:
    try:
        try:
            response = _request(url, method="HEAD", timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in {403, 405, 501}:
                raise
            response = _request(
                url,
                method="GET",
                timeout=timeout,
                headers={"Range": "bytes=0-0"},
            )
        with response:
            status = int(getattr(response, "status", response.getcode()))
            content_type = (
                (response.headers.get("Content-Type") or "")
                .split(";", 1)[0]
                .strip()
                .casefold()
            )
            content_length = (response.headers.get("Content-Length") or "").strip()
            if not 200 <= status < 300:
                return {
                    "ready": False,
                    "state": "waiting",
                    "reason": f"HTTP {status}",
                }
            if content_type in {"text/html", "application/xhtml+xml"}:
                return {
                    "ready": False,
                    "state": "invalid",
                    "reason": f"MP4 URL returns {content_type}",
                }
            if content_length.isdigit() and int(content_length) <= 0:
                return {
                    "ready": False,
                    "state": "invalid",
                    "reason": "MP4 content length is zero",
                }
            return {
                "ready": True,
                "state": "ready",
                "status": status,
                "content_type": content_type,
                "content_length": (
                    int(content_length) if content_length.isdigit() else None
                ),
            }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        if _remote_missing(exc):
            return {
                "ready": False,
                "state": "waiting",
                "reason": f"HTTP {exc.code}",
            }
        return {
            "ready": False,
            "state": "waiting",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def parse_png_dimensions(header: bytes) -> tuple[int, int]:
    if len(header) < 24:
        raise VideoRssError("PNG response is shorter than the IHDR header")
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise VideoRssError("Preview URL does not contain a PNG image")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def probe_png(url: str, *, timeout: int) -> dict[str, Any]:
    try:
        with _request(
            url,
            method="GET",
            timeout=timeout,
            headers={"Range": "bytes=0-31"},
        ) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status not in {200, 206}:
                return {
                    "ready": False,
                    "state": "waiting",
                    "reason": f"HTTP {status}",
                }
            header = response.read(32)
            try:
                width, height = parse_png_dimensions(header)
            except VideoRssError as exc:
                return {
                    "ready": False,
                    "state": "invalid",
                    "reason": str(exc),
                }
            if width < MIN_PREVIEW_WIDTH or height < MIN_PREVIEW_HEIGHT:
                return {
                    "ready": False,
                    "state": "invalid",
                    "reason": (
                        f"Preview is {width}x{height}; minimum is "
                        f"{MIN_PREVIEW_WIDTH}x{MIN_PREVIEW_HEIGHT}"
                    ),
                    "width": width,
                    "height": height,
                }
            return {
                "ready": True,
                "state": "ready",
                "status": status,
                "width": width,
                "height": height,
                "content_type": (
                    (response.headers.get("Content-Type") or "")
                    .split(";", 1)[0]
                    .strip()
                    .casefold()
                ),
            }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        if _remote_missing(exc):
            return {
                "ready": False,
                "state": "waiting",
                "reason": f"HTTP {exc.code}",
            }
        return {
            "ready": False,
            "state": "waiting",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def probe_assets(media: VideoMedia, *, timeout: int) -> dict[str, Any]:
    mp4 = probe_mp4(media.url, timeout=timeout)
    png = probe_png(media.thumbnail_url, timeout=timeout)
    invalid = [
        name
        for name, result in (("mp4", mp4), ("thumbnail", png))
        if result.get("state") == "invalid"
    ]
    ready = bool(mp4.get("ready")) and bool(png.get("ready")) and not invalid
    return {
        "ready": ready,
        "invalid": invalid,
        "mp4": mp4,
        "thumbnail": png,
    }


def read_site_base_url(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VideoRssError(f"Cannot read site config {path}: {exc}") from exc
    value = data.get("site_base_url")
    if not isinstance(value, str) or not is_https(value):
        raise VideoRssError("site_base_url must be an absolute HTTPS URL")
    return value.rstrip("/")


def write_output(path: Path | None, values: dict[str, str]) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rss", type=Path, default=Path("posts/rss.xml"))
    parser.add_argument(
        "--site-config",
        type=Path,
        default=Path("automation/config/site.json"),
    )
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--skip-remote-check",
        action="store_true",
        help=(
            "For offline tests/manual dry-runs only; production workflow must "
            "not use this flag."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report: dict[str, Any] = {
        "status": "error",
        "changed": False,
        "publication_date": args.publication_date,
        "rss": str(args.rss),
    }
    exit_code = 1
    try:
        publication_date = date.fromisoformat(args.publication_date)
        site_base_url = read_site_base_url(args.site_config)
        media = expected_media(site_base_url, publication_date)
        report["video_url"] = media.url
        report["thumbnail_url"] = media.thumbnail_url

        text = args.rss.read_text(encoding="utf-8")
        item, _index, _blocks = find_target_item(
            text,
            publication_date=publication_date,
            site_base_url=site_base_url,
        )
        if item is None:
            report.update(
                status="waiting_article",
                reason="Target article is not yet present in RSS",
            )
            exit_code = 0
        else:
            existing = extract_video_media(item)
            if existing is not None:
                if existing != media:
                    raise VideoRssError(
                        "Target article already contains a different video media group"
                    )
                report.update(status="already_enriched", changed=False)
                exit_code = 0
            else:
                if args.skip_remote_check:
                    assets = {"ready": True, "invalid": [], "mode": "skipped"}
                else:
                    assets = probe_assets(media, timeout=args.timeout)
                report["assets"] = assets
                if assets.get("invalid"):
                    report.update(
                        status="invalid_assets",
                        reason="Published media failed validation",
                    )
                    exit_code = 1
                elif not assets.get("ready"):
                    report.update(
                        status="waiting_assets",
                        reason="MP4 and PNG are not both ready",
                    )
                    exit_code = 0
                elif not args.apply:
                    report.update(status="ready_dry_run", changed=False)
                    exit_code = 0
                else:
                    updated, changed = enrich_rss_text(
                        text,
                        publication_date=publication_date,
                        site_base_url=site_base_url,
                        updated_at=datetime.now(ZoneInfo("Europe/Moscow")),
                    )
                    if changed:
                        args.rss.write_text(updated, encoding="utf-8")
                    report.update(
                        status="enriched" if changed else "already_enriched",
                        changed=changed,
                    )
                    exit_code = 0
    except Exception as exc:
        report.update(status="error", error=f"{type(exc).__name__}: {exc}")
        exit_code = 1

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_output(
        args.github_output,
        {
            "status": str(report.get("status", "error")),
            "changed": "true" if report.get("changed") else "false",
        },
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
