from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from orchestrator_common import describe_tree, diff_manifests, operation_summary
from release_common import (
    ROOT,
    assert_inside,
    current_iso,
    read_json,
    relative_to_root,
    resolve_from_root,
    sha256_file,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создать заблокированный план production-синхронизации.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--release-manifest", required=True, type=Path)
    parser.add_argument("--gate-report", required=True, type=Path)
    parser.add_argument("--live-dir", required=True, type=Path)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-blocked", action="store_true")
    return parser.parse_args()


def create_plan(
    config: dict[str, Any],
    release_manifest: dict[str, Any],
    gate_report: dict[str, Any],
    live_dir: Path,
    candidate_dir: Path,
    output: Path,
) -> dict[str, Any]:
    live_root = ROOT / str(config.get("live_posts_directory", "posts"))
    preview_root = ROOT / str(
        config.get("preview_root", "automation/preview/production-orchestrator")
    )
    if live_dir.resolve() != live_root.resolve():
        raise RuntimeError(f"live-dir должен быть ровно {live_root.resolve()}.")
    assert_inside(candidate_dir, ROOT / "automation" / "preview", "candidate-dir")
    assert_inside(output, preview_root, "output")
    if not live_dir.is_dir() or not candidate_dir.is_dir():
        raise RuntimeError("Live и candidate каталоги должны существовать.")
    if release_manifest.get("status") != "ok":
        raise RuntimeError("Release manifest должен иметь status=ok.")
    if gate_report.get("status") not in {"blocked", "ready"}:
        raise RuntimeError("Production gate report имеет неизвестный status.")

    live = describe_tree(live_dir)
    candidate = describe_tree(candidate_dir)
    operations = diff_manifests(live["files"], candidate["files"])

    blockers: list[str] = []
    if config.get("publication_enabled") is not True:
        blockers.append("publication_enabled=false")
    if config.get("simulation_only") is True:
        blockers.append("simulation_only=true")
    if gate_report.get("status") != "ready":
        blockers.append("production gate is not ready")
    if release_manifest.get("production_eligible") is not True:
        blockers.append("release candidate is not production eligible")
    if (
        release_manifest.get("release_kind") == "golden_fixture"
        and config.get("allow_golden_fixture_publication") is not True
    ):
        blockers.append("golden fixture publication is forbidden")
    if config.get("allow_repository_write") is not True:
        blockers.append("repository write is disabled")
    if config.get("allow_ftp") is not True:
        blockers.append("FTP is disabled")

    execution_allowed = not blockers
    plan = {
        "schema_version": 1,
        "status": "ready" if execution_allowed else "blocked",
        "mode": "artifact_only_dry_run",
        "execution_allowed": execution_allowed,
        "created_at": current_iso(),
        "workflow_ref": os.environ.get("GITHUB_REF", "unknown"),
        "release": {
            "release_id": release_manifest.get("release_id"),
            "release_kind": release_manifest.get("release_kind"),
            "production_eligible": release_manifest.get("production_eligible"),
            "manifest_path": relative_to_root(resolve_from_root(output).parent / "release-manifest.json"),
            "manifest_sha256": sha256_file(resolve_from_root(output).parent / "release-manifest.json")
            if (resolve_from_root(output).parent / "release-manifest.json").is_file()
            else None,
        },
        "gate": {
            "status": gate_report.get("status"),
            "blockers": gate_report.get("blockers", []),
        },
        "live": {
            "path": relative_to_root(live_dir),
            "tree_sha256": live["tree_sha256"],
            "file_count": live["file_count"],
        },
        "candidate": {
            "path": relative_to_root(candidate_dir),
            "tree_sha256": candidate["tree_sha256"],
            "file_count": candidate["file_count"],
        },
        "operations": operations,
        "summary": operation_summary(operations),
        "blockers": blockers,
        "safety": {
            "live_posts_modified": False,
            "repository_write_used": False,
            "ftp_used": False,
            "external_network_used": False,
            "artifact_only": True,
        },
    }
    write_json(output, plan)
    return plan


def main() -> int:
    args = parse_args()
    try:
        output = resolve_from_root(args.output)
        plan = create_plan(
            read_json(resolve_from_root(args.config)),
            read_json(resolve_from_root(args.release_manifest)),
            read_json(resolve_from_root(args.gate_report)),
            resolve_from_root(args.live_dir),
            resolve_from_root(args.candidate_dir),
            output,
        )
        if args.expect_blocked and plan["status"] != "blocked":
            print("Publication plan unexpectedly became executable.", file=sys.stderr)
            return 1
        if not args.expect_blocked and plan["status"] != "ready":
            print("Publication plan is blocked:", file=sys.stderr)
            for blocker in plan["blockers"]:
                print(f"- {blocker}", file=sys.stderr)
            return 1
        print(f"Publication plan: {plan['status']}; operations={plan['summary']['total']}")
        return 0
    except Exception as exc:
        print(f"Publication plan failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
