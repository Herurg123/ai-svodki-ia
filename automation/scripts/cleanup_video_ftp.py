#!/usr/bin/env python3
"""Prune expired NotebookLM MP4/PNG assets from the hard-confined FTP video dir.

This maintenance entrypoint is intentionally independent from RSS and from the
local NotebookLM worker. It only manages remote files whose basename exactly
matches ``ai-svodka-YYYY-MM-DD.mp4`` or ``ai-svodka-YYYY-MM-DD.png`` inside the
single FTP directory ``video``.
"""
from __future__ import annotations

import argparse
import ftplib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from cleanup_repository_content import MINIMUM_RETENTION_DAYS, resolve_reference_date

REMOTE_DIR = "video"
FTP_PORT = 21
FILE_PATTERN = re.compile(r"^ai-svodka-(\d{4}-\d{2}-\d{2})\.(mp4|png)$")


class VideoFtpCleanupError(RuntimeError):
    """Raised when the remote video cleanup cannot be proven safe."""


@dataclass(frozen=True)
class RemoteEntry:
    name: str
    entry_type: str
    size: int | None = None


def safe_listing_name(raw: str) -> str | None:
    """Accept only a basename or the same basename explicitly under ``video``."""
    value = raw.strip()
    if not value or "\x00" in value or "\\" in value:
        return None

    parts = PurePosixPath(value).parts
    if len(parts) == 1:
        name = parts[0]
    elif len(parts) == 2 and parts[0] == REMOTE_DIR:
        name = parts[1]
    elif len(parts) == 3 and parts[0] == "/" and parts[1] == REMOTE_DIR:
        name = parts[2]
    else:
        # NLST is allowed to prefix the current directory, but nested or foreign
        # paths are not reduced to basenames because that would broaden scope.
        return None

    if not name or name in {".", ".."} or "/" in name:
        return None
    return name


