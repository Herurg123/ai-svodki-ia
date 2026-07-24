#!/usr/bin/env python3
"""Normalize deterministic digest fields before contract validation.

This utility performs no network requests. It is intentionally safe to run for
both freshly generated and recovered editorial artifacts. At present it repairs
legacy image prompts that predate the mandatory safety/style constraints.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONSTRAINTS = (
    "без логотипов",
    "без дополнительного текста",
    "без водяных знаков",
    "без узнаваемых лиц",
)
JSON_FILES = (
    "digest.json",
    "editorial-output.json",
    "editorial-output-raw.json",
)
TEXT_FILES = ("image-prompt.txt", "image_prompt.txt")


class NormalizationError(RuntimeError):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NormalizationError(f"Не найден обязательный файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise NormalizationError(f"Некорректный JSON {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_prompt(prompt: str) -> tuple[str, list[str]]:
    value = prompt.strip()
    if not value:
        raise NormalizationError("image_prompt пуст")

    lower = value.lower()
    missing = [constraint for constraint in CONSTRAINTS if constraint not in lower]
    if not missing:
        return value, []

    suffix = "Ограничения: " + "; ".join(missing) + "."
    separator = "\n" if value.endswith((".", ";", ":")) else ".\n"
    normalized = value + separator + suffix
    return normalized, missing


def normalize_json_prompts(payload: Any, *, path: str = "$") -> tuple[Any, list[dict[str, Any]]]:
    changes: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in list(payload.items()):
            child_path = f"{path}.{key}"
            if key == "image_prompt" and isinstance(value, str):
                normalized, missing = normalize_prompt(value)
                if missing:
                    payload[key] = normalized
                    changes.append(
                        {
                            "field": child_path,
                            "added_constraints": missing,
                        }
                    )
            else:
                _, nested_changes = normalize_json_prompts(value, path=child_path)
                changes.extend(nested_changes)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _, nested_changes = normalize_json_prompts(value, path=f"{path}[{index}]")
            changes.extend(nested_changes)
    return payload, changes


def normalize_artifact(artifact_dir: Path, report_path: Path) -> dict[str, Any]:
    if not artifact_dir.is_dir():
        raise NormalizationError(f"Каталог artifact не найден: {artifact_dir}")

    report: dict[str, Any] = {
        "status": "ok",
        "artifact_dir": str(artifact_dir),
        "changed_files": [],
        "changes": [],
    }
    prompt_locations = 0

    for name in JSON_FILES:
        path = artifact_dir / name
        if not path.is_file():
            if name == "digest.json":
                raise NormalizationError(f"Не найден обязательный файл: {path}")
            continue
        payload = read_json(path)
        normalized, changes = normalize_json_prompts(payload)
        prompt_locations += sum(1 for change in changes) or _count_prompts(payload)
        if changes:
            write_json(path, normalized)
            report["changed_files"].append(name)
            report["changes"].extend(
                {"file": name, **change} for change in changes
            )

    for name in TEXT_FILES:
        path = artifact_dir / name
        if not path.is_file():
            continue
        prompt_locations += 1
        original = path.read_text(encoding="utf-8")
        normalized, missing = normalize_prompt(original)
        if missing:
            path.write_text(normalized + "\n", encoding="utf-8")
            report["changed_files"].append(name)
            report["changes"].append(
                {
                    "file": name,
                    "field": "text",
                    "added_constraints": missing,
                }
            )

    if prompt_locations == 0:
        raise NormalizationError("В artifact не найден image_prompt")

    # The old validation report hashes pre-normalized files and must never be
    # reused as an image source manifest. The validator immediately recreates it.
    stale_validation = artifact_dir / "artifact-validation.json"
    if stale_validation.resolve() != report_path.resolve() and stale_validation.exists():
        stale_validation.unlink()
        report["removed_stale_validation"] = True
    else:
        report["removed_stale_validation"] = False

    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report)
    return report


def _count_prompts(payload: Any) -> int:
    if isinstance(payload, dict):
        return sum(
            (1 if key == "image_prompt" and isinstance(value, str) else _count_prompts(value))
            for key, value in payload.items()
        )
    if isinstance(payload, list):
        return sum(_count_prompts(value) for value in payload)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = normalize_artifact(args.artifact_dir, args.report)
    except NormalizationError as exc:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            args.report,
            {
                "status": "error",
                "artifact_dir": str(args.artifact_dir),
                "error": str(exc),
            },
        )
        print(f"Digest normalization failed: {exc}")
        return 1
    print(
        "Digest normalization: ok; changed files: "
        + (", ".join(report["changed_files"]) or "none")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
