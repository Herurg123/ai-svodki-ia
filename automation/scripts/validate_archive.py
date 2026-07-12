from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_PATH = ROOT / "automation" / "archive" / "index.json"


def parse_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone missing")
    return parsed


def validate_story(
    story: dict[str, Any],
    item_position: int,
    story_position: int,
    legacy_allowed: bool,
) -> list[str]:
    errors: list[str] = []
    prefix = f"Item {item_position}, story {story_position}"

    if "Meta*" in json.dumps(story, ensure_ascii=False):
        errors.append(f"{prefix}: Meta* запрещено в служебных данных")

    if story.get("legacy") is True and legacy_allowed:
        return errors

    required = {
        "candidate_id",
        "section",
        "headline",
        "organization",
        "topic",
        "event_type",
        "status",
        "summary",
        "published_at",
        "published_date",
        "time_precision",
        "sources",
        "keywords",
        "geography",
        "category",
    }
    missing = sorted(required.difference(story))
    if missing:
        errors.append(f"{prefix}: missing fields: {', '.join(missing)}")
        return errors

    if story["status"] not in {"new", "update"}:
        errors.append(f"{prefix}: invalid status {story['status']!r}")
    if story["section"] not in {"world", "russia"}:
        errors.append(f"{prefix}: invalid section {story['section']!r}")
    if story["time_precision"] not in {"date", "datetime"}:
        errors.append(f"{prefix}: invalid time_precision")
    if story["time_precision"] == "datetime":
        try:
            parse_aware_datetime(str(story["published_at"]))
        except (TypeError, ValueError):
            errors.append(f"{prefix}: invalid published_at")
    elif story["published_at"] is not None:
        errors.append(f"{prefix}: date precision requires published_at=null")

    try:
        date.fromisoformat(str(story["published_date"]))
    except ValueError:
        errors.append(f"{prefix}: invalid published_date")

    if not isinstance(story["sources"], list):
        errors.append(f"{prefix}: sources must be a list")
    if not isinstance(story["keywords"], list):
        errors.append(f"{prefix}: keywords must be a list")
    return errors


def validate_item(
    item: dict[str, Any],
    position: int,
    archive_version: int,
) -> list[str]:
    errors: list[str] = []
    required_fields = {
        "date",
        "title",
        "link",
        "summary",
        "topics",
        "source_urls",
    }
    if archive_version >= 2:
        required_fields.update({"published_at", "stories"})

    missing = required_fields.difference(item)
    if missing:
        errors.append(
            f"Item {position}: missing fields: {', '.join(sorted(missing))}"
        )
        return errors

    try:
        date.fromisoformat(str(item["date"]))
    except ValueError:
        errors.append(f"Item {position}: invalid date: {item['date']}")

    if archive_version >= 2:
        try:
            parse_aware_datetime(str(item["published_at"]))
        except (TypeError, ValueError):
            errors.append(f"Item {position}: invalid published_at")

    if not isinstance(item["title"], str) or not item["title"].strip():
        errors.append(f"Item {position}: empty title")
    if "Meta*" in json.dumps(item, ensure_ascii=False):
        errors.append(f"Item {position}: Meta* запрещено в архивных данных")
    if not str(item["link"]).startswith("https://rybalka.one/posts/"):
        errors.append(f"Item {position}: unexpected article link: {item['link']}")
    if not isinstance(item["topics"], list):
        errors.append(f"Item {position}: topics must be a list")
    if not isinstance(item["source_urls"], list):
        errors.append(f"Item {position}: source_urls must be a list")
    elif len(item["source_urls"]) != len(set(item["source_urls"])):
        errors.append(f"Item {position}: duplicate source_urls")

    if archive_version >= 2:
        stories = item.get("stories")
        if not isinstance(stories, list):
            errors.append(f"Item {position}: stories must be a list")
        else:
            seen_story_ids: set[str] = set()
            for story_position, story in enumerate(stories, start=1):
                if not isinstance(story, dict):
                    errors.append(
                        f"Item {position}, story {story_position}: must be an object"
                    )
                    continue
                errors.extend(
                    validate_story(
                        story,
                        position,
                        story_position,
                        legacy_allowed=True,
                    )
                )
                candidate_id = str(story.get("candidate_id", ""))
                if candidate_id in seen_story_ids:
                    errors.append(
                        f"Item {position}: duplicate story candidate_id {candidate_id}"
                    )
                seen_story_ids.add(candidate_id)

    return errors


def main() -> int:
    if not ARCHIVE_PATH.exists():
        print(f"Archive not found: {ARCHIVE_PATH}", file=sys.stderr)
        return 1

    try:
        archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(archive, dict):
        print("Archive root must be an object", file=sys.stderr)
        return 1

    version = archive.get("version", 1)
    if version not in {1, 2}:
        print(f"Unsupported archive version: {version}", file=sys.stderr)
        return 1

    items = archive.get("items")
    if not isinstance(items, list):
        print("Archive field 'items' must be a list", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    if len(items) < 3:
        errors.append(f"Archive contains only {len(items)} items; expected at least 3")
    if version == 1:
        warnings.append("Archive version 1: structured stories are not available yet")

    seen_dates: set[str] = set()
    seen_links: set[str] = set()
    for position, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Item {position}: must be an object")
            continue
        errors.extend(validate_item(item, position, int(version)))
        item_date = str(item.get("date", ""))
        item_link = str(item.get("link", ""))
        if item_date in seen_dates:
            errors.append(f"Duplicate date: {item_date}")
        if item_link in seen_links:
            errors.append(f"Duplicate link: {item_link}")
        seen_dates.add(item_date)
        seen_links.add(item_link)

    if errors:
        print("Archive validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Archive validation passed")
    print(f"Version: {version}")
    print(f"Items: {len(items)}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
