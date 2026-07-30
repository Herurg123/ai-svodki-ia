#!/usr/bin/env python3
"""Compact old repository content without touching the published site."""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "automation" / "content"
DATE_DIRECTORY = re.compile(r"\d{4}-\d{2}-\d{2}")
PRESERVED_FILENAMES = frozenset({"meta.json", "stories.json"})
MINIMUM_RETENTION_DAYS = 32


class CleanupError(RuntimeError):
    """Raised when cleanup cannot be proven safe."""


@dataclass(frozen=True)
class CleanupTarget:
    publication_date: date
    directory: Path
    entries: tuple[Path, ...]
    files: int
    bytes: int


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CleanupError(f"Required retention file is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CleanupError(f"Cannot read valid JSON from {path}: {exc}") from exc


def validate_retention_record(directory: Path) -> None:
    meta_path = directory / "meta.json"
    stories_path = directory / "stories.json"
    for path in (meta_path, stories_path):
        if path.is_symlink() or not path.is_file():
            raise CleanupError(
                f"Old content directory must contain a regular {path.name}: {directory}"
            )

    meta = read_json(meta_path)
    stories = read_json(stories_path)
    if not isinstance(meta, dict):
        raise CleanupError(f"{meta_path} must contain a JSON object")
    if not isinstance(stories, list) or not stories:
        raise CleanupError(f"{stories_path} must contain a non-empty JSON array")
    if any(not isinstance(item, dict) for item in stories):
        raise CleanupError(f"{stories_path} must contain only JSON objects")


def entry_stats(path: Path) -> tuple[int, int]:
    if path.is_symlink():
        return 1, path.lstat().st_size
    if path.is_file():
        return 1, path.stat().st_size
    if path.is_dir():
        files = 0
        size = 0
        for child in path.iterdir():
            child_files, child_size = entry_stats(child)
            files += child_files
            size += child_size
        return files, size
    return 1, path.lstat().st_size


def remove_entry(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)


def describe_entry(path: Path, directory: Path) -> str:
    relative = path.relative_to(directory).as_posix()
    if path.is_dir() and not path.is_symlink():
        return f"{relative}/"
    return relative


def build_plan(
    content_root: Path,
    *,
    reference_date: date,
    retention_days: int,
) -> tuple[date, list[CleanupTarget]]:
    if retention_days < MINIMUM_RETENTION_DAYS:
        raise CleanupError(
            f"retention_days must be at least {MINIMUM_RETENTION_DAYS}"
        )
    if content_root.is_symlink() or not content_root.is_dir():
        raise CleanupError(f"Content root must be a regular directory: {content_root}")

    cutoff_date = reference_date - timedelta(days=retention_days)
    targets: list[CleanupTarget] = []

    for directory in sorted(content_root.iterdir(), key=lambda path: path.name):
        if not DATE_DIRECTORY.fullmatch(directory.name):
            continue
        try:
            publication_date = date.fromisoformat(directory.name)
        except ValueError as exc:
            raise CleanupError(
                f"Invalid date-shaped content directory: {directory}"
            ) from exc
        if directory.is_symlink() or not directory.is_dir():
            raise CleanupError(
                f"Date-shaped content path must be a regular directory: {directory}"
            )
        if publication_date >= cutoff_date:
            continue

        validate_retention_record(directory)
        entries = tuple(
            sorted(
                (
                    entry
                    for entry in directory.iterdir()
                    if entry.name not in PRESERVED_FILENAMES
                ),
                key=lambda path: path.name,
            )
        )
        files = 0
        size = 0
        for entry in entries:
            entry_files, entry_size = entry_stats(entry)
            files += entry_files
            size += entry_size
        targets.append(
            CleanupTarget(
                publication_date=publication_date,
                directory=directory,
                entries=entries,
                files=files,
                bytes=size,
            )
        )

    return cutoff_date, targets


def run_cleanup(
    content_root: Path,
    *,
    reference_date: date,
    retention_days: int,
    apply: bool,
) -> dict[str, Any]:
    cutoff_date, targets = build_plan(
        content_root,
        reference_date=reference_date,
        retention_days=retention_days,
    )
    changed_targets = [target for target in targets if target.entries]

    removed_entries = [
        entry.relative_to(content_root).as_posix()
        for target in changed_targets
        for entry in target.entries
    ]
    compaction_details = [
        {
            "publication_date": target.publication_date.isoformat(),
            "removed_entries": [
                describe_entry(entry, target.directory)
                for entry in target.entries
            ],
            "removed_files": target.files,
            "removed_bytes": target.bytes,
        }
        for target in changed_targets
    ]
    removed_files = sum(target.files for target in changed_targets)
    removed_bytes = sum(target.bytes for target in changed_targets)

    # All dated directories are validated before the first destructive operation.
    if apply:
        for target in changed_targets:
            for entry in target.entries:
                remove_entry(entry)

    return {
        "status": "ok",
        "mode": "apply" if apply else "dry-run",
        "reference_date": reference_date.isoformat(),
        "timezone": None,
        "retention_days": retention_days,
        "cutoff_date": cutoff_date.isoformat(),
        "deletion_rule": "publication_date < cutoff_date",
        "preserved_filenames": sorted(PRESERVED_FILENAMES),
        "eligible_directories": [
            target.publication_date.isoformat() for target in targets
        ],
        "compacted_directories": [
            target.publication_date.isoformat() for target in changed_targets
        ],
        "already_compact_directories": [
            target.publication_date.isoformat()
            for target in targets
            if not target.entries
        ],
        "compaction_details": compaction_details,
        "removed_entries": removed_entries,
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
        "changes_planned": bool(changed_targets),
        "changes_applied": bool(changed_targets) and apply,
    }


def format_bytes(value: int) -> str:
    if value < 0:
        raise ValueError("Byte count cannot be negative")
    units = ("Б", "КиБ", "МиБ", "ГиБ")
    amount = float(value)
    unit = units[0]
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            break
        amount /= 1024
    if unit == "Б":
        return f"{value} {unit}"
    return f"{amount:.1f}".replace(".", ",") + f" {unit}"


def markdown_code(value: str) -> str:
    safe = html.escape(value.replace("\r", " ").replace("\n", " "))
    safe = safe.replace("|", "&#124;")
    return f"<code>{safe}</code>"


def russian_plural(value: int, one: str, few: str, many: str) -> str:
    last_two = value % 100
    if 11 <= last_two <= 14:
        return many
    last = value % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def render_github_summary(
    report: dict[str, Any] | None,
    *,
    cleanup_outcome: str,
    validation_outcome: str,
    commit_outcome: str,
) -> str:
    lines = ["# Ночная очистка GitHub-репозитория", ""]
    if cleanup_outcome != "success" or report is None:
        lines.extend(
            [
                "❌ Очистка не завершилась, итоговый отчёт не сформирован.",
                "",
                "Изменения в `main` этим запуском не опубликованы. "
                "Причину смотри в шагах workflow.",
                "",
            ]
        )
        return "\n".join(lines)

    mode = report["mode"]
    details = report["compaction_details"]
    changes_planned = bool(report["changes_planned"])
    removed_files = int(report["removed_files"])
    removed_bytes = int(report["removed_bytes"])
    eligible_count = len(report["eligible_directories"])
    compacted_count = len(report["compacted_directories"])
    already_compact_count = len(report["already_compact_directories"])

    published = (
        mode == "apply"
        and changes_planned
        and validation_outcome == "success"
        and commit_outcome == "success"
    )
    if mode == "dry-run":
        if changes_planned:
            headline = (
                "🟡 Проверка завершена: мусор найден, но ничего не удалено "
                "(ручной dry-run)."
            )
        else:
            headline = "✅ Проверка завершена: удалять нечего."
        result_label = "не удалено (dry-run)"
        amount_label = "К удалению найдено"
    elif not changes_planned:
        headline = "✅ Ночная очистка завершена: удалять нечего."
        result_label = "уже компактно"
        amount_label = "Удалено"
    elif published:
        headline = "✅ Ночная очистка завершена, изменения записаны в `main`."
        result_label = "удалено"
        amount_label = "Удалено"
    elif validation_outcome == "failure":
        headline = (
            "❌ Мусор найден, но проверка безопасности не прошла. "
            "`main` не изменён."
        )
        result_label = "не опубликовано"
        amount_label = "К удалению найдено"
    elif commit_outcome == "failure":
        headline = (
            "❌ Мусор найден, но commit/push не завершился. "
            "`main` не изменён."
        )
        result_label = "не опубликовано"
        amount_label = "К удалению найдено"
    else:
        headline = (
            "⚠️ Мусор найден, но изменения не были записаны в `main`. "
            "Проверь шаги workflow."
        )
        result_label = "не опубликовано"
        amount_label = "К удалению найдено"

    lines.extend(
        [
            headline,
            "",
            f"- Режим: **{'очистка' if mode == 'apply' else 'проверка без удаления'}**.",
            (
                f"- Граница: обрабатываются только выпуски **раньше "
                f"{report['cutoff_date']}**; эта дата и всё новее сохраняются полностью."
            ),
            (
                f"- Старых выпусков: **{eligible_count}**; "
                f"с лишними файлами: **{compacted_count}**; "
                f"уже компактных: **{already_compact_count}**."
            ),
            (
                f"- {amount_label}: **{removed_files} "
                f"{russian_plural(removed_files, 'файл', 'файла', 'файлов')}**, "
                f"**{format_bytes(removed_bytes)}**."
            ),
            "",
        ]
    )

    if details:
        lines.extend(
            [
                "## Что найдено по выпускам",
                "",
                "| Выпуск | Найденные элементы | Файлов | Объём | Сохранено | Итог |",
                "|---|---|---:|---:|---|---|",
            ]
        )
        preserved = ", ".join(
            markdown_code(name) for name in report["preserved_filenames"]
        )
        for detail in details:
            entries = "<br>".join(
                markdown_code(name) for name in detail["removed_entries"]
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(detail["publication_date"]),
                        entries or "—",
                        str(detail["removed_files"]),
                        format_bytes(int(detail["removed_bytes"])),
                        preserved,
                        result_label,
                    ]
                )
                + " |"
            )
        lines.append("")
    else:
        lines.extend(["Обработанных выпусков нет: файлы не удалялись.", ""])

    lines.extend(
        [
            "## Что гарантированно сохранено",
            "",
            "- В каждом старом выпуске: `meta.json` и `stories.json` "
            "(нужны для редакционной дедупликации).",
            "- Публичные `posts/`, RSS, sitemap, FTP и `dzen-test` "
            "этот workflow не меняет.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compact automation/content releases older than the retention window. "
            "Dry-run is the default."
        )
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=MINIMUM_RETENTION_DAYS,
    )
    parser.add_argument(
        "--timezone",
        default="Europe/Moscow",
    )
    parser.add_argument(
        "--reference-date",
        help="Optional deterministic YYYY-MM-DD date; defaults to today in --timezone.",
    )
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the plan. Without this flag no files are changed.",
    )
    return parser.parse_args()


def resolve_reference_date(value: str | None, timezone_name: str) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CleanupError(
                f"reference-date must use YYYY-MM-DD: {value!r}"
            ) from exc
    try:
        zone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise CleanupError(f"Unknown timezone: {timezone_name!r}") from exc
    return datetime.now(zone).date()


def main() -> int:
    args = parse_args()
    try:
        reference_date = resolve_reference_date(
            args.reference_date,
            args.timezone,
        )
        report = run_cleanup(
            CONTENT_ROOT,
            reference_date=reference_date,
            retention_days=args.retention_days,
            apply=args.apply,
        )
        report["timezone"] = args.timezone
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"Repository content cleanup failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
