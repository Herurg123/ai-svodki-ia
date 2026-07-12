from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from orchestrator_common import describe_tree, diff_manifests, operation_summary, validate_relative_path
from release_common import ROOT, assert_inside, current_iso, read_json, resolve_from_root, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверить production orchestrator dry-run и rollback drill.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--live-dir", required=True, type=Path)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--release-manifest", required=True, type=Path)
    parser.add_argument("--gate-report", required=True, type=Path)
    parser.add_argument("--publication-plan", required=True, type=Path)
    parser.add_argument("--snapshot-manifest", required=True, type=Path)
    parser.add_argument("--rollback-plan", required=True, type=Path)
    parser.add_argument("--drill-report", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def add_error(errors: list[dict[str, str]], code: str, message: str) -> None:
    errors.append({"code": code, "message": message})


def validate(
    config: dict[str, Any],
    live_dir: Path,
    candidate_dir: Path,
    release_manifest: dict[str, Any],
    gate_report: dict[str, Any],
    publication_plan: dict[str, Any],
    snapshot_manifest: dict[str, Any],
    rollback_plan: dict[str, Any],
    drill_report: dict[str, Any],
    report_path: Path,
) -> dict[str, Any]:
    assert_inside(candidate_dir, ROOT / "automation" / "preview", "candidate-dir")
    assert_inside(report_path, ROOT / "automation" / "preview", "report")
    errors: list[dict[str, str]] = []

    if config.get("publication_enabled") is not False:
        add_error(errors, "publication_enabled", "publication_enabled должен оставаться false.")
    if config.get("rollback_execution_enabled") is not False:
        add_error(errors, "rollback_enabled", "rollback_execution_enabled должен оставаться false.")
    for key in ("allow_repository_write", "allow_ftp", "allow_external_network", "allow_schedule"):
        if config.get(key) is not False:
            add_error(errors, "unsafe_config", f"{key} должен оставаться false.")
    if release_manifest.get("release_kind") != "golden_fixture" or release_manifest.get("production_eligible") is not False:
        add_error(errors, "release_kind", "Dry-run должен использовать непубликуемый golden fixture.")
    if gate_report.get("status") != "blocked":
        add_error(errors, "gate_status", "Production gate должен оставаться blocked.")
    if publication_plan.get("status") != "blocked" or publication_plan.get("execution_allowed") is not False:
        add_error(errors, "publication_plan", "Publication plan должен быть заблокирован.")
    if rollback_plan.get("status") != "blocked" or rollback_plan.get("execution_allowed") is not False:
        add_error(errors, "rollback_plan", "Rollback plan должен быть заблокирован.")
    if drill_report.get("status") != "ok":
        add_error(errors, "drill_status", "Rollback drill должен иметь status=ok.")

    live = describe_tree(live_dir)
    candidate = describe_tree(candidate_dir)
    expected_publication = diff_manifests(live["files"], candidate["files"])
    if publication_plan.get("operations") != expected_publication:
        add_error(errors, "publication_operations", "Publication operations не совпадают с реальным diff.")
    if publication_plan.get("summary") != operation_summary(expected_publication):
        add_error(errors, "publication_summary", "Publication summary не совпадает с operations.")

    snapshot_files = snapshot_manifest.get("files") if isinstance(snapshot_manifest.get("files"), dict) else {}
    expected_rollback = diff_manifests(candidate["files"], snapshot_files)
    if rollback_plan.get("operations") != expected_rollback:
        add_error(errors, "rollback_operations", "Rollback operations не совпадают с реальным diff.")
    if rollback_plan.get("summary") != operation_summary(expected_rollback):
        add_error(errors, "rollback_summary", "Rollback summary не совпадает с operations.")

    for plan_name, plan in (("publication", publication_plan), ("rollback", rollback_plan)):
        seen: set[str] = set()
        for operation in plan.get("operations", []):
            try:
                relative = str(operation.get("path", ""))
                validate_relative_path(relative)
                if relative in seen:
                    raise RuntimeError("duplicate path")
                seen.add(relative)
            except Exception as exc:
                add_error(errors, "unsafe_operation", f"{plan_name}: {exc}")

    safety = drill_report.get("safety") if isinstance(drill_report.get("safety"), dict) else {}
    expected_safety = {
        "live_posts_unchanged": True,
        "actual_release_applied": False,
        "actual_rollback_applied": False,
        "repository_write_used": False,
        "ftp_used": False,
        "external_network_used": False,
    }
    for key, expected in expected_safety.items():
        if safety.get(key) is not expected:
            add_error(errors, "drill_safety", f"drill safety {key} должен быть {expected}.")

    report = {
        "schema_version": 1,
        "status": "ok" if not errors else "error",
        "checked_at": current_iso(),
        "errors": errors,
        "summary": {
            "publication_operations": len(expected_publication),
            "rollback_operations": len(expected_rollback),
            "live_tree_sha256": live["tree_sha256"],
            "candidate_tree_sha256": candidate["tree_sha256"],
            "gate_status": gate_report.get("status"),
            "publication_plan_status": publication_plan.get("status"),
            "rollback_plan_status": rollback_plan.get("status"),
            "drill_status": drill_report.get("status"),
        },
    }
    write_json(report_path, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = validate(
            read_json(resolve_from_root(args.config)),
            resolve_from_root(args.live_dir),
            resolve_from_root(args.candidate_dir),
            read_json(resolve_from_root(args.release_manifest)),
            read_json(resolve_from_root(args.gate_report)),
            read_json(resolve_from_root(args.publication_plan)),
            read_json(resolve_from_root(args.snapshot_manifest)),
            read_json(resolve_from_root(args.rollback_plan)),
            read_json(resolve_from_root(args.drill_report)),
            resolve_from_root(args.report),
        )
        if report["status"] != "ok":
            for error in report["errors"]:
                print(f"{error['code']}: {error['message']}", file=sys.stderr)
            return 1
        print("Production orchestrator dry-run contract: ok")
        return 0
    except Exception as exc:
        print(f"Orchestrator validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
