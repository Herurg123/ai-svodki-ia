from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orchestrator_common import apply_operations, copy_tree, describe_tree
from release_common import ROOT, assert_inside, current_iso, read_json, resolve_from_root, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Применить release и rollback только к временной копии.")
    parser.add_argument("--live-dir", required=True, type=Path)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--snapshot-dir", required=True, type=Path)
    parser.add_argument("--snapshot-manifest", required=True, type=Path)
    parser.add_argument("--publication-plan", required=True, type=Path)
    parser.add_argument("--rollback-plan", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def simulate(
    live_dir: Path,
    candidate_dir: Path,
    snapshot_dir: Path,
    snapshot_manifest: dict,
    publication_plan: dict,
    rollback_plan: dict,
    output_dir: Path,
    report_path: Path,
) -> dict:
    if live_dir.resolve() != (ROOT / "posts").resolve():
        raise RuntimeError("Симуляция ожидает корневой posts/ как read-only источник.")
    for path, label in (
        (candidate_dir, "candidate-dir"),
        (snapshot_dir, "snapshot-dir"),
        (output_dir, "output-dir"),
        (report_path, "report"),
    ):
        assert_inside(path, ROOT / "automation" / "preview", label)
    if publication_plan.get("status") != "blocked" or publication_plan.get("execution_allowed") is not False:
        raise RuntimeError("Dry-run ожидает заблокированный publication plan.")
    if rollback_plan.get("status") != "blocked" or rollback_plan.get("execution_allowed") is not False:
        raise RuntimeError("Dry-run ожидает заблокированный rollback plan.")

    live_before = describe_tree(live_dir)
    snapshot = describe_tree(snapshot_dir)
    candidate = describe_tree(candidate_dir)
    if snapshot_manifest.get("tree_sha256") != snapshot["tree_sha256"]:
        raise RuntimeError("Snapshot directory не совпадает со snapshot manifest.")
    if snapshot_manifest.get("files") != snapshot["files"]:
        raise RuntimeError("Файлы snapshot были изменены.")
    if snapshot["tree_sha256"] != live_before["tree_sha256"]:
        raise RuntimeError("Snapshot не соответствует текущему live posts/.")

    simulated_live = output_dir / "simulated-live"
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    copy_tree(live_dir, simulated_live)

    apply_operations(simulated_live, candidate_dir, publication_plan["operations"])
    promoted = describe_tree(simulated_live)
    if promoted["tree_sha256"] != candidate["tree_sha256"] or promoted["files"] != candidate["files"]:
        raise RuntimeError("Publication plan не воспроизвёл candidate tree.")

    apply_operations(simulated_live, snapshot_dir, rollback_plan["operations"])
    restored = describe_tree(simulated_live)
    if restored["tree_sha256"] != snapshot["tree_sha256"] or restored["files"] != snapshot["files"]:
        raise RuntimeError("Rollback plan не восстановил исходное дерево.")

    live_after = describe_tree(live_dir)
    live_unchanged = live_before["tree_sha256"] == live_after["tree_sha256"] and live_before["files"] == live_after["files"]
    if not live_unchanged:
        raise RuntimeError("Симуляция изменила настоящий posts/.")

    report = {
        "schema_version": 1,
        "status": "ok",
        "mode": "artifact_only_simulation",
        "created_at": current_iso(),
        "promotion": {
            "status": "ok",
            "expected_tree_sha256": candidate["tree_sha256"],
            "actual_tree_sha256": promoted["tree_sha256"],
            "operations_applied": len(publication_plan["operations"]),
        },
        "rollback": {
            "status": "ok",
            "expected_tree_sha256": snapshot["tree_sha256"],
            "actual_tree_sha256": restored["tree_sha256"],
            "operations_applied": len(rollback_plan["operations"]),
        },
        "safety": {
            "live_posts_unchanged": live_unchanged,
            "actual_release_applied": False,
            "actual_rollback_applied": False,
            "repository_write_used": False,
            "ftp_used": False,
            "external_network_used": False,
        },
    }
    write_json(report_path, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = simulate(
            resolve_from_root(args.live_dir),
            resolve_from_root(args.candidate_dir),
            resolve_from_root(args.snapshot_dir),
            read_json(resolve_from_root(args.snapshot_manifest)),
            read_json(resolve_from_root(args.publication_plan)),
            read_json(resolve_from_root(args.rollback_plan)),
            resolve_from_root(args.output_dir),
            resolve_from_root(args.report),
        )
        print(
            "Release and rollback simulation passed; "
            f"live unchanged={report['safety']['live_posts_unchanged']}"
        )
        return 0
    except Exception as exc:
        print(f"Release and rollback simulation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