def _parse_size(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def list_remote_entries(ftp: Any) -> tuple[list[RemoteEntry], str]:
    """List the current ``video`` directory, preferring MLSD with NLST fallback."""
    try:
        rows = list(ftp.mlsd())
    except (AttributeError, ftplib.error_perm):
        rows = None

    if rows is not None:
        entries: dict[str, RemoteEntry] = {}
        for raw_name, facts in rows:
            name = safe_listing_name(raw_name)
            if name is None:
                continue
            facts = facts or {}
            entries[name] = RemoteEntry(
                name=name,
                entry_type=str(facts.get("type", "unknown")).casefold(),
                size=_parse_size(facts.get("size")),
            )
        return sorted(entries.values(), key=lambda row: row.name), "mlsd"

    entries: dict[str, RemoteEntry] = {}
    for raw_name in ftp.nlst():
        name = safe_listing_name(raw_name)
        if name is None:
            continue
        entries[name] = RemoteEntry(name=name, entry_type="unknown", size=None)
    return sorted(entries.values(), key=lambda row: row.name), "nlst"


def build_plan(
    entries: list[RemoteEntry],
    *,
    reference_date: date,
    retention_days: int,
) -> dict[str, Any]:
    if retention_days < MINIMUM_RETENTION_DAYS:
        raise VideoFtpCleanupError(
            f"retention_days must be at least {MINIMUM_RETENTION_DAYS}"
        )

    cutoff_date = reference_date - timedelta(days=retention_days)
    expired: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    invalid_managed: list[str] = []

    for entry in entries:
        if entry.entry_type not in {"file", "unknown"}:
            ignored.append({"name": entry.name, "reason": f"type={entry.entry_type}"})
            continue

        match = FILE_PATTERN.fullmatch(entry.name)
        if match is None:
            ignored.append({"name": entry.name, "reason": "outside managed pattern"})
            continue

        try:
            media_date = date.fromisoformat(match.group(1))
        except ValueError:
            invalid_managed.append(entry.name)
            continue

        row = {
            "name": entry.name,
            "publication_date": media_date.isoformat(),
            "kind": match.group(2),
            "size": entry.size,
        }
        if media_date < cutoff_date:
            expired.append(row)
        else:
            retained.append(row)

    # Validate the complete managed inventory before the first DELETE. A file
    # shaped like ours but carrying an impossible calendar date is ambiguity,
    # not permission to guess.
    if invalid_managed:
        raise VideoFtpCleanupError(
            "managed video filenames contain invalid dates: "
            + ", ".join(sorted(invalid_managed))
        )

    expired.sort(key=lambda row: (row["publication_date"], row["name"]))
    retained.sort(key=lambda row: (row["publication_date"], row["name"]))
    ignored.sort(key=lambda row: row["name"])
    return {
        "reference_date": reference_date.isoformat(),
        "retention_days": retention_days,
        "cutoff_date": cutoff_date.isoformat(),
        "deletion_rule": "publication_date < cutoff_date",
        "expired_files": expired,
        "retained_files": retained,
        "ignored_entries": ignored,
    }


def run_cleanup(
    ftp: Any,
    *,
    reference_date: date,
    retention_days: int,
    apply: bool,
) -> dict[str, Any]:
    """Plan or apply cleanup after hard-confining the FTP session to ``video``."""
    ftp.cwd(REMOTE_DIR)
    entries, listing_mode = list_remote_entries(ftp)
    plan = build_plan(
        entries,
        reference_date=reference_date,
        retention_days=retention_days,
    )
    expired = list(plan["expired_files"])
    deleted: list[str] = []

    if apply:
        for row in expired:
            name = str(row["name"])
            # Defense in depth: DELETE receives a basename only, never a path.
            if safe_listing_name(name) != name or FILE_PATTERN.fullmatch(name) is None:
                raise VideoFtpCleanupError(f"unsafe deletion target: {name!r}")
            ftp.delete(name)
            deleted.append(name)

        # Verify the remote state after mutation. A partial failure remains
        # retryable because the next run simply plans the remaining old files.
        remaining, _ = list_remote_entries(ftp)
        remaining_names = {row.name for row in remaining}
        still_present = [name for name in deleted if name in remaining_names]
        if still_present:
            raise VideoFtpCleanupError(
                "FTP verification found files that should have been deleted: "
                + ", ".join(still_present)
            )

    removed_bytes_known = sum(
        int(row["size"])
        for row in expired
        if row.get("size") is not None and row["name"] in deleted
    )
    removed_sizes_known = sum(
        1
        for row in expired
        if row.get("size") is not None and row["name"] in deleted
    )
    return {
        "status": "ok",
        "mode": "apply" if apply else "dry-run",
        "remote_dir": REMOTE_DIR,
        "listing_mode": listing_mode,
        "files_seen": len(entries),
        **plan,
        "changes_planned": bool(expired),
        "changes_applied": bool(deleted),
        "deleted_files": deleted,
        "deleted_count": len(deleted),
        "removed_bytes_known": removed_bytes_known,
        "removed_sizes_known": removed_sizes_known,
    }


def render_github_summary(report: dict[str, Any] | None, *, outcome: str) -> str:
    lines = ["# Видео и превью на FTP", ""]
    if outcome != "success" or report is None:
        return "\n".join(
            lines
            + [
                "❌ Очистка FTP-каталога `video/` не подтверждена.",
                "",
                "Неизвестные файлы и каталоги не удаляются автоматически.",
                "",
            ]
        )

    expired = report["expired_files"]
    mode = report["mode"]
    if mode == "dry-run":
        headline = (
            "🟡 Найдены старые video assets; это dry-run, ничего не удалено."
            if expired
            else "✅ Старых video assets нет; dry-run завершён."
        )
    elif expired:
        headline = "✅ Старые MP4/PNG удалены из FTP-каталога `video/`."
    else:
        headline = "✅ FTP-каталог `video/` уже соответствует retention policy."

    lines.extend(
        [
            headline,
            "",
            f"- Граница: удаляются только файлы раньше **{report['cutoff_date']}**.",
            "- Управляемый шаблон: `ai-svodka-YYYY-MM-DD.mp4` и `.png`.",
            f"- Найдено старых файлов: **{len(expired)}**.",
            f"- Удалено: **{report['deleted_count']}**.",
            (
                "- Неуправляемых записей, оставленных без изменений: "
                f"**{len(report['ignored_entries'])}**."
            ),
            "",
        ]
    )
    if expired:
        lines.extend(
            [
                "| Дата | Тип | Файл | Итог |",
                "|---|---|---|---|",
            ]
        )
        deleted = set(report["deleted_files"])
        for row in expired:
            if mode == "dry-run":
                result = "не удалено (dry-run)"
            elif row["name"] in deleted:
                result = "удалено"
            else:
                result = "не удалено"
            lines.append(
                f"| {row['publication_date']} | {row['kind']} | "
                f"<code>{row['name']}</code> | {result} |"
            )
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retention-days", type=int, default=MINIMUM_RETENTION_DAYS)
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--reference-date")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise VideoFtpCleanupError(f"required environment variable is missing: {name}")
    return value


def main() -> int:
    args = parse_args()
    report: dict[str, Any] = {
        "status": "error",
        "mode": "apply" if args.apply else "dry-run",
        "remote_dir": REMOTE_DIR,
    }
    ftp: ftplib.FTP | None = None
    exit_code = 1
    try:
        reference_date = resolve_reference_date(args.reference_date, args.timezone)
        server = _required_env("FTP_SERVER")
        username = _required_env("FTP_USERNAME")
        password = _required_env("FTP_PASSWORD")
        if "://" in server or "/" in server or "\\" in server:
            raise VideoFtpCleanupError(
                "FTP_SERVER must contain only the server hostname"
            )

        ftp = ftplib.FTP()
        ftp.connect(server, FTP_PORT, timeout=args.timeout)
        ftp.login(username, password)
        ftp.set_pasv(True)
        report = run_cleanup(
            ftp,
            reference_date=reference_date,
            retention_days=args.retention_days,
            apply=args.apply,
        )
        exit_code = 0
    except Exception as exc:
        report.update(status="error", error=f"{type(exc).__name__}: {exc}")
        exit_code = 1
    finally:
        if ftp is not None:
            try:
                ftp.quit()
            except Exception:
                try:
                    ftp.close()
                except Exception:
                    pass
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
