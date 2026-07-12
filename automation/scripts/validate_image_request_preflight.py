#!/usr/bin/env python3
"""Validate an Image API preview request before any paid network call.

The validator is standard-library only. It verifies that the triggering commit
changes exactly the image request file, that request_id has never been used,
and that the saved editorial artifact is complete and hash-locked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

REQUEST_REL = Path("automation/requests/image-preview.json")
SOURCE_ROOT_REL = Path("automation/fixtures/editorial")
SOURCE_MANIFEST = "image-source.json"
EXPECTED_REQUEST_KEYS = {
    "enabled",
    "mode",
    "source",
    "publication_date",
    "request_id",
}
REQUIRED_SOURCE_FILES = {
    "article.html",
    "candidates.json",
    "digest.json",
    "editorial-output-raw.json",
    "editorial-output.json",
    "editorial-prompt-input.txt",
    "image-prompt.txt",
    "meta.json",
    "metadata-normalization.json",
    "policy-normalization.json",
    "research-filtered-out.json",
    "research-input-info.json",
    "research-output-raw.json",
    "research-prompt-input.txt",
    "run-info.json",
    "selection.json",
    "sources.json",
    "stories.json",
}
FORBIDDEN_SOURCE_FILES = {
    "cover.png",
    "image-request.json",
    "image-manifest.json",
    "image-api-response.json",
    "cover-validation.json",
}
REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
ZERO_SHA_RE = re.compile(r"0{40,64}")


class PreflightError(ValueError):
    """A deterministic failure that must block the paid image workflow."""


@dataclass(frozen=True)
class ValidatedImageRequest:
    source: str
    publication_date: str
    request_id: str
    source_manifest_sha256: str
    editorial_request_id: str
    editorial_commit: str
    digest_sha256: str
    title: str
    cover_filename: str
    prompt_sha256: str


def run_git(repo_root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PreflightError(f"git {' '.join(args)} завершился ошибкой: {detail}")
    return completed.stdout


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PreflightError(f"Не удалось прочитать {label}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError(f"{label} содержит некорректный JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PreflightError(f"{label} должен содержать JSON-объект")
    return payload


def strict_date(value: Any, field: str) -> str:
    text = str(value)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise PreflightError(f"{field} должна иметь строгий формат YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise PreflightError(f"{field} должна иметь строгий формат YYYY-MM-DD")
    return text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_source_directory(repo_root: Path, raw: str) -> tuple[Path, str]:
    relative = Path(raw)
    if relative.is_absolute():
        raise PreflightError("source должен быть относительным путём внутри репозитория")
    resolved = (repo_root / relative).resolve()
    allowed_root = (repo_root / SOURCE_ROOT_REL).resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise PreflightError(
            f"source должен находиться внутри {SOURCE_ROOT_REL.as_posix()}/"
        ) from exc
    if not resolved.is_dir():
        raise PreflightError(f"Каталог source не найден: {relative.as_posix()}")
    normalized = resolved.relative_to(repo_root.resolve()).as_posix()
    return resolved, normalized


def validate_source_directory(
    source_dir: Path,
    expected_publication_date: str | None = None,
) -> dict[str, Any]:
    manifest_path = source_dir / SOURCE_MANIFEST
    manifest = load_json(manifest_path, manifest_path.as_posix())

    if manifest.get("status") != "ok":
        raise PreflightError("image-source.json: status должен быть ok")
    if manifest.get("source_type") != "validated_editorial_artifact":
        raise PreflightError(
            "image-source.json: source_type должен быть validated_editorial_artifact"
        )
    if manifest.get("editorial_artifact_validation_status") != "ok":
        raise PreflightError("Редакционный artifact не имеет подтверждённого status=ok")
    if manifest.get("web_search_calls") != 0:
        raise PreflightError("Image source должен происходить из editorial_only с web_search_calls=0")
    if manifest.get("research_reused") is not True:
        raise PreflightError("Image source должен фиксировать research_reused=true")

    publication_date = strict_date(
        manifest.get("publication_date"),
        "image-source.json: publication_date",
    )
    if expected_publication_date and publication_date != expected_publication_date:
        raise PreflightError(
            "publication_date request не совпадает с image source: "
            f"{expected_publication_date} != {publication_date}"
        )

    editorial_request_id = str(manifest.get("editorial_request_id", "")).strip()
    editorial_commit = str(manifest.get("editorial_commit", "")).strip()
    if not editorial_request_id:
        raise PreflightError("image-source.json: отсутствует editorial_request_id")
    if re.fullmatch(r"[0-9a-f]{40}", editorial_commit) is None:
        raise PreflightError("image-source.json: editorial_commit должен быть SHA-1")

    files = manifest.get("files")
    if not isinstance(files, dict):
        raise PreflightError("image-source.json: files должен быть JSON-объектом")
    file_names = set(files)
    if file_names != REQUIRED_SOURCE_FILES:
        missing = sorted(REQUIRED_SOURCE_FILES - file_names)
        extra = sorted(file_names - REQUIRED_SOURCE_FILES)
        raise PreflightError(
            f"Неверный набор файлов image source. Отсутствуют: {missing}; лишние: {extra}"
        )

    actual_top_level = {
        path.name for path in source_dir.iterdir() if path.is_file()
    }
    expected_top_level = REQUIRED_SOURCE_FILES | {SOURCE_MANIFEST}
    if actual_top_level != expected_top_level:
        missing = sorted(expected_top_level - actual_top_level)
        extra = sorted(actual_top_level - expected_top_level)
        raise PreflightError(
            f"Каталог image source не совпадает с manifest. Отсутствуют: {missing}; лишние: {extra}"
        )

    for forbidden in FORBIDDEN_SOURCE_FILES:
        if (source_dir / forbidden).exists():
            raise PreflightError(f"Image source не должен содержать готовый output: {forbidden}")

    checked_files: list[dict[str, Any]] = []
    for name in sorted(REQUIRED_SOURCE_FILES):
        expected_hash = files.get(name)
        if not isinstance(expected_hash, str) or SHA256_RE.fullmatch(expected_hash) is None:
            raise PreflightError(f"Некорректный SHA-256 для {name}")
        path = source_dir / name
        if not path.is_file() or path.is_symlink():
            raise PreflightError(f"Не найден обычный файл image source: {name}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise PreflightError(
                f"SHA-256 не совпадает для {name}: {actual_hash} != {expected_hash}"
            )
        checked_files.append(
            {"path": name, "sha256": actual_hash, "size_bytes": path.stat().st_size}
        )

    digest = load_json(source_dir / "digest.json", "digest.json")
    if digest.get("status") != "ok":
        raise PreflightError("digest.json: status должен быть ok")
    digest_date = strict_date(digest.get("date"), "digest.json: date")
    if digest_date != publication_date:
        raise PreflightError("digest.json: date не совпадает с image-source.json")
    title = str(digest.get("title", "")).strip()
    cover_filename = str(digest.get("cover_filename", "")).strip()
    prompt = str(digest.get("image_prompt", "")).strip()
    if not all((title, cover_filename, prompt)):
        raise PreflightError(
            "digest.json должен содержать title, cover_filename и image_prompt"
        )
    if not cover_filename.endswith(".png") or Path(cover_filename).name != cover_filename:
        raise PreflightError("digest.cover_filename должен быть безопасным PNG-именем")

    prompt_file = (source_dir / "image-prompt.txt").read_text(encoding="utf-8").strip()
    if prompt_file != prompt:
        raise PreflightError("image-prompt.txt не совпадает с digest.image_prompt")

    run_info = load_json(source_dir / "run-info.json", "run-info.json")
    if run_info.get("status") != "ok":
        raise PreflightError("run-info.json: status должен быть ok")
    if run_info.get("request_id") != editorial_request_id:
        raise PreflightError("run-info.request_id не совпадает с editorial_request_id")
    total_usage = run_info.get("total_usage")
    if not isinstance(total_usage, dict) or total_usage.get("web_search_calls") != 0:
        raise PreflightError("run-info должен подтверждать web_search_calls=0")
    research = run_info.get("research")
    if not isinstance(research, dict):
        raise PreflightError("run-info.research отсутствует")
    response = research.get("response")
    if not isinstance(response, dict) or response.get("response_status") != "reused":
        raise PreflightError("run-info должен подтверждать переиспользованный research")

    return {
        "status": "ok",
        "publication_date": publication_date,
        "editorial_request_id": editorial_request_id,
        "editorial_commit": editorial_commit,
        "source_manifest_sha256": sha256_file(manifest_path),
        "digest_sha256": sha256_file(source_dir / "digest.json"),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "title": title,
        "cover_filename": cover_filename,
        "files": checked_files,
    }


def validate_request_payload(
    payload: dict[str, Any],
    repo_root: Path,
) -> ValidatedImageRequest:
    actual_keys = set(payload)
    if actual_keys != EXPECTED_REQUEST_KEYS:
        missing = sorted(EXPECTED_REQUEST_KEYS - actual_keys)
        extra = sorted(actual_keys - EXPECTED_REQUEST_KEYS)
        raise PreflightError(
            "image-preview.json имеет неверный набор полей. "
            f"Отсутствуют: {missing}; лишние: {extra}"
        )
    if payload.get("enabled") is not True:
        raise PreflightError("image-preview.json: enabled должен быть true")
    if payload.get("mode") != "image_api_preview":
        raise PreflightError("image-preview.json: mode должен быть image_api_preview")

    publication_date = strict_date(payload.get("publication_date"), "publication_date")
    request_id = str(payload.get("request_id", ""))
    if REQUEST_ID_RE.fullmatch(request_id) is None:
        raise PreflightError(
            "request_id должен содержать только латинские буквы, цифры, точку, дефис или подчёркивание"
        )
    raw_source = payload.get("source")
    if not isinstance(raw_source, str) or not raw_source.strip():
        raise PreflightError("source должен быть непустым путём")
    source_dir, normalized_source = safe_source_directory(repo_root, raw_source)
    source_report = validate_source_directory(source_dir, publication_date)

    return ValidatedImageRequest(
        source=normalized_source,
        publication_date=publication_date,
        request_id=request_id,
        source_manifest_sha256=str(source_report["source_manifest_sha256"]),
        editorial_request_id=str(source_report["editorial_request_id"]),
        editorial_commit=str(source_report["editorial_commit"]),
        digest_sha256=str(source_report["digest_sha256"]),
        title=str(source_report["title"]),
        cover_filename=str(source_report["cover_filename"]),
        prompt_sha256=str(source_report["prompt_sha256"]),
    )


def normalize_before_sha(repo_root: Path, before_sha: str, current_sha: str) -> str:
    if before_sha and ZERO_SHA_RE.fullmatch(before_sha) is None:
        run_git(repo_root, "cat-file", "-e", f"{before_sha}^{{commit}}")
        return before_sha
    parent = run_git(repo_root, "rev-parse", f"{current_sha}^").strip()
    if not parent:
        raise PreflightError("Не удалось определить предыдущий commit")
    return parent


def changed_files(repo_root: Path, before_sha: str, current_sha: str) -> list[str]:
    output = run_git(
        repo_root,
        "diff",
        "--name-only",
        "--diff-filter=ACMRDTUXB",
        before_sha,
        current_sha,
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def request_from_git(
    repo_root: Path, revision: str, request_rel: Path
) -> dict[str, Any] | None:
    completed = subprocess.run(
        ["git", "show", f"{revision}:{request_rel.as_posix()}"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightError(
            f"Предыдущая версия {request_rel.as_posix()} содержит некорректный JSON"
        ) from exc
    return payload if isinstance(payload, dict) else None


def historical_request_ids(
    repo_root: Path, before_sha: str, request_rel: Path
) -> dict[str, list[str]]:
    commits = [
        line.strip()
        for line in run_git(
            repo_root, "rev-list", before_sha, "--", request_rel.as_posix()
        ).splitlines()
        if line.strip()
    ]
    result: dict[str, list[str]] = {}
    for commit in commits:
        payload = request_from_git(repo_root, commit, request_rel)
        if not payload:
            continue
        value = payload.get("request_id")
        if isinstance(value, str) and value:
            result.setdefault(value, []).append(commit)
    return result


def validate_preflight(
    *,
    repo_root: Path,
    request_rel: Path,
    before_sha: str,
    current_sha: str,
    expected_ref: str | None,
    actual_ref: str | None,
) -> tuple[dict[str, Any], ValidatedImageRequest]:
    if expected_ref and actual_ref != expected_ref:
        raise PreflightError(
            f"Workflow разрешён только для {expected_ref}; получено {actual_ref!r}"
        )
    repo_root = repo_root.resolve()
    request_path = (repo_root / request_rel).resolve()
    if not request_path.is_file():
        raise PreflightError(f"Request-файл не найден: {request_rel.as_posix()}")

    current_sha_resolved = run_git(repo_root, "rev-parse", current_sha).strip()
    before_sha_resolved = normalize_before_sha(repo_root, before_sha, current_sha_resolved)
    files = changed_files(repo_root, before_sha_resolved, current_sha_resolved)
    expected_files = [request_rel.as_posix()]
    if files != expected_files:
        raise PreflightError(
            "Платный Image API workflow разрешён только для отдельного commit, "
            f"изменяющего ровно {request_rel.as_posix()}. Изменены: {files}"
        )

    payload = load_json(request_path, request_rel.as_posix())
    validated = validate_request_payload(payload, repo_root)

    previous = request_from_git(repo_root, before_sha_resolved, request_rel)
    previous_id = previous.get("request_id") if isinstance(previous, dict) else None
    if previous_id == validated.request_id:
        raise PreflightError(
            f"request_id не изменился относительно предыдущего commit: {validated.request_id}"
        )
    history = historical_request_ids(repo_root, before_sha_resolved, request_rel)
    reused_in = history.get(validated.request_id, [])
    if reused_in:
        raise PreflightError(
            f"request_id уже использовался ранее: {validated.request_id}; commits: {reused_in[:5]}"
        )

    report = {
        "validator": "image-request-preflight",
        "status": "ok",
        "request_path": request_rel.as_posix(),
        "before_sha": before_sha_resolved,
        "current_sha": current_sha_resolved,
        "changed_files": files,
        "previous_request_id": previous_id,
        "request": {
            "mode": "image_api_preview",
            "source": validated.source,
            "publication_date": validated.publication_date,
            "request_id": validated.request_id,
        },
        "source": {
            "manifest_sha256": validated.source_manifest_sha256,
            "digest_sha256": validated.digest_sha256,
            "prompt_sha256": validated.prompt_sha256,
            "editorial_request_id": validated.editorial_request_id,
            "editorial_commit": validated.editorial_commit,
            "title": validated.title,
            "cover_filename": validated.cover_filename,
        },
        "errors": [],
    }
    return report, validated


def append_github_outputs(path: Path, request: ValidatedImageRequest) -> None:
    rows = {
        "source": request.source,
        "publication_date": request.publication_date,
        "request_id": request.request_id,
        "source_manifest_sha256": request.source_manifest_sha256,
        "editorial_request_id": request.editorial_request_id,
        "editorial_commit": request.editorial_commit,
        "digest_sha256": request.digest_sha256,
        "prompt_sha256": request.prompt_sha256,
        "cover_filename": request.cover_filename,
    }
    with path.open("a", encoding="utf-8") as stream:
        for key, value in rows.items():
            if "\n" in value or "\r" in value:
                raise PreflightError(f"GitHub output {key} содержит перевод строки")
            stream.write(f"{key}={value}\n")


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--request", type=Path, default=REQUEST_REL)
    parser.add_argument("--before-sha", default=os.environ.get("BEFORE_SHA", ""))
    parser.add_argument("--current-sha", default=os.environ.get("GITHUB_SHA", "HEAD"))
    parser.add_argument("--actual-ref", default=os.environ.get("GITHUB_REF"))
    parser.add_argument("--expected-ref", default="refs/heads/automation-prep")
    parser.add_argument("--source-only", type=Path, default=None)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("automation/preview/image-preflight/request-preflight.json"),
    )
    parser.add_argument("--github-output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = args.report
    try:
        if args.source_only is not None:
            source_dir = (
                args.source_only
                if args.source_only.is_absolute()
                else (args.repo_root / args.source_only).resolve()
            )
            source = validate_source_directory(source_dir)
            report = {
                "validator": "image-source-preflight",
                "status": "ok",
                "source": source,
                "errors": [],
            }
            write_report(report_path, report)
            print("Image source preflight: ok")
            print(f"Source manifest SHA-256: {source['source_manifest_sha256']}")
            print(f"Report: {report_path}")
            return 0

        report, request = validate_preflight(
            repo_root=args.repo_root,
            request_rel=args.request,
            before_sha=args.before_sha,
            current_sha=args.current_sha,
            expected_ref=args.expected_ref,
            actual_ref=args.actual_ref,
        )
        write_report(report_path, report)
        if args.github_output is not None:
            append_github_outputs(args.github_output, request)
        print("Image request preflight: ok")
        print(f"Request ID: {request.request_id}")
        print(f"Editorial request: {request.editorial_request_id}")
        print(f"Changed files: {report['changed_files']}")
        print(f"Source manifest SHA-256: {request.source_manifest_sha256}")
        print(f"Report: {report_path}")
        return 0
    except (PreflightError, OSError) as exc:
        error_report = {
            "validator": "image-request-preflight",
            "status": "error",
            "request_path": args.request.as_posix(),
            "before_sha": args.before_sha,
            "current_sha": args.current_sha,
            "errors": [{"code": "preflight_failed", "message": str(exc)}],
        }
        try:
            write_report(report_path, error_report)
        except OSError:
            pass
        print(f"Image request preflight: error: {exc}", file=sys.stderr)
        print(f"Report: {report_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
