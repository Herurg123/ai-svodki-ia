#!/usr/bin/env python3
"""Restore the complete editorial artifact from a saved workflow artifact.

The failed image step can leave multiple copies of digest.json. This script
selects a complete editorial directory deterministically and rejects incomplete
or wrong-date candidates instead of copying the first filesystem match.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

REQUIRED_FILES = (
    "run-info.json",
    "candidates.json",
    "selection.json",
    "digest.json",
    "stories.json",
    "sources.json",
    "meta.json",
    "editorial-output-raw.json",
    "metadata-normalization.json",
    "editorial-output.json",
)
IMAGE_STAGE_FILES = (
    "cover.png",
    "image-source.json",
    "image-request.json",
    "image-manifest.json",
    "image-api-response.json",
    "image-api-error.json",
    "cover-validation.json",
    "artifact-validation.json",
)


class RecoveryError(RuntimeError):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"Не удалось прочитать {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def digest_date(payload: Any) -> str:
    if isinstance(payload, dict):
        value = payload.get("date")
        if isinstance(value, str):
            return value
        nested = payload.get("digest")
        if isinstance(nested, dict) and isinstance(nested.get("date"), str):
            return nested["date"]
    return ""


def candidate_score(path: Path) -> tuple[int, int, str]:
    rendered = path.as_posix()
    image_penalty = 1 if "/production-daily/image/" in f"/{rendered}/" else 0
    return image_penalty, len(path.parts), rendered


def choose_source(recovery_root: Path, publication_date: str) -> tuple[Path, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    complete: list[Path] = []
    for digest_path in sorted(recovery_root.rglob("digest.json")):
        source_dir = digest_path.parent
        missing = [name for name in REQUIRED_FILES if not (source_dir / name).is_file()]
        try:
            found_date = digest_date(read_json(digest_path))
        except RecoveryError as exc:
            diagnostics.append(
                {
                    "directory": str(source_dir),
                    "status": "invalid-json",
                    "error": str(exc),
                }
            )
            continue
        row = {
            "directory": str(source_dir),
            "date": found_date,
            "missing_files": missing,
        }
        if found_date != publication_date:
            row["status"] = "wrong-date"
        elif missing:
            row["status"] = "incomplete"
        else:
            row["status"] = "complete"
            complete.append(source_dir)
        diagnostics.append(row)

    if not complete:
        raise RecoveryError(
            f"В recovery artifact нет полного editorial-каталога за {publication_date}"
        )
    return sorted(complete, key=candidate_score)[0], diagnostics


def recover(
    recovery_root: Path,
    target_dir: Path,
    publication_date: str,
    report_path: Path,
) -> dict[str, Any]:
    if not recovery_root.is_dir():
        raise RecoveryError(f"Recovery artifact не найден: {recovery_root}")
    source_dir, diagnostics = choose_source(recovery_root, publication_date)

    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)

    removed: list[str] = []
    for name in IMAGE_STAGE_FILES:
        path = target_dir / name
        if path.exists():
            path.unlink()
            removed.append(name)

    report = {
        "status": "ok",
        "publication_date": publication_date,
        "recovery_root": str(recovery_root),
        "selected_source": str(source_dir),
        "target_dir": str(target_dir),
        "removed_image_stage_files": removed,
        "candidates": diagnostics,
    }
    write_json(report_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovery-root", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = recover(
            args.recovery_root,
            args.target_dir,
            args.publication_date,
            args.report,
        )
    except RecoveryError as exc:
        write_json(
            args.report,
            {
                "status": "error",
                "publication_date": args.publication_date,
                "recovery_root": str(args.recovery_root),
                "error": str(exc),
            },
        )
        print(f"Digest recovery failed: {exc}")
        return 1
    print(f"Digest recovery: ok; selected {report['selected_source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
