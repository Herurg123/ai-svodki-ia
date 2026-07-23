from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from release_common import (
    ROOT,
    assert_inside,
    current_iso,
    read_json,
    relative_to_root,
    resolve_from_root,
    sha256_file,
    tree_digest,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверить artifact-only release candidate.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def validate(manifest_path: Path, report_path: Path) -> dict[str, Any]:
    assert_inside(manifest_path, ROOT / "automation" / "preview", "manifest")
    assert_inside(report_path, ROOT / "automation" / "preview", "report")
    errors: list[str] = []
    warnings: list[str] = []
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise RuntimeError("release manifest должен содержать объект.")

    if manifest.get("status") != "ok":
        errors.append("release manifest должен иметь status=ok.")
    if manifest.get("release_kind") != "golden_fixture":
        errors.append("Stage 6 ожидает release_kind=golden_fixture.")
    if manifest.get("production_eligible") is not False:
        errors.append("Golden fixture обязан иметь production_eligible=false.")
    else:
        warnings.append("Golden fixture намеренно непригоден для production.")

    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    candidate = manifest.get("candidate") if isinstance(manifest.get("candidate"), dict) else {}
    source_path = resolve_from_root(str(source.get("path", "")))
    candidate_path = resolve_from_root(str(candidate.get("path", "")))
    for path, label in ((source_path, "source"), (candidate_path, "candidate")):
        assert_inside(path, ROOT / "automation" / "preview", label)
        if not path.is_dir():
            errors.append(f"{label} directory отсутствует: {path}")

    if source_path.is_dir() and tree_digest(source_path) != source.get("tree_sha256"):
        errors.append("Source tree SHA-256 не совпадает.")
    if candidate_path.is_dir() and tree_digest(candidate_path) != candidate.get("tree_sha256"):
        errors.append("Candidate tree SHA-256 не совпадает.")

    for section_name, section, fields in (
        ("source", source, ("digest_sha256", "cover_sha256", "release_source_sha256")),
        ("candidate", candidate, ("index_sha256", "rss_sha256", "page_sha256", "cover_sha256")),
    ):
        for field in fields:
            value = section.get(field)
            if not isinstance(value, str) or len(value) != 64:
                errors.append(f"{section_name}.{field} должен быть SHA-256.")

    if source.get("cover_sha256") != candidate.get("cover_sha256"):
        errors.append("Source и published cover имеют разные SHA-256.")

    validations = manifest.get("validations")
    required = {
        "materialization": "ok",
        "editorial_artifact": "ok",
        "cover_contract": "ok",
        "site": "ok",
        "dzen_feed": "ok",
        "build": "ok",
        "visual_review": "accepted",
    }
    if not isinstance(validations, dict):
        errors.append("validations должен быть объектом.")
        validations = {}
    for name, expected_status in required.items():
        entry = validations.get(name)
        if not isinstance(entry, dict) or entry.get("status") != expected_status:
            errors.append(f"Validation {name} должен иметь status={expected_status}.")
            continue
        path = resolve_from_root(str(entry.get("path", "")))
        if not path.is_file():
            errors.append(f"Validation file отсутствует: {name}")
        elif sha256_file(path) != entry.get("sha256"):
            errors.append(f"Validation SHA-256 не совпадает: {name}")

    safety = manifest.get("safety") if isinstance(manifest.get("safety"), dict) else {}
    expected_safety = {
        "live_posts_unchanged": True,
        "ftp_used": False,
        "openai_used": False,
        "network_used": False,
        "request_files_changed": False,
    }
    for key, expected in expected_safety.items():
        if safety.get(key) is not expected:
            errors.append(f"safety.{key} должен быть {expected!r}.")

    for root in (source_path, candidate_path):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_symlink():
                errors.append(f"Символическая ссылка запрещена: {relative_to_root(path)}")
            if "automation/requests" in path.as_posix():
                errors.append(f"Release candidate содержит request path: {path}")

    report = {
        "schema_version": 1,
        "status": "ok" if not errors else "error",
        "checked_at": current_iso(),
        "manifest": relative_to_root(manifest_path),
        "release_id": manifest.get("release_id"),
        "release_kind": manifest.get("release_kind"),
        "production_eligible": manifest.get("production_eligible"),
        "errors": errors,
        "warnings": warnings,
    }
    write_json(report_path, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = validate(resolve_from_root(args.manifest), resolve_from_root(args.report))
        if report["errors"]:
            print("Release candidate validation failed:", file=sys.stderr)
            for error in report["errors"]:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("Release candidate validation passed")
        return 0
    except Exception as exc:
        print(f"Release candidate validation failed unexpectedly: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
