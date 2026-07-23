from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from daily_orchestrator_common import (
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

REQUIRED_REPORTS = {
    "materialization": ("materialization.json", "ok"),
    "research_stage": ("research-stage.json", "ok"),
    "editorial_stage": ("editorial-stage.json", "ok"),
    "image_stage": ("image-stage.json", "ok"),
    "editorial_validation": ("editorial-validation.json", "ok"),
    "image_validation": ("image-validation.json", "ok"),
    "release_materialization": ("release/materialization.json", "ok"),
    "release_editorial_validation": ("release/editorial-artifact-validation.json", "ok"),
    "release_cover_validation": ("release/cover-validation.json", "ok"),
    "build": ("release/build-info.json", "ok"),
    "site_validation": ("release/site-validation.json", "ok"),
    "dzen_validation": ("release/dzen-feed-validation.json", "ok"),
    "release_manifest": ("release/release-manifest.json", "ok"),
    "release_validation": ("release/release-validation.json", "ok"),
    "production_gate": ("release/gate-report.json", "blocked"),
    "workflow_safety": ("workflow-safety.json", "ok"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Завершить единый artifact-only daily replay.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def finalize(run_dir: Path, output_path: Path) -> dict[str, Any]:
    assert_inside(run_dir, ROOT / "automation" / "preview" / "daily-orchestrator", "run-dir")
    assert_inside(output_path, run_dir, "output")
    reports: dict[str, Any] = {}
    for name, (relative, expected_status) in REQUIRED_REPORTS.items():
        path = run_dir / relative
        payload = read_json(path)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Report {name} должен содержать объект.")
        if payload.get("status") != expected_status:
            raise RuntimeError(
                f"Report {name} должен иметь status={expected_status}, "
                f"получено {payload.get('status')!r}."
            )
        reports[name] = {
            "path": relative_to_root(path),
            "sha256": sha256_file(path),
            "status": payload.get("status"),
        }

    research_stage = read_json(run_dir / "research-stage.json")
    editorial_stage = read_json(run_dir / "editorial-stage.json")
    image_stage = read_json(run_dir / "image-stage.json")
    release_manifest = read_json(run_dir / "release/release-manifest.json")
    gate = read_json(run_dir / "release/gate-report.json")
    if not all(isinstance(value, dict) for value in (research_stage, editorial_stage, image_stage, release_manifest, gate)):
        raise RuntimeError("Stage reports должны быть JSON-объектами.")

    publication_date = str(research_stage.get("publication_date"))
    if {
        publication_date,
        str(editorial_stage.get("publication_date")),
        str(image_stage.get("publication_date")),
        str(release_manifest.get("publication_date")),
    } != {publication_date}:
        raise RuntimeError("Publication date расходится между стадиями.")

    source = release_manifest.get("source") if isinstance(release_manifest.get("source"), dict) else {}
    candidate = (
        release_manifest.get("candidate")
        if isinstance(release_manifest.get("candidate"), dict)
        else {}
    )
    manifest = {
        "schema_version": 1,
        "status": "ok",
        "mode": "recorded_fixture_replay",
        "publication_date": publication_date,
        "run_dir": relative_to_root(run_dir),
        "lineage": {
            "research_candidates": research_stage.get("candidate_count"),
            "editorial_request_id": editorial_stage.get("source_request_id"),
            "selected_candidate_ids": editorial_stage.get("selected_candidate_ids"),
            "image_request_id": image_stage.get("source_request_id"),
            "image_model": image_stage.get("source_model"),
            "cover_sha256": image_stage.get("cover_sha256"),
            "release_id": release_manifest.get("release_id"),
        },
        "replay": {
            "research_mocked": research_stage.get("mock_response"),
            "editorial_mocked": editorial_stage.get("mock_response"),
            "image_mocked": image_stage.get("mock_response"),
            "historical_sources_used_openai": True,
            "current_run_network_used": False,
            "current_run_openai_used": False,
            "current_run_paid_api_calls": 0,
        },
        "release": {
            "release_kind": release_manifest.get("release_kind"),
            "production_eligible": release_manifest.get("production_eligible"),
            "source_tree_sha256": source.get("tree_sha256"),
            "candidate_tree_sha256": candidate.get("tree_sha256"),
            "source_cover_sha256": source.get("cover_sha256"),
            "candidate_cover_sha256": candidate.get("cover_sha256"),
            "production_gate_status": gate.get("status"),
        },
        "reports": reports,
        "current_run": {
            "network_used": False,
            "openai_used": False,
            "responses_api_calls": 0,
            "image_api_calls": 0,
            "web_search_calls": 0,
            "ftp_used": False,
            "repository_write_used": False,
            "production_paths_changed": False,
        },
        "stage_tree_sha256": {
            "research": tree_digest(run_dir / "research"),
            "editorial": tree_digest(run_dir / "editorial"),
            "image": tree_digest(run_dir / "image"),
            "release_source": tree_digest(run_dir / "release/source"),
            "release_site": tree_digest(run_dir / "release/site/posts"),
        },
        "created_at": current_iso(),
    }
    write_json(output_path, manifest)
    return manifest


def main() -> int:
    args = parse_args()
    try:
        manifest = finalize(
            resolve_from_root(args.run_dir),
            resolve_from_root(args.output),
        )
        print("Daily orchestrator replay finalized")
        print(f"Publication date: {manifest['publication_date']}")
        return 0
    except Exception as exc:
        print(f"Daily orchestrator finalization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
