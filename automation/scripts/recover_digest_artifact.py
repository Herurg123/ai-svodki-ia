#!/usr/bin/env python3
"""Restore a reusable full, partial-editorial, or research-only artifact.

A failed production run may contain completed paid research even when the
editorial policy or coverage gate failed before canonical digest files were
written. Recovery must preserve that work instead of forcing a second full
research pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

FULL_REQUIRED_FILES = (
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
PARTIAL_EDITORIAL_FILES = (
    "run-info.json",
    "candidates.json",
    "research-output-raw.json",
    "editorial-output-raw.json",
    "editorial-output.json",
)
RESEARCH_ONLY_FILES = (
    "run-info.json",
    "candidates.json",
    "research-output-raw.json",
)
# Backward-compatible public name used by existing unit tests.
REQUIRED_FILES = FULL_REQUIRED_FILES
IMAGE_STAGE_FILES = (
    "cover.png",
    "image-source.json",
    "image-request.json",
    "image-manifest.json",
    "image-api-response.json",
    "image-api-error.json",
    "cover-validation.json",
    "artifact-validation.json",
    "artifact-normalization.json",
)

IMAGE_RECOVERY_REQUIRED = (
    "cover.png",
    "image-manifest.json",
    "cover-validation.json",
    "digest.json",
    "article.html",
    "stories.json",
    "sources.json",
    "meta.json",
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


def artifact_date(source_dir: Path) -> str:
    for name in ("candidates.json", "digest.json", "editorial-output.json", "run-info.json"):
        path = source_dir / name
        if not path.is_file():
            continue
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        for key in ("publication_date", "date"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        digest = payload.get("digest")
        if isinstance(digest, dict):
            value = digest.get("date")
            if isinstance(value, str) and value:
                return value
    return ""


def research_is_reusable(source_dir: Path) -> tuple[bool, str | None]:
    run_info = read_json(source_dir / "run-info.json")
    candidates = read_json(source_dir / "candidates.json")
    if not isinstance(run_info, dict):
        return False, "run-info.json должен содержать объект"
    research = run_info.get("research")
    if not isinstance(research, dict) or research.get("status") != "ok":
        return False, "research.status не равен ok"
    if not isinstance(candidates, dict) or not isinstance(candidates.get("candidates"), list):
        return False, "candidates.json не содержит candidates[]"
    return True, None


def classify_source(source_dir: Path) -> tuple[str | None, list[str]]:
    missing_full = [name for name in FULL_REQUIRED_FILES if not (source_dir / name).is_file()]
    if not missing_full:
        return "full", []
    missing_partial = [
        name for name in PARTIAL_EDITORIAL_FILES if not (source_dir / name).is_file()
    ]
    if not missing_partial:
        return "partial_editorial", missing_full
    missing_research = [
        name for name in RESEARCH_ONLY_FILES if not (source_dir / name).is_file()
    ]
    if not missing_research:
        return "research_only", missing_full
    return None, missing_research


def candidate_score(item: tuple[Path, str]) -> tuple[int, int, int, str]:
    path, mode = item
    rendered = path.as_posix()
    mode_rank = {"full": 0, "partial_editorial": 1, "research_only": 2}[mode]
    image_penalty = 1 if "/production-daily/image/" in f"/{rendered}/" else 0
    return mode_rank, image_penalty, len(path.parts), rendered


def choose_source(
    recovery_root: Path,
    publication_date: str,
) -> tuple[Path, str, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    reusable: list[tuple[Path, str]] = []
    seen: set[Path] = set()

    for marker in sorted(recovery_root.rglob("run-info.json")):
        source_dir = marker.parent
        if source_dir in seen:
            continue
        seen.add(source_dir)
        mode, missing = classify_source(source_dir)
        row: dict[str, Any] = {
            "directory": str(source_dir),
            "mode": mode,
            "missing_files": missing,
        }
        if mode is None:
            row["status"] = "incomplete"
            diagnostics.append(row)
            continue
        try:
            found_date = artifact_date(source_dir)
        except RecoveryError as exc:
            row["status"] = "invalid-json"
            row["error"] = str(exc)
            diagnostics.append(row)
            continue
        row["date"] = found_date
        if found_date != publication_date:
            row["status"] = "wrong-date"
            diagnostics.append(row)
            continue
        if mode == "full":
            usable, reason = True, None
        else:
            try:
                usable, reason = research_is_reusable(source_dir)
            except RecoveryError as exc:
                usable, reason = False, str(exc)
        if not usable:
            row["status"] = "unusable"
            row["error"] = reason
            diagnostics.append(row)
            continue
        row["status"] = "reusable"
        reusable.append((source_dir, mode))
        diagnostics.append(row)

    if not reusable:
        raise RecoveryError(
            f"В recovery artifact нет пригодного research/editorial-каталога за {publication_date}"
        )
    selected_dir, selected_mode = sorted(reusable, key=candidate_score)[0]
    return selected_dir, selected_mode, diagnostics


def validate_recovery_freshness(
    source_dir: Path,
    publication_date: str,
    timezone_name: str,
) -> dict[str, str]:
    run_info = read_json(source_dir / "run-info.json")
    if not isinstance(run_info, dict):
        raise RecoveryError("run-info.json должен содержать JSON-объект")
    finished_at = run_info.get("finished_at")
    if not isinstance(finished_at, str) or not finished_at.strip():
        raise RecoveryError("run-info.json не содержит finished_at для проверки свежести")
    try:
        finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoveryError(f"Некорректный finished_at: {finished_at}") from exc
    if finished.tzinfo is None:
        raise RecoveryError("finished_at должен содержать часовой пояс")
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise RecoveryError(f"Некорректный timezone: {timezone_name}") from exc
    local_finished = finished.astimezone(timezone)
    local_date = local_finished.date().isoformat()
    if local_date != publication_date:
        raise RecoveryError(
            "Recovery artifact устарел: research/editorial завершён "
            f"{local_finished.isoformat(timespec='seconds')}, "
            f"а выпуск имеет дату {publication_date}"
        )
    return {
        "finished_at": finished.isoformat(timespec="seconds"),
        "finished_at_local": local_finished.isoformat(timespec="seconds"),
        "timezone": timezone_name,
        "local_date": local_date,
    }



def restore_merged_coverage_research(
    recovery_root: Path,
    target_dir: Path,
    publication_date: str,
) -> dict[str, Any] | None:
    name = f"coverage-audit-merged-candidates-{publication_date}.json"
    matches = sorted(path for path in recovery_root.rglob(name) if path.is_file())
    for path in matches:
        try:
            payload = read_json(path)
        except RecoveryError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("publication_date") != publication_date:
            continue
        if not isinstance(payload.get("candidates"), list):
            continue
        write_json(target_dir / "candidates.json", payload)
        write_json(target_dir / "research-output-raw.json", payload)
        return {
            "source": str(path),
            "candidate_count": len(payload["candidates"]),
        }
    return None

def restore_completed_coverage_audit(
    recovery_root: Path,
    report_path: Path,
    publication_date: str,
) -> dict[str, Any] | None:
    """Restore a completed paid coverage audit beside the recovery report.

    ensure_story_coverage.py reads this exact path before deciding whether a
    targeted web search is needed. Restoring the report prevents a manual
    recovery run from paying for the same completed audit twice.
    """

    target = report_path.parent / "coverage-audit.json"
    matches = sorted(
        path for path in recovery_root.rglob("coverage-audit.json") if path.is_file()
    )
    for path in matches:
        try:
            payload = read_json(path)
        except RecoveryError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("publication_date") != publication_date:
            continue
        api = payload.get("api")
        if payload.get("web_search_performed") is not True:
            continue
        if not isinstance(api, dict) or api.get("status") != "completed":
            continue
        write_json(target, payload)
        return {
            "source": str(path),
            "target": str(target),
            "web_search_calls": api.get("web_search_calls"),
        }
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def choose_reusable_image_source(
    recovery_root: Path,
    publication_date: str,
) -> tuple[Path | None, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    valid: list[Path] = []

    for manifest_path in sorted(recovery_root.rglob("image-manifest.json")):
        source_dir = manifest_path.parent
        row: dict[str, Any] = {"directory": str(source_dir)}
        missing = [name for name in IMAGE_RECOVERY_REQUIRED if not (source_dir / name).is_file()]
        if missing:
            row["status"] = "incomplete"
            row["missing_files"] = missing
            diagnostics.append(row)
            continue
        try:
            manifest = read_json(manifest_path)
            validation = read_json(source_dir / "cover-validation.json")
            found_date = artifact_date(source_dir)
        except RecoveryError as exc:
            row["status"] = "invalid"
            row["error"] = str(exc)
            diagnostics.append(row)
            continue
        if found_date != publication_date:
            row["status"] = "wrong-date"
            row["date"] = found_date
            diagnostics.append(row)
            continue
        if not isinstance(manifest, dict) or manifest.get("status") != "ok":
            row["status"] = "invalid-manifest"
            diagnostics.append(row)
            continue
        if not isinstance(validation, dict) or validation.get("status") != "ok":
            row["status"] = "invalid-cover-validation"
            diagnostics.append(row)
            continue
        expected_sha = str(manifest.get("sha256", "")).strip()
        actual_sha = sha256_file(source_dir / "cover.png")
        if not expected_sha or expected_sha != actual_sha:
            row["status"] = "cover-sha-mismatch"
            row["expected_sha256"] = expected_sha
            row["actual_sha256"] = actual_sha
            diagnostics.append(row)
            continue
        row["status"] = "reusable"
        row["cover_sha256"] = actual_sha
        diagnostics.append(row)
        valid.append(source_dir)

    if not valid:
        return None, diagnostics
    valid.sort(key=lambda path: (len(path.parts), path.as_posix()))
    return valid[0], diagnostics


def restore_reusable_image(
    recovery_root: Path,
    image_target_dir: Path | None,
    publication_date: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    source_dir, diagnostics = choose_reusable_image_source(
        recovery_root,
        publication_date,
    )
    if source_dir is None or image_target_dir is None:
        return None, diagnostics
    if image_target_dir.exists():
        shutil.rmtree(image_target_dir)
    image_target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, image_target_dir)
    return {
        "source": str(source_dir),
        "target": str(image_target_dir),
        "cover_sha256": sha256_file(image_target_dir / "cover.png"),
    }, diagnostics


def recover(
    recovery_root: Path,
    target_dir: Path,
    publication_date: str,
    report_path: Path,
    timezone_name: str = "Europe/Moscow",
    image_target_dir: Path | None = None,
) -> dict[str, Any]:
    if not recovery_root.is_dir():
        raise RecoveryError(f"Recovery artifact не найден: {recovery_root}")
    source_dir, recovery_mode, diagnostics = choose_source(
        recovery_root,
        publication_date,
    )
    freshness = validate_recovery_freshness(
        source_dir,
        publication_date,
        timezone_name,
    )

    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)

    merged_research = restore_merged_coverage_research(
        recovery_root,
        target_dir,
        publication_date,
    )
    completed_coverage_audit = restore_completed_coverage_audit(
        recovery_root,
        report_path,
        publication_date,
    )

    recovered_image, image_diagnostics = restore_reusable_image(
        recovery_root,
        image_target_dir,
        publication_date,
    )

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
        "recovery_mode": recovery_mode,
        "target_dir": str(target_dir),
        "removed_stage_files": removed,
        "merged_coverage_research": merged_research,
        "completed_coverage_audit": completed_coverage_audit,
        "image_recovered": recovered_image is not None,
        "recovered_image": recovered_image,
        "image_candidates": image_diagnostics,
        "freshness": freshness,
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
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--image-target-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = recover(
            args.recovery_root,
            args.target_dir,
            args.publication_date,
            args.report,
            args.timezone,
            args.image_target_dir,
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
    print(
        "Digest recovery: ok; "
        f"mode={report['recovery_mode']}; selected {report['selected_source']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
