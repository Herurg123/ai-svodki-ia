from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from orchestrator_common import (
    assert_inside_allowed_preview_roots,
    describe_tree,
    diff_manifests,
    operation_summary,
    validate_manifest,
)
from release_common import ROOT, assert_inside, current_iso, read_json, relative_to_root, resolve_from_root, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создать заблокированный план rollback.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--snapshot-manifest", required=True, type=Path)
    parser.add_argument("--post-release-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-blocked", action="store_true")
    return parser.parse_args()


def create_plan(
    config: dict[str, Any],
    snapshot_manifest: dict[str, Any],
    post_release_dir: Path,
    output: Path,
) -> dict[str, Any]:
    preview_root = ROOT / str(
        config.get("preview_root", "automation/preview/production-orchestrator")
    )
    assert_inside(post_release_dir, ROOT / "automation" / "preview", "post-release-dir")
    assert_inside_allowed_preview_roots(output, config, ROOT, "output")
    if snapshot_manifest.get("status") != "ok":
        raise RuntimeError("Snapshot manifest должен иметь status=ok.")
    snapshot_files = snapshot_manifest.get("files")
    validate_manifest(snapshot_files)
    post_release = describe_tree(post_release_dir)
    operations = diff_manifests(post_release["files"], snapshot_files)

    blockers: list[str] = []
    if config.get("rollback_execution_enabled") is not True:
        blockers.append("rollback execution is disabled")
    if config.get("simulation_only") is True:
        blockers.append("simulation_only=true")
    if config.get("allow_repository_write") is not True:
        blockers.append("repository write is disabled")
    if config.get("allow_ftp") is not True:
        blockers.append("FTP is disabled")

    execution_allowed = not blockers
    plan = {
        "schema_version": 1,
        "status": "ready" if execution_allowed else "blocked",
        "mode": "artifact_only_rollback_drill",
        "execution_allowed": execution_allowed,
        "created_at": current_iso(),
        "post_release": {
            "path": relative_to_root(post_release_dir),
            "tree_sha256": post_release["tree_sha256"],
            "file_count": post_release["file_count"],
        },
        "restore_target": {
            "tree_sha256": snapshot_manifest["tree_sha256"],
            "file_count": snapshot_manifest["file_count"],
            "snapshot_path": snapshot_manifest["snapshot_path"],
        },
        "operations": operations,
        "summary": operation_summary(operations),
        "blockers": blockers,
        "safety": {
            "actual_live_posts_modified": False,
            "repository_write_used": False,
            "ftp_used": False,
            "artifact_only": True,
        },
    }
    write_json(output, plan)
    return plan


def main() -> int:
    args = parse_args()
    try:
        plan = create_plan(
            read_json(resolve_from_root(args.config)),
            read_json(resolve_from_root(args.snapshot_manifest)),
            resolve_from_root(args.post_release_dir),
            resolve_from_root(args.output),
        )
        if args.expect_blocked and plan["status"] != "blocked":
            print("Rollback plan unexpectedly became executable.", file=sys.stderr)
            return 1
        if not args.expect_blocked and plan["status"] != "ready":
            print("Rollback plan is blocked.", file=sys.stderr)
            return 1
        print(f"Rollback plan: {plan['status']}; operations={plan['summary']['total']}")
        return 0
    except Exception as exc:
        print(f"Rollback plan failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
