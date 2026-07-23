#!/usr/bin/env python3
"""Validate a paid digest request before any OpenAI API call.

The validator is deliberately offline. It validates the triggering Git diff,
request schema, request-id uniqueness, and saved-research fixture integrity.
It can write both a JSON report and GitHub Actions step outputs.
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
from typing import Any, Iterable

REQUEST_REL = Path("automation/requests/digest-preview.json")
RESEARCH_ROOT_REL = Path("automation/fixtures/research")
EXPECTED_KEYS = {
    "enabled",
    "mode",
    "research_input",
    "publication_date",
    "request_id",
    "minimum_candidates",
    "minimum_russian_candidates",
    "maximum_candidates",
    "minimum_selected_stories",
    "maximum_selected_stories",
}
NUMERIC_FIELDS = (
    "minimum_candidates",
    "minimum_russian_candidates",
    "maximum_candidates",
    "minimum_selected_stories",
    "maximum_selected_stories",
)
REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
ZERO_SHA_RE = re.compile(r"0{40,64}")


class PreflightError(ValueError):
    """A deterministic validation failure that must block the paid workflow."""


@dataclass(frozen=True)
class ValidatedRequest:
    mode: str
    research_input: str
    publication_date: str
    request_id: str
    numeric_fields: dict[str, int]
    fixture_sha256: str | None
    fixture_candidates: int | None


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


def safe_relative_path(repo_root: Path, raw: str, allowed_root_rel: Path) -> tuple[Path, str]:
    relative = Path(raw)
    if relative.is_absolute():
        raise PreflightError("research_input должен быть относительным путём внутри репозитория")
    resolved = (repo_root / relative).resolve()
    allowed_root = (repo_root / allowed_root_rel).resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise PreflightError(
            f"research_input должен находиться внутри {allowed_root_rel.as_posix()}/"
        ) from exc
    normalized = resolved.relative_to(repo_root.resolve()).as_posix()
    return resolved, normalized


def validate_request_payload(payload: dict[str, Any], repo_root: Path) -> ValidatedRequest:
    actual_keys = set(payload)
    if actual_keys != EXPECTED_KEYS:
        missing = sorted(EXPECTED_KEYS - actual_keys)
        extra = sorted(actual_keys - EXPECTED_KEYS)
        raise PreflightError(
            "digest-preview.json имеет неверный набор полей. "
            f"Отсутствуют: {missing}; лишние: {extra}"
        )

    if payload["enabled"] is not True:
        raise PreflightError("digest-preview.json: enabled должен быть true")

    mode = str(payload["mode"])
    if mode not in {"full", "editorial_only"}:
        raise PreflightError("mode должен быть full или editorial_only")

    publication_date = strict_date(payload["publication_date"], "publication_date")

    request_id = str(payload["request_id"])
    if REQUEST_ID_RE.fullmatch(request_id) is None:
        raise PreflightError(
            "request_id должен содержать только латинские буквы, цифры, "
            "точку, дефис или подчёркивание"
        )

    numeric_fields: dict[str, int] = {}
    for key in NUMERIC_FIELDS:
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise PreflightError(f"{key} должен быть целым числом")
        numeric_fields[key] = value

    if not (
        1
        <= numeric_fields["minimum_candidates"]
        <= numeric_fields["maximum_candidates"]
        <= 24
    ):
        raise PreflightError(
            "Требуется 1 <= minimum_candidates <= maximum_candidates <= 24"
        )
    if not (
        0
        <= numeric_fields["minimum_russian_candidates"]
        <= numeric_fields["maximum_candidates"]
    ):
        raise PreflightError("minimum_russian_candidates имеет недопустимое значение")
    if not (
        1
        <= numeric_fields["minimum_selected_stories"]
        <= numeric_fields["maximum_selected_stories"]
        <= 15
    ):
        raise PreflightError(
            "Требуется 1 <= minimum_selected_stories "
            "<= maximum_selected_stories <= 15"
        )

    research_input = payload["research_input"]
    fixture_sha256: str | None = None
    fixture_candidates: int | None = None
    research_input_text = ""

    if mode == "full":
        if research_input is not None:
            raise PreflightError("При mode=full поле research_input должно быть null")
    else:
        if not isinstance(research_input, str) or not research_input.strip():
            raise PreflightError(
                "При mode=editorial_only research_input должен быть непустым путём"
            )
        fixture_path, research_input_text = safe_relative_path(
            repo_root, research_input, RESEARCH_ROOT_REL
        )
        if not fixture_path.is_file():
            raise PreflightError(f"Файл research_input не найден: {research_input_text}")
        fixture = load_json(fixture_path, research_input_text)
        fixture_date = strict_date(
            fixture.get("publication_date"),
            f"{research_input_text}: publication_date",
        )
        if fixture_date != publication_date:
            raise PreflightError(
                "publication_date request не совпадает с publication_date research fixture: "
                f"{publication_date} != {fixture_date}"
            )
        fixture_status = fixture.get("status")
        if fixture_status not in {None, "ok", "success"}:
            raise PreflightError(
                f"Research fixture имеет неуспешный status: {fixture_status!r}"
            )
        candidates = fixture.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise PreflightError("Research fixture должен содержать непустой candidates[]")
        fixture_candidates = len(candidates)
        fixture_sha256 = hashlib.sha256(fixture_path.read_bytes()).hexdigest()

    return ValidatedRequest(
        mode=mode,
        research_input=research_input_text,
        publication_date=publication_date,
        request_id=request_id,
        numeric_fields=numeric_fields,
        fixture_sha256=fixture_sha256,
        fixture_candidates=fixture_candidates,
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


def request_from_git(repo_root: Path, revision: str, request_rel: Path) -> dict[str, Any] | None:
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
    repo_root: Path,
    before_sha: str,
    request_rel: Path,
) -> dict[str, list[str]]:
    commits = [
        line.strip()
        for line in run_git(
            repo_root,
            "rev-list",
            before_sha,
            "--",
            request_rel.as_posix(),
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


def append_github_outputs(path: Path, request: ValidatedRequest) -> None:
    rows = {
        "mode": request.mode,
        "research_input": request.research_input,
        "publication_date": request.publication_date,
        "request_id": request.request_id,
        "fixture_sha256": request.fixture_sha256 or "",
        "fixture_candidates": ""
        if request.fixture_candidates is None
        else str(request.fixture_candidates),
        **{key: str(value) for key, value in request.numeric_fields.items()},
    }
    with path.open("a", encoding="utf-8") as stream:
        for key, value in rows.items():
            if "\n" in value or "\r" in value:
                raise PreflightError(f"GitHub output {key} содержит перевод строки")
            stream.write(f"{key}={value}\n")


def validate_preflight(
    *,
    repo_root: Path,
    request_rel: Path,
    before_sha: str,
    current_sha: str,
    expected_ref: str | None,
    actual_ref: str | None,
) -> tuple[dict[str, Any], ValidatedRequest]:
    if expected_ref and actual_ref != expected_ref:
        raise PreflightError(
            f"Workflow разрешён только для {expected_ref}; получено {actual_ref!r}"
        )

    repo_root = repo_root.resolve()
    request_path = (repo_root / request_rel).resolve()
    if not request_path.is_file():
        raise PreflightError(f"Request-файл не найден: {request_rel.as_posix()}")

    current_sha_resolved = run_git(repo_root, "rev-parse", current_sha).strip()
    before_sha_resolved = normalize_before_sha(
        repo_root, before_sha, current_sha_resolved
    )

    files = changed_files(repo_root, before_sha_resolved, current_sha_resolved)
    expected_files = [request_rel.as_posix()]
    if files != expected_files:
        raise PreflightError(
            "Платный workflow разрешён только для отдельного commit, изменяющего "
            f"ровно {request_rel.as_posix()}. Изменены: {files}"
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
        "validator": "paid-request-preflight",
        "status": "ok",
        "request_path": request_rel.as_posix(),
        "before_sha": before_sha_resolved,
        "current_sha": current_sha_resolved,
        "changed_files": files,
        "previous_request_id": previous_id,
        "request": {
            "mode": validated.mode,
            "research_input": validated.research_input or None,
            "publication_date": validated.publication_date,
            "request_id": validated.request_id,
            **validated.numeric_fields,
        },
        "fixture": {
            "sha256": validated.fixture_sha256,
            "candidates": validated.fixture_candidates,
        },
        "errors": [],
    }
    return report, validated


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--request", type=Path, default=REQUEST_REL)
    parser.add_argument("--before-sha", default=os.environ.get("BEFORE_SHA", ""))
    parser.add_argument("--current-sha", default=os.environ.get("GITHUB_SHA", "HEAD"))
    parser.add_argument("--actual-ref", default=os.environ.get("GITHUB_REF"))
    parser.add_argument("--expected-ref", default="refs/heads/automation-prep")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("automation/preview/preflight/request-preflight.json"),
    )
    parser.add_argument("--github-output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = args.report
    try:
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
        print("Paid request preflight: ok")
        print(f"Request ID: {request.request_id}")
        print(f"Mode: {request.mode}")
        print(f"Changed files: {report['changed_files']}")
        if request.fixture_sha256:
            print(f"Research fixture SHA-256: {request.fixture_sha256}")
        print(f"Report: {report_path}")
        return 0
    except (PreflightError, OSError) as exc:
        error_report = {
            "validator": "paid-request-preflight",
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
        print(f"Paid request preflight: error: {exc}", file=sys.stderr)
        print(f"Report: {report_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
