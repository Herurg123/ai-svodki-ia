from __future__ import annotations

import hashlib
import json
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ATOM_NS = "http://www.w3.org/2005/Atom"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return "missing"
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()

def assert_inside(path: Path, parent: Path, label: str) -> None:
    resolved = path.resolve()
    allowed = parent.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise RuntimeError(f"{label} must be inside {allowed}")

def parse_rss(path: Path) -> dict[str, Any]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise RuntimeError(f"RSS XML is invalid: {exc}") from exc
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("RSS channel is missing")
    atom = channel.find(f"{{{ATOM_NS}}}link")
    self_url = atom.get("href", "").strip() if atom is not None else ""
    items = []
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        pub_raw = (item.findtext("pubDate") or "").strip()
        title = (item.findtext("title") or "").strip()
        if not link or not pub_raw:
            raise RuntimeError(f"Incomplete RSS item: {title!r}")
        parsed = parsedate_to_datetime(pub_raw)
        if parsed.tzinfo is None:
            raise RuntimeError(f"RSS pubDate has no timezone: {pub_raw}")
        items.append({
            "title": title,
            "link": link,
            "date": parsed.date().isoformat(),
            "categories": [
                (node.text or "").strip()
                for node in item.findall("category")
                if (node.text or "").strip()
            ],
        })
    if not items:
        raise RuntimeError("RSS contains no items")
    items.sort(key=lambda row: row["date"], reverse=True)
    return {
        "self_url": self_url,
        "channel_link": (channel.findtext("link") or "").strip(),
        "items": items,
        "latest_date": items[0]["date"],
    }

def runtime_context(
    *,
    config: dict[str, Any],
    rss: dict[str, Any],
    now_iso: str | None = None,
    publication_date_override: str | None = None,
) -> dict[str, Any]:
    timezone_name = str(config["timezone"])
    zone = ZoneInfo(timezone_name)
    if now_iso:
        current = datetime.fromisoformat(now_iso)
        if current.tzinfo is None:
            current = current.replace(tzinfo=zone)
        current = current.astimezone(zone)
    else:
        current = datetime.now(zone)

    target = (
        date.fromisoformat(publication_date_override)
        if publication_date_override
        else current.date()
    )
    first = date.fromisoformat(str(config["first_publication_date"]))
    if target < first:
        raise RuntimeError(
            f"Publication date {target} is before first allowed date {first}"
        )

    expected_feed = str(config["feed_url"])
    if rss["self_url"] != expected_feed:
        raise RuntimeError(
            f"RSS self URL must be {expected_feed!r}; received {rss['self_url']!r}"
        )

    legacy_prefix = str(config["legacy_prefix"])
    legacy_count = sum(
        1 for row in rss["items"] if str(row["link"]).startswith(legacy_prefix)
    )
    minimum_legacy = int(config["minimum_legacy_items"])
    if legacy_count < minimum_legacy:
        raise RuntimeError(
            f"RSS must preserve at least {minimum_legacy} legacy items; got {legacy_count}"
        )

    target_url = f"{str(config['site_base_url']).rstrip('/')}/{target.isoformat()}/"
    if any(row["link"] == target_url for row in rss["items"]):
        raise RuntimeError(f"RSS already contains {target_url}")

    if bool(config.get("require_previous_day_in_rss", True)):
        expected_previous = (target - timedelta(days=1)).isoformat()
        if rss["latest_date"] != expected_previous:
            raise RuntimeError(
                "Latest RSS item must be the previous calendar day: "
                f"expected {expected_previous}, got {rss['latest_date']}"
            )

    return {
        "status": "ok",
        "publication_date": target.isoformat(),
        "previous_date": (target - timedelta(days=1)).isoformat(),
        "target_url": target_url,
        "digest_request_id": f"production-digest-{target.isoformat()}",
        "image_request_id": f"production-image-{target.isoformat()}",
        "legacy_items": legacy_count,
        "rss_latest_date": rss["latest_date"],
        "timezone": timezone_name,
        "publication_hour_local": int(config["publication_hour_local"]),
        "generated_at": current.isoformat(timespec="seconds"),
    }

def safe_replace_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.tmp-{os.getpid()}"
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(source, temporary)
    if destination.exists():
        backup = destination.parent / f".{destination.name}.old-{os.getpid()}"
        if backup.exists():
            shutil.rmtree(backup)
        destination.replace(backup)
        temporary.replace(destination)
        shutil.rmtree(backup)
    else:
        temporary.replace(destination)
