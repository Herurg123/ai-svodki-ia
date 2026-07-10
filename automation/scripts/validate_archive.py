from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_PATH = ROOT / "automation" / "archive" / "index.json"


def validate_item(item: dict[str, Any], position: int) -> list[str]:
    errors: list[str] = []

    required_fields = {
        "date",
        "title",
        "link",
        "summary",
        "topics",
        "source_urls",
    }

    missing = required_fields.difference(item)

    if missing:
        errors.append(
            f"Item {position}: missing fields: {', '.join(sorted(missing))}"
        )
        return errors

    try:
        date.fromisoformat(item["date"])
    except (TypeError, ValueError):
        errors.append(f"Item {position}: invalid date: {item['date']}")

    if not isinstance(item["title"], str) or not item["title"].strip():
        errors.append(f"Item {position}: empty title")

    if not str(item["link"]).startswith("https://rybalka.one/posts/"):
        errors.append(
            f"Item {position}: unexpected article link: {item['link']}"
        )

    if not isinstance(item["topics"], list):
        errors.append(f"Item {position}: topics must be a list")

    if not isinstance(item["source_urls"], list):
        errors.append(f"Item {position}: source_urls must be a list")

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

    items = archive.get("items")

    if not isinstance(items, list):
        print("Archive field 'items' must be a list", file=sys.stderr)
        return 1

    errors: list[str] = []

    if len(items) < 3:
        errors.append(
            f"Archive contains only {len(items)} items; expected at least 3"
        )

    seen_dates: set[str] = set()
    seen_links: set[str] = set()

    for position, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Item {position}: must be an object")
            continue

        errors.extend(validate_item(item, position))

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
    print(f"Items: {len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
