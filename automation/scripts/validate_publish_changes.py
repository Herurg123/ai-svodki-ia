#!/usr/bin/env python3
"""Validate and stage only canonical production release changes.

Runtime outputs under automation/preview and automation/recovery are expected
working-tree files. They must never be committed, but their presence must not
block a valid production commit.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Iterable


class PublishChangesError(RuntimeError):
    pass


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_paths() -> list[str]:
    paths = set(git_lines("diff", "--name-only"))
    paths.update(git_lines("diff", "--cached", "--name-only"))
    paths.update(git_lines("ls-files", "--others", "--exclude-standard"))
    return sorted(paths)


def is_under(path: str, prefix: str) -> bool:
    return path == prefix.rstrip("/") or path.startswith(prefix)


def classify_paths(paths: Iterable[str], publication_date: str) -> dict[str, list[str]]:
    publish_prefixes = (
        "posts/",
        f"automation/content/{publication_date}/",
    )
    publish_exact = {"automation/archive/index.json"}
    transient_prefixes = (
        "automation/preview/",
        "automation/recovery/",
    )

    result = {"publish": [], "transient": [], "unexpected": []}
    for path in paths:
        if path in publish_exact or any(is_under(path, p) for p in publish_prefixes):
            result["publish"].append(path)
        elif any(is_under(path, p) for p in transient_prefixes):
            result["transient"].append(path)
        else:
            result["unexpected"].append(path)
    return result


def write_report(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_and_stage(publication_date: str, report_path: Path | None = None) -> dict[str, object]:
    before = changed_paths()
    classified = classify_paths(before, publication_date)
    if classified["unexpected"]:
        report = {
            "status": "error",
            "publication_date": publication_date,
            "changed_paths": before,
            **classified,
            "error": "unexpected repository changes",
        }
        write_report(report_path, report)
        raise PublishChangesError(
            f"Unexpected changed paths: {classified['unexpected']}"
        )

    stage_targets = [
        "posts",
        f"automation/content/{publication_date}",
        "automation/archive/index.json",
    ]
    subprocess.run(
        ["git", "add", "--", *stage_targets],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    staged = git_lines("diff", "--cached", "--name-only")
    staged_classified = classify_paths(staged, publication_date)
    if staged_classified["unexpected"] or staged_classified["transient"]:
        bad = staged_classified["unexpected"] + staged_classified["transient"]
        report = {
            "status": "error",
            "publication_date": publication_date,
            "changed_paths": before,
            "staged_paths": staged,
            **classified,
            "error": f"non-publish paths were staged: {bad}",
        }
        write_report(report_path, report)
        raise PublishChangesError(f"Non-publish paths staged: {bad}")
    if not staged:
        report = {
            "status": "error",
            "publication_date": publication_date,
            "changed_paths": before,
            "staged_paths": [],
            **classified,
            "error": "no production changes found",
        }
        write_report(report_path, report)
        raise PublishChangesError("No production changes found")

    report = {
        "status": "ok",
        "publication_date": publication_date,
        "changed_paths": before,
        "publish_paths": classified["publish"],
        "transient_paths_ignored": classified["transient"],
        "staged_paths": staged,
    }
    write_report(report_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = validate_and_stage(args.publication_date, args.report)
    except (PublishChangesError, subprocess.CalledProcessError) as exc:
        print(f"Publish change validation failed: {exc}")
        return 1
    print(
        "Publish change validation: ok; staged "
        f"{len(report['staged_paths'])} path(s); ignored "
        f"{len(report['transient_paths_ignored'])} runtime path(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
