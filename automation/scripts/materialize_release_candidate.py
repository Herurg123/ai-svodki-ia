from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from release_common import (
    ROOT,
    assert_inside,
    current_iso,
    file_manifest,
    read_json,
    relative_to_root,
    resolve_from_root,
    sha256_file,
    tree_digest,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Материализовать golden release fixture только в automation/preview/."
    )
    parser.add_argument("--release-fixture", required=True, type=Path)
    parser.add_argument("--editorial-source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def verify_hashes(root: Path, expected: dict[str, Any], label: str) -> None:
    actual = file_manifest(root)
    expected_normalized = {str(key): str(value) for key, value in expected.items()}
    if actual != expected_normalized:
        missing = sorted(set(expected_normalized) - set(actual))
        extra = sorted(set(actual) - set(expected_normalized))
        changed = sorted(
            key
            for key in set(actual).intersection(expected_normalized)
            if actual[key] != expected_normalized[key]
        )
        raise RuntimeError(
            f"{label}: хеши не совпадают; missing={missing}, extra={extra}, changed={changed}"
        )


def materialize(
    release_fixture: Path,
    editorial_source: Path,
    output_dir: Path,
    report_path: Path,
) -> dict[str, Any]:
    assert_inside(release_fixture, ROOT / "automation" / "fixtures" / "release", "release-fixture")
    assert_inside(editorial_source, ROOT / "automation" / "fixtures" / "editorial", "editorial-source")
    assert_inside(output_dir, ROOT / "automation" / "preview", "output-dir")
    assert_inside(report_path, ROOT / "automation" / "preview", "report")

    source_manifest_path = release_fixture / "release-source.json"
    source_manifest = read_json(source_manifest_path)
    if not isinstance(source_manifest, dict):
        raise RuntimeError("release-source.json должен содержать JSON-объект.")
    if source_manifest.get("status") != "ok":
        raise RuntimeError("release source должен иметь status=ok.")
    if source_manifest.get("role") != "golden_test_fixture":
        raise RuntimeError("Эта материализация разрешена только для golden_test_fixture.")
    if source_manifest.get("production_eligible") is not False:
        raise RuntimeError("Golden fixture обязан иметь production_eligible=false.")
    if source_manifest.get("editorial_source") != relative_to_root(editorial_source):
        raise RuntimeError("editorial_source не совпадает с release-source.json.")

    verify_hashes(editorial_source, source_manifest.get("editorial_files", {}), "editorial source")

    image_expected = source_manifest.get("image_files")
    if not isinstance(image_expected, dict) or not image_expected:
        raise RuntimeError("release-source.json не содержит image_files.")
    image_actual: dict[str, str] = {}
    for name, expected_hash in image_expected.items():
        filename = str(name)
        if Path(filename).name != filename:
            raise RuntimeError(f"Недопустимое имя image fixture: {filename}")
        path = release_fixture / filename
        if not path.is_file():
            raise RuntimeError(f"Не найден image fixture: {path}")
        actual_hash = sha256_file(path)
        image_actual[filename] = actual_hash
        if actual_hash != str(expected_hash):
            raise RuntimeError(f"Хеш image fixture не совпадает: {filename}")

    temporary = output_dir.parent / f".{output_dir.name}.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(editorial_source, temporary)
    for filename in image_expected:
        shutil.copy2(release_fixture / filename, temporary / filename)
    shutil.copy2(source_manifest_path, temporary / "release-source.json")

    digest = read_json(temporary / "digest.json")
    if not isinstance(digest, dict):
        raise RuntimeError("digest.json должен содержать объект.")
    if str(digest.get("date")) != str(source_manifest.get("publication_date")):
        raise RuntimeError("Дата digest не совпадает с release source.")
    cover_filename = str(digest.get("cover_filename", ""))
    cover_path = temporary / "cover.png"
    if sha256_file(cover_path) != str(source_manifest.get("cover_sha256")):
        raise RuntimeError("cover.png не совпадает с принятым SHA-256.")
    if cover_filename != "ai-svodka-2026-07-11.png":
        raise RuntimeError("Golden fixture содержит неожиданное имя production-обложки.")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    temporary.replace(output_dir)

    report = {
        "schema_version": 1,
        "status": "ok",
        "mode": "golden_fixture_materialization",
        "production_eligible": False,
        "publication_date": source_manifest["publication_date"],
        "release_fixture": relative_to_root(release_fixture),
        "editorial_source": relative_to_root(editorial_source),
        "output_dir": relative_to_root(output_dir),
        "editorial_files": len(source_manifest["editorial_files"]),
        "image_files": len(image_actual),
        "source_tree_sha256": tree_digest(output_dir),
        "cover_sha256": sha256_file(output_dir / "cover.png"),
        "created_at": current_iso(),
    }
    write_json(report_path, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = materialize(
            resolve_from_root(args.release_fixture),
            resolve_from_root(args.editorial_source),
            resolve_from_root(args.output_dir),
            resolve_from_root(args.report),
        )
        print("Release candidate source materialized")
        print(f"Source SHA-256: {report['source_tree_sha256']}")
        return 0
    except Exception as exc:
        print(f"Release materialization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
