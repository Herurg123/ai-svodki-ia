from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from release_common import ROOT, current_iso, relative_to_root, resolve_from_root, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверить, что dry-run workflows не умеют публиковать.")
    parser.add_argument("--workflow", action="append", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


FORBIDDEN_PATTERNS = {
    "schedule_trigger": re.compile(r"(?m)^\s*schedule\s*:"),
    "write_permission": re.compile(r"(?mi)^\s*contents\s*:\s*write\s*$"),
    "secret_reference": re.compile(r"\$\{\{\s*secrets\."),
    "production_environment": re.compile(r"(?mi)^\s*environment\s*:\s*production\s*$"),
    "deploy_action": re.compile(r"FTP-Deploy-Action", re.IGNORECASE),
    "main_push_trigger": re.compile(r"(?m)^\s*-\s*main\s*$"),
    "repository_mutation": re.compile(
        r"(?mi)^\s*(?:-\s*)?(?:run\s*:\s*)?(?:git\s+(?:add|commit|push)|gh\s+api\b)"
    ),
    "external_transfer": re.compile(
        r"(?mi)^\s*(?:-\s*)?(?:run\s*:\s*)?(?:curl|wget|scp|rsync|ftp|sftp)\b"
    ),
    "workflow_run_trigger": re.compile(r"(?m)^\s*workflow_run\s*:"),
    "repository_dispatch_trigger": re.compile(r"(?m)^\s*repository_dispatch\s*:"),
}


def validate_workflows(paths: list[Path], report_path: Path) -> dict:
    errors: list[dict[str, str]] = []
    checked: list[dict[str, object]] = []
    for path in paths:
        resolved = resolve_from_root(path)
        try:
            relative = resolved.relative_to((ROOT / ".github" / "workflows").resolve())
        except ValueError as exc:
            raise RuntimeError(f"Workflow должен находиться внутри .github/workflows/: {resolved}") from exc
        text = resolved.read_text(encoding="utf-8")
        matches: list[str] = []
        for code, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                matches.append(code)
                errors.append(
                    {
                        "code": code,
                        "workflow": relative.as_posix(),
                        "message": f"Запрещённая возможность обнаружена: {code}",
                    }
                )
        required = {
            "contents_read": bool(re.search(r"(?mi)^\s*contents\s*:\s*read\s*$", text)),
            "checkout_read_only": "persist-credentials: false" in text,
            "preview_branch": bool(re.search(r"(?m)^\s*-\s*automation-prep\s*$", text)),
        }
        for key, present in required.items():
            if not present:
                errors.append(
                    {
                        "code": f"missing_{key}",
                        "workflow": relative.as_posix(),
                        "message": f"Не выполнено обязательное условие: {key}",
                    }
                )
        checked.append(
            {
                "path": relative.as_posix(),
                "forbidden_matches": matches,
                "required": required,
            }
        )
    report = {
        "schema_version": 1,
        "status": "ok" if not errors else "error",
        "checked_at": current_iso(),
        "workflows": checked,
        "errors": errors,
    }
    write_json(resolve_from_root(report_path), report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = validate_workflows(args.workflow, args.report)
        if report["status"] != "ok":
            for error in report["errors"]:
                print(f"{error['workflow']}: {error['code']}", file=sys.stderr)
            return 1
        print(f"Workflow safety: ok ({len(report['workflows'])} files)")
        return 0
    except Exception as exc:
        print(f"Workflow safety validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
