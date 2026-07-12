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
    validate_config,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверить единый artifact-only daily replay.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def validate(config_path: Path, manifest_path: Path, report_path: Path) -> dict[str, Any]:
    assert_inside(config_path, ROOT / "automation" / "config", "config")
    assert_inside(manifest_path, ROOT / "automation" / "preview" / "daily-orchestrator", "manifest")
    assert_inside(report_path, ROOT / "automation" / "preview" / "daily-orchestrator", "report")
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    config = read_json(config_path)
    manifest = read_json(manifest_path)
    if not isinstance(config, dict):
        raise RuntimeError("Config должен содержать объект.")
    if not isinstance(manifest, dict):
        raise RuntimeError("Manifest должен содержать объект.")
    try:
        validate_config(config)
    except RuntimeError as exc:
        errors.append({"code": "unsafe_config", "message": str(exc)})

    if manifest.get("status") != "ok":
        errors.append({"code": "manifest_status", "message": "Manifest должен иметь status=ok."})
    if manifest.get("mode") != "recorded_fixture_replay":
        errors.append({"code": "manifest_mode", "message": "Неверный replay mode."})
    if manifest.get("publication_date") != config.get("publication_date"):
        errors.append({"code": "publication_date", "message": "Дата manifest не совпадает с config."})

    run_dir = resolve_from_root(str(manifest.get("run_dir", "")))
    try:
        assert_inside(run_dir, resolve_from_root(config["output_root"]), "run_dir")
    except Exception as exc:
        errors.append({"code": "run_dir", "message": str(exc)})

    expected = config.get("expected") if isinstance(config.get("expected"), dict) else {}
    lineage = manifest.get("lineage") if isinstance(manifest.get("lineage"), dict) else {}
    if lineage.get("research_candidates") != expected.get("research_candidates"):
        errors.append({"code": "candidate_count", "message": "Research candidate count не совпадает."})
    if lineage.get("editorial_request_id") != expected.get("editorial_request_id"):
        errors.append({"code": "editorial_lineage", "message": "Editorial request_id не совпадает."})
    if lineage.get("image_request_id") != expected.get("image_request_id"):
        errors.append({"code": "image_lineage", "message": "Image request_id не совпадает."})
    if lineage.get("image_model") != expected.get("image_model"):
        errors.append({"code": "image_model", "message": "Image model не совпадает."})
    if lineage.get("cover_sha256") != expected.get("cover_sha256"):
        errors.append({"code": "cover_lineage", "message": "Cover SHA-256 не совпадает."})
    selected = lineage.get("selected_candidate_ids")
    if not isinstance(selected, list) or len(selected) != expected.get("selected_stories"):
        errors.append({"code": "selected_stories", "message": "Число выбранных сюжетов не совпадает."})

    replay = manifest.get("replay") if isinstance(manifest.get("replay"), dict) else {}
    for field in ("research_mocked", "editorial_mocked", "image_mocked"):
        if replay.get(field) is not True:
            errors.append({"code": "replay_stage", "message": f"{field} должен быть true."})
    for field in ("current_run_network_used", "current_run_openai_used"):
        if replay.get(field) is not False:
            errors.append({"code": "paid_api_usage", "message": f"{field} должен быть false."})
    if replay.get("current_run_paid_api_calls") != 0:
        errors.append({"code": "paid_api_usage", "message": "Текущий replay не должен вызывать API."})

    current = manifest.get("current_run") if isinstance(manifest.get("current_run"), dict) else {}
    false_fields = (
        "network_used",
        "openai_used",
        "ftp_used",
        "repository_write_used",
        "production_paths_changed",
    )
    for field in false_fields:
        if current.get(field) is not False:
            errors.append({"code": "unsafe_runtime", "message": f"current_run.{field} должен быть false."})
    for field in ("responses_api_calls", "image_api_calls", "web_search_calls"):
        if current.get(field) != 0:
            errors.append({"code": "paid_api_usage", "message": f"current_run.{field} должен быть 0."})

    release = manifest.get("release") if isinstance(manifest.get("release"), dict) else {}
    if release.get("release_kind") != "golden_fixture":
        errors.append({"code": "release_kind", "message": "Replay должен использовать golden_fixture."})
    if release.get("production_eligible") is not False:
        errors.append({"code": "production_eligible", "message": "Golden replay не может быть production eligible."})
    if release.get("production_gate_status") != "blocked":
        errors.append({"code": "production_gate", "message": "Production gate должен быть blocked."})
    if release.get("source_cover_sha256") != release.get("candidate_cover_sha256"):
        errors.append({"code": "cover_copy", "message": "Cover изменился при сборке сайта."})
    if release.get("source_cover_sha256") != expected.get("cover_sha256"):
        errors.append({"code": "cover_copy", "message": "Release cover не совпадает с принятым SHA-256."})

    reports = manifest.get("reports") if isinstance(manifest.get("reports"), dict) else {}
    if not reports:
        errors.append({"code": "reports", "message": "Manifest не содержит reports."})
    for name, entry in reports.items():
        if not isinstance(entry, dict):
            errors.append({"code": "report_entry", "message": f"Report {name} имеет неверный формат."})
            continue
        path = resolve_from_root(str(entry.get("path", "")))
        try:
            assert_inside(path, run_dir, f"report {name}")
        except Exception as exc:
            errors.append({"code": "report_path", "message": str(exc)})
            continue
        if not path.is_file():
            errors.append({"code": "report_missing", "message": f"Report не найден: {name}"})
        elif sha256_file(path) != entry.get("sha256"):
            errors.append({"code": "report_hash", "message": f"SHA-256 report не совпадает: {name}"})

    stage_hashes = manifest.get("stage_tree_sha256")
    expected_stage_dirs = {
        "research": run_dir / "research",
        "editorial": run_dir / "editorial",
        "image": run_dir / "image",
        "release_source": run_dir / "release/source",
        "release_site": run_dir / "release/site/posts",
    }
    if not isinstance(stage_hashes, dict):
        errors.append({"code": "stage_hashes", "message": "stage_tree_sha256 должен быть объектом."})
        stage_hashes = {}
    for name, path in expected_stage_dirs.items():
        if not path.is_dir():
            errors.append({"code": "stage_missing", "message": f"Stage directory отсутствует: {name}"})
        elif tree_digest(path) != stage_hashes.get(name):
            errors.append({"code": "stage_hash", "message": f"Stage SHA-256 не совпадает: {name}"})

    if replay.get("historical_sources_used_openai") is True:
        warnings.append(
            {
                "code": "historical_openai_provenance",
                "message": "Golden fixtures исторически созданы через OpenAI, но текущий replay не вызывает API.",
            }
        )

    report = {
        "schema_version": 1,
        "status": "ok" if not errors else "error",
        "manifest": relative_to_root(manifest_path),
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "lineage_valid": not any(error["code"].endswith("lineage") for error in errors),
            "paid_api_calls": current.get("responses_api_calls", -1) + current.get("image_api_calls", -1),
            "web_search_calls": current.get("web_search_calls"),
            "production_gate": release.get("production_gate_status"),
            "production_eligible": release.get("production_eligible"),
        },
        "created_at": current_iso(),
    }
    write_json(report_path, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = validate(
            resolve_from_root(args.config),
            resolve_from_root(args.manifest),
            resolve_from_root(args.report),
        )
        print(f"Daily orchestrator replay validation: {report['status']}")
        for error in report["errors"]:
            print(f"ERROR [{error['code']}]: {error['message']}", file=sys.stderr)
        return 0 if report["status"] == "ok" else 1
    except Exception as exc:
        print(f"Daily orchestrator validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
