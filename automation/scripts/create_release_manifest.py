from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from release_common import (
    ROOT,
    assert_inside,
    current_iso,
    git_value,
    read_json,
    relative_to_root,
    resolve_from_root,
    sha256_file,
    tree_digest,
    write_json,
)

REPORT_NAMES = {
    "materialization": "materialization.json",
    "editorial_artifact": "editorial-artifact-validation.json",
    "cover_contract": "cover-validation.json",
    "site": "site-validation.json",
    "dzen_feed": "dzen-feed-validation.json",
    "build": "build-info.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создать release-manifest.json для artifact-only candidate.")
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--site-dir", required=True, type=Path)
    parser.add_argument("--reports-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def require_ok(report: Any, label: str) -> dict[str, Any]:
    if not isinstance(report, dict) or report.get("status") != "ok":
        raise RuntimeError(f"{label} должен иметь status=ok.")
    return report


def create_manifest(source_dir: Path, site_dir: Path, reports_dir: Path, output: Path) -> dict[str, Any]:
    for path, parent, label in (
        (source_dir, ROOT / "automation" / "preview", "source-dir"),
        (site_dir, ROOT / "automation" / "preview", "site-dir"),
        (reports_dir, ROOT / "automation" / "preview", "reports-dir"),
        (output, ROOT / "automation" / "preview", "output"),
    ):
        assert_inside(path, parent, label)

    digest = require_ok(read_json(source_dir / "digest.json"), "digest.json")
    release_source = require_ok(read_json(source_dir / "release-source.json"), "release-source.json")
    visual_review = read_json(source_dir / "visual-review.json")
    if not isinstance(visual_review, dict) or visual_review.get("status") != "accepted":
        raise RuntimeError("visual-review.json должен иметь status=accepted.")

    reports: dict[str, dict[str, Any]] = {}
    for key, filename in REPORT_NAMES.items():
        reports[key] = require_ok(read_json(reports_dir / filename), filename)

    if reports["build"].get("live_posts_sha256_before") != reports["build"].get("live_posts_sha256_after"):
        raise RuntimeError("build-info.json сообщает об изменении live posts/.")

    slug = str(digest["slug"])
    cover_filename = str(digest["cover_filename"])
    page_path = site_dir / slug / "index.html"
    published_cover = site_dir / "images" / cover_filename
    for path in (site_dir / "index.html", site_dir / "rss.xml", page_path, published_cover):
        if not path.is_file():
            raise RuntimeError(f"В release candidate отсутствует: {path}")

    source_cover_hash = sha256_file(source_dir / "cover.png")
    published_cover_hash = sha256_file(published_cover)
    if source_cover_hash != published_cover_hash:
        raise RuntimeError("Published cover отличается от принятого cover.png.")
    if source_cover_hash != str(release_source.get("cover_sha256")):
        raise RuntimeError("Cover SHA не совпадает с release source.")
    if visual_review.get("cover_sha256") != source_cover_hash:
        raise RuntimeError("Visual review относится к другой обложке.")

    validation_entries = {
        key: {
            "status": value["status"],
            "path": relative_to_root(reports_dir / REPORT_NAMES[key]),
            "sha256": sha256_file(reports_dir / REPORT_NAMES[key]),
        }
        for key, value in reports.items()
    }
    validation_entries["visual_review"] = {
        "status": "accepted",
        "path": relative_to_root(source_dir / "visual-review.json"),
        "sha256": sha256_file(source_dir / "visual-review.json"),
    }

    manifest = {
        "schema_version": 1,
        "status": "ok",
        "release_id": f"golden-{digest['date']}-{release_source['image_request_id']}",
        "release_kind": "golden_fixture",
        "production_eligible": False,
        "publication_date": digest["date"],
        "published_at": digest["published_at"],
        "title": digest["title"],
        "provenance": {
            "editorial_request_id": release_source["editorial_request_id"],
            "editorial_commit": release_source["editorial_commit"],
            "image_request_id": release_source["image_request_id"],
            "image_commit": release_source["image_commit"],
            "image_model": release_source["image_model"],
            "accepted_artifact_sha256": release_source["accepted_artifact_sha256"],
            "workflow_sha": git_value("GITHUB_SHA"),
            "workflow_ref": git_value("GITHUB_REF"),
        },
        "source": {
            "path": relative_to_root(source_dir),
            "tree_sha256": tree_digest(source_dir),
            "digest_sha256": sha256_file(source_dir / "digest.json"),
            "cover_sha256": source_cover_hash,
            "release_source_sha256": sha256_file(source_dir / "release-source.json"),
        },
        "candidate": {
            "path": relative_to_root(site_dir),
            "tree_sha256": tree_digest(site_dir),
            "index_sha256": sha256_file(site_dir / "index.html"),
            "rss_sha256": sha256_file(site_dir / "rss.xml"),
            "page_sha256": sha256_file(page_path),
            "cover_sha256": published_cover_hash,
            "page_path": relative_to_root(page_path),
            "cover_path": relative_to_root(published_cover),
        },
        "validations": validation_entries,
        "safety": {
            "live_posts_unchanged": True,
            "ftp_used": False,
            "openai_used": False,
            "network_used": False,
            "request_files_changed": False,
        },
        "created_at": current_iso(),
    }
    write_json(output, manifest)
    return manifest


def main() -> int:
    args = parse_args()
    try:
        manifest = create_manifest(
            resolve_from_root(args.source_dir),
            resolve_from_root(args.site_dir),
            resolve_from_root(args.reports_dir),
            resolve_from_root(args.output),
        )
        print(f"Release manifest created: {manifest['release_id']}")
        return 0
    except Exception as exc:
        print(f"Release manifest failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
