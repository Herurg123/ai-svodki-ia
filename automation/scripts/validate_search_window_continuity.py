
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from production_daily_common import read_json, write_json


def parse_aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError(
            f"timestamp должен содержать часовой пояс: {value!r}"
        )
    return parsed


def latest_archive_release(
    archive: dict[str, Any],
    *,
    timezone_name: str,
    publication_hour: int,
) -> tuple[date, datetime]:
    zone = ZoneInfo(timezone_name)
    values: list[tuple[date, datetime]] = []

    for item in archive.get("items", []):
        if not isinstance(item, dict):
            continue
        raw_date = item.get("date")
        if not isinstance(raw_date, str):
            continue
        try:
            item_date = date.fromisoformat(raw_date)
        except ValueError:
            continue

        raw_cutoff = item.get("search_cutoff_at") or item.get("published_at")
        if isinstance(raw_cutoff, str) and raw_cutoff.strip():
            try:
                search_cutoff_at = parse_aware(raw_cutoff)
            except (RuntimeError, ValueError):
                search_cutoff_at = datetime.combine(
                    item_date,
                    time(hour=publication_hour),
                    tzinfo=zone,
                )
        else:
            search_cutoff_at = datetime.combine(
                item_date,
                time(hour=publication_hour),
                tzinfo=zone,
            )
        values.append((item_date, search_cutoff_at))

    if not values:
        raise RuntimeError("Архив дедупликации не содержит выпусков.")

    return max(values, key=lambda value: value[1])


def validate(
    *,
    runtime: dict[str, Any],
    archive: dict[str, Any],
    timezone_name: str,
    publication_hour: int,
) -> dict[str, Any]:
    expected_date = date.fromisoformat(
        str(runtime["previous_published_date"])
    )
    archive_date, archive_at = latest_archive_release(
        archive,
        timezone_name=timezone_name,
        publication_hour=publication_hour,
    )

    if archive_date != expected_date:
        raise RuntimeError(
            "Последний выпуск в архиве дедупликации не совпадает с RSS: "
            f"RSS={expected_date.isoformat()}, "
            f"archive={archive_date.isoformat()}."
        )

    target = date.fromisoformat(str(runtime["publication_date"]))
    if archive_date >= target:
        raise RuntimeError(
            "Дата последнего архивного выпуска должна быть старше "
            f"нового выпуска: archive={archive_date}, target={target}."
        )

    return {
        "status": "ok",
        "publication_date": target.isoformat(),
        "previous_published_date": archive_date.isoformat(),
        "search_window_start_at": archive_at.isoformat(
            timespec="seconds"
        ),
        "missed_calendar_days": int(
            runtime.get("missed_calendar_days", 0)
        ),
        "policy": "from_last_successful_research_cutoff",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--publication-hour", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        report = validate(
            runtime=read_json(args.runtime),
            archive=read_json(args.archive),
            timezone_name=args.timezone,
            publication_hour=args.publication_hour,
        )
    except Exception as exc:
        report = {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        write_json(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
