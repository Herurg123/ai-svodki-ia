from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from daily_orchestrator_common import (
    ROOT,
    assert_inside,
    compare_manifest,
    current_iso,
    file_manifest,
    read_json,
    relative_to_root,
    resolve_from_root,
    sha256_file,
    tree_digest,
    validate_config,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Материализовать единый daily replay без сети и платных API."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def materialize(config_path: Path, output_dir: Path, report_path: Path) -> dict[str, Any]:
    assert_inside(config_path, ROOT / "automation" / "config", "config")
    assert_inside(output_dir, ROOT / "automation" / "preview", "output-dir")
    assert_inside(report_path, ROOT / "automation" / "preview", "report")

    config = read_json(config_path)
    if not isinstance(config, dict):
        raise RuntimeError("daily orchestrator config должен содержать объект.")
    validate_config(config)

    configured_root = resolve_from_root(config["output_root"])
    assert_inside(output_dir, configured_root, "output-dir")

    replay_source_path = resolve_from_root(config["replay_source"])
    replay_source = read_json(replay_source_path)
    if not isinstance(replay_source, dict) or replay_source.get("status") != "ok":
        raise RuntimeError("replay-source.json должен иметь status=ok.")
    if replay_source.get("mode") != "recorded_fixture_replay":
        raise RuntimeError("replay source имеет неверный mode.")
    if replay_source.get("production_eligible") is not False:
        raise RuntimeError("Replay source обязан иметь production_eligible=false.")

    research_path = resolve_from_root(config["research_fixture"])
    editorial_path = resolve_from_root(config["editorial_fixture"])
    release_path = resolve_from_root(config["release_fixture"])
    if not research_path.is_file():
        raise RuntimeError(f"Research fixture не найден: {research_path}")
    if not editorial_path.is_dir():
        raise RuntimeError(f"Editorial fixture не найден: {editorial_path}")
    if not release_path.is_dir():
        raise RuntimeError(f"Release fixture не найден: {release_path}")

    sources = replay_source.get("sources")
    if not isinstance(sources, dict):
        raise RuntimeError("replay source не содержит sources.")
    research_source = sources.get("research") if isinstance(sources.get("research"), dict) else {}
    editorial_source = sources.get("editorial") if isinstance(sources.get("editorial"), dict) else {}
    release_source = sources.get("release") if isinstance(sources.get("release"), dict) else {}

    if relative_to_root(research_path) != research_source.get("path"):
        raise RuntimeError("Research path не совпадает с replay source.")
    if sha256_file(research_path) != research_source.get("sha256"):
        raise RuntimeError("Research fixture SHA-256 не совпадает.")
    if relative_to_root(editorial_path) != editorial_source.get("path"):
        raise RuntimeError("Editorial path не совпадает с replay source.")
    compare_manifest(file_manifest(editorial_path), editorial_source.get("files", {}), "editorial")
    if tree_digest(editorial_path) != editorial_source.get("tree_sha256"):
        raise RuntimeError("Editorial fixture tree SHA-256 не совпадает.")
    if relative_to_root(release_path) != release_source.get("path"):
        raise RuntimeError("Release path не совпадает с replay source.")
    compare_manifest(file_manifest(release_path), release_source.get("files", {}), "release")
    if tree_digest(release_path) != release_source.get("tree_sha256"):
        raise RuntimeError("Release fixture tree SHA-256 не совпадает.")

    research = read_json(research_path)
    digest = read_json(editorial_path / "digest.json")
    run_info = read_json(editorial_path / "run-info.json")
    selection = read_json(editorial_path / "selection.json")
    source_release = read_json(release_path / "release-source.json")
    image_manifest = read_json(release_path / "image-manifest.json")
    visual_review = read_json(release_path / "visual-review.json")
    for value, label in (
        (research, "research"),
        (digest, "digest"),
        (run_info, "run-info"),
        (selection, "selection"),
        (source_release, "release-source"),
        (image_manifest, "image-manifest"),
        (visual_review, "visual-review"),
    ):
        if not isinstance(value, dict):
            raise RuntimeError(f"{label} должен содержать JSON-объект.")

    publication_date = str(config["publication_date"])
    dates = {
        str(research.get("publication_date")),
        str(digest.get("date")),
        str(run_info.get("publication_date")),
        str(source_release.get("publication_date")),
    }
    if dates != {publication_date}:
        raise RuntimeError(f"Даты replay-источников расходятся: {sorted(dates)}")

    expected = config["expected"]
    candidates = research.get("candidates") if isinstance(research.get("candidates"), list) else []
    selected = (
        selection.get("selected_candidate_ids")
        if isinstance(selection.get("selected_candidate_ids"), list)
        else []
    )
    if len(candidates) != expected["research_candidates"]:
        raise RuntimeError("Число research candidates не совпадает с config.expected.")
    if len(selected) != expected["selected_stories"]:
        raise RuntimeError("Число выбранных сюжетов не совпадает с config.expected.")
    if run_info.get("request_id") != expected["editorial_request_id"]:
        raise RuntimeError("Editorial request_id не совпадает.")
    if source_release.get("image_request_id") != expected["image_request_id"]:
        raise RuntimeError("Image request_id не совпадает.")
    if source_release.get("image_model") != expected["image_model"]:
        raise RuntimeError("Image model не совпадает.")
    if source_release.get("cover_sha256") != expected["cover_sha256"]:
        raise RuntimeError("Принятый cover SHA-256 не совпадает.")

    research_response = (
        run_info.get("research", {}).get("response", {})
        if isinstance(run_info.get("research"), dict)
        else {}
    )
    if research_response.get("web_search_calls") != 0:
        raise RuntimeError("Recorded editorial source должен иметь web_search_calls=0.")
    if research_response.get("response_status") != "reused":
        raise RuntimeError("Recorded editorial source должен переиспользовать research.")
    if visual_review.get("status") != "accepted":
        raise RuntimeError("Image fixture не прошёл ручную визуальную проверку.")

    temporary = output_dir.parent / f".{output_dir.name}.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)

    research_dir = temporary / "research"
    editorial_dir = temporary / "editorial"
    image_dir = temporary / "image"
    research_dir.mkdir()
    shutil.copy2(research_path, research_dir / "candidates.json")
    copy_tree(editorial_path, editorial_dir)
    image_dir.mkdir()
    image_files = source_release.get("image_files")
    if not isinstance(image_files, dict) or not image_files:
        raise RuntimeError("release-source не содержит image_files.")
    for filename in image_files:
        path = release_path / str(filename)
        if not path.is_file() or Path(str(filename)).name != str(filename):
            raise RuntimeError(f"Некорректный image fixture: {filename}")
        shutil.copy2(path, image_dir / str(filename))
    for filename in ("digest.json", "image-prompt.txt", "image-source.json"):
        shutil.copy2(editorial_path / filename, image_dir / filename)
    shutil.copy2(release_path / "release-source.json", image_dir / "release-source.json")

    geography = [str(item.get("geography")) for item in candidates if isinstance(item, dict)]
    write_json(
        temporary / "research-stage.json",
        {
            "schema_version": 1,
            "status": "ok",
            "mode": "recorded_fixture_replay",
            "publication_date": publication_date,
            "source": relative_to_root(research_path),
            "source_sha256": sha256_file(research_path),
            "candidate_count": len(candidates),
            "world_candidates": geography.count("world"),
            "russian_candidates": geography.count("russia"),
            "mock_response": True,
            "current_run": {"network_used": False, "openai_used": False, "web_search_calls": 0},
            "created_at": current_iso(),
        },
    )
    total_usage = run_info.get("total_usage") if isinstance(run_info.get("total_usage"), dict) else {}
    write_json(
        temporary / "editorial-stage.json",
        {
            "schema_version": 1,
            "status": "ok",
            "mode": "recorded_fixture_replay",
            "publication_date": publication_date,
            "source": relative_to_root(editorial_path),
            "source_tree_sha256": tree_digest(editorial_path),
            "source_request_id": run_info.get("request_id"),
            "source_pipeline": run_info.get("pipeline"),
            "selected_story_count": len(selected),
            "selected_candidate_ids": selected,
            "source_usage": total_usage,
            "source_was_generated_with_openai": True,
            "research_reused": True,
            "mock_response": True,
            "current_run": {"network_used": False, "openai_used": False, "responses_api_calls": 0},
            "created_at": current_iso(),
        },
    )
    write_json(
        temporary / "image-stage.json",
        {
            "schema_version": 1,
            "status": "ok",
            "mode": "recorded_fixture_replay",
            "publication_date": publication_date,
            "source": relative_to_root(release_path),
            "source_request_id": source_release.get("image_request_id"),
            "source_model": source_release.get("image_model"),
            "cover_sha256": sha256_file(image_dir / "cover.png"),
            "width": image_manifest.get("width"),
            "height": image_manifest.get("height"),
            "visual_review": visual_review.get("status"),
            "source_was_generated_with_openai": True,
            "mock_response": True,
            "current_run": {"network_used": False, "openai_used": False, "image_api_calls": 0},
            "created_at": current_iso(),
        },
    )
    write_json(
        temporary / "inputs-manifest.json",
        {
            "schema_version": 1,
            "status": "ok",
            "replay_source": relative_to_root(replay_source_path),
            "replay_source_sha256": sha256_file(replay_source_path),
            "research": {"path": relative_to_root(research_path), "sha256": sha256_file(research_path)},
            "editorial": {
                "path": relative_to_root(editorial_path),
                "tree_sha256": tree_digest(editorial_path),
                "files": file_manifest(editorial_path),
            },
            "release": {
                "path": relative_to_root(release_path),
                "tree_sha256": tree_digest(release_path),
                "files": file_manifest(release_path),
            },
            "created_at": current_iso(),
        },
    )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    temporary.replace(output_dir)

    report = {
        "schema_version": 1,
        "status": "ok",
        "mode": "recorded_fixture_replay",
        "publication_date": publication_date,
        "output_dir": relative_to_root(output_dir),
        "output_tree_sha256": tree_digest(output_dir),
        "current_run": {
            "network_used": False,
            "openai_used": False,
            "paid_api_calls": 0,
            "ftp_used": False,
            "production_paths_changed": False,
        },
        "created_at": current_iso(),
    }
    write_json(report_path, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = materialize(
            resolve_from_root(args.config),
            resolve_from_root(args.output_dir),
            resolve_from_root(args.report),
        )
        print("Daily orchestrator replay materialized")
        print(f"Tree SHA-256: {report['output_tree_sha256']}")
        return 0
    except Exception as exc:
        print(f"Daily orchestrator replay failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
