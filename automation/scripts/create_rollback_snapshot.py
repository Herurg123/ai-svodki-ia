from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orchestrator_common import copy_tree, describe_tree
from release_common import ROOT, assert_inside, current_iso, relative_to_root, resolve_from_root, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создать artifact-only снимок текущего posts/.")
    parser.add_argument("--live-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args()


def create_snapshot(live_dir: Path, output_dir: Path, manifest_path: Path) -> dict:
    if live_dir.resolve() != (ROOT / "posts").resolve():
        raise RuntimeError("Rollback snapshot разрешён только для корневого posts/.")
    assert_inside(output_dir, ROOT / "automation" / "preview", "output-dir")
    assert_inside(manifest_path, ROOT / "automation" / "preview", "manifest")
    snapshot_posts = output_dir / "posts"
    copy_tree(live_dir, snapshot_posts)
    live = describe_tree(live_dir)
    snapshot = describe_tree(snapshot_posts)
    if live["tree_sha256"] != snapshot["tree_sha256"] or live["files"] != snapshot["files"]:
        raise RuntimeError("Снимок posts/ не совпал с исходным деревом.")
    manifest = {
        "schema_version": 1,
        "status": "ok",
        "snapshot_kind": "pre_release_artifact",
        "created_at": current_iso(),
        "source_path": relative_to_root(live_dir),
        "snapshot_path": relative_to_root(snapshot_posts),
        "tree_sha256": snapshot["tree_sha256"],
        "file_count": snapshot["file_count"],
        "files": snapshot["files"],
        "restorable": True,
        "actual_production_changed": False,
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    args = parse_args()
    try:
        manifest = create_snapshot(
            resolve_from_root(args.live_dir),
            resolve_from_root(args.output_dir),
            resolve_from_root(args.manifest),
        )
        print(f"Rollback snapshot created: {manifest['file_count']} files")
        return 0
    except Exception as exc:
        print(f"Rollback snapshot failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
