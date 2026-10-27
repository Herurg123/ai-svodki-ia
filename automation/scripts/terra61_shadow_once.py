#!/usr/bin/env python3
"""One-day, no-publication Terra 6.1 comparison boundary (remove after 2026-10-28).

The production run writes a pre-paid frozen manifest. A separate, non-deploying
job checks out that exact source revision and consumes only public metadata from
the saved Terra 5.6 artifact to freeze identical temporal boundaries. It never
imports Terra 5.6 candidates into the new model's context.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAY = "2026-10-28"
BASELINE_NAME = "terra-compare-baseline-2026-10-28.json"
PRIMARY_NAME = f"primary-recall-{DAY}.json"
PROD_MODEL = "gpt-5.6-terra"
SHADOW_MODEL = "gpt-6.1-terra"
INPUT_PATHS = (
    "automation/archive/index.json",
    "automation/config/site.json",
    "automation/config/editorial.json",
    "automation/config/production-daily.json",
    "automation/prompts/primary_recall_pass.md",
    "automation/prompts/research_candidates.md",
    "automation/prompts/daily_digest.md",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected object in {path.name}")
    return value


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def one_under(directory: Path, name: str) -> Path:
    found = list(directory.rglob(name))
    if len(found) != 1:
        raise RuntimeError(f"Expected exactly one {name} in saved Terra 5.6 artifact, found {len(found)}")
    return found[0]


def iso_day(value: str) -> None:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("Frozen temporal boundary must carry a timezone")
    if parsed.date().isoformat() != DAY:
        raise RuntimeError("Frozen cutoff does not belong to the 2026-10-28 experiment")


def inputs() -> dict[str, str]:
    return {name: sha256(ROOT / name) for name in INPUT_PATHS}


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def baseline(dest: Path) -> None:
    if os.getenv("GITHUB_EVENT_NAME") != "schedule" or os.getenv("GITHUB_RUN_ATTEMPT") != "1":
        raise RuntimeError("Baseline only allowed on the original scheduled run")
    write(dest, {
        "experiment": "terra61-one-shot",
        "publication_date": DAY,
        "production_model": PROD_MODEL,
        "source_sha": git_head(),
        "input_sha256": inputs(),
        "image_shadow_enabled": False,
        "production_mutation_shadow_enabled": False,
    })


def prepare(source: Path, evidence: Path, github_env: Path, expected_sha: str, run_id: str) -> None:
    original = read(one_under(source, BASELINE_NAME))
    if original.get("publication_date") != DAY or original.get("production_model") != PROD_MODEL:
        raise RuntimeError("Incompatible baseline artifact")
    if original.get("source_sha") != expected_sha or git_head() != expected_sha:
        raise RuntimeError("Shadow checkout does not match paid production source SHA")
    if original.get("input_sha256") != inputs():
        raise RuntimeError("Frozen input hashes differ from the original Terra 5.6 baseline")

    primary = read(one_under(source, PRIMARY_NAME))
    run_info = read(one_under(source, "run-info.json"))
    if run_info.get("model_requested") != PROD_MODEL:
        raise RuntimeError("Saved baseline run-info does not identify Terra 5.6")
    if primary.get("status") not in {"complete", "complete_with_gaps"}:
        # Valid 12/12 Primary passes can return zero candidates and explicitly
        # report complete_with_gaps before Hybrid/Coverage recovers the digest.
        raise RuntimeError("Terra 5.6 baseline Primary was not complete")
    window = primary.get("search_window") or {}
    start_at = window.get("start_at")
    end_at = window.get("end_at")
    editorial_cutoff = run_info.get("research_cutoff_at")
    for value in (end_at, editorial_cutoff):
        iso_day(str(value or ""))
    if not isinstance(start_at, str) or not start_at.strip():
        raise RuntimeError("Missing baseline search start")
    if primary.get("search_budget", {}).get("completed_calls") != 12:
        raise RuntimeError("Baseline did not finish the twelve Primary searches")

    detail = {
        "experiment": "terra61-one-shot",
        "date": DAY,
        "shadow_model": SHADOW_MODEL,
        "production_model": PROD_MODEL,
        "production_run_id": run_id,
        "source_sha": expected_sha,
        "baseline_manifest_sha256": sha256(one_under(source, BASELINE_NAME)),
        "baseline_primary_sha256": sha256(one_under(source, PRIMARY_NAME)),
        "baseline_run_info_sha256": sha256(one_under(source, "run-info.json")),
        "input_sha256": inputs(),
        "frozen_primary_search_window": window,
        "frozen_editorial_cutoff": editorial_cutoff,
        "initial_primary_calls": 12,
        "no_publication": True,
        "no_cover_generation": True,
        "status": "prepared",
    }
    write(evidence, detail)
    with github_env.open("a", encoding="utf-8") as fp:
        fp.write(f"AI_DIGEST_TERRA61_PRIMARY_CUTOFF={end_at}\n")
        fp.write(f"AI_DIGEST_TERRA61_EDITORIAL_CUTOFF={editorial_cutoff}\n")
        fp.write(f"AI_DIGEST_TERRA61_SHADOW={DAY}\n")
    print("Исходные файлы и границы Terra 5.6 проверены по SHA-256, shadow готов.")


def finish(evidence: Path, manifest: Path) -> None:
    if evidence.is_file():
        report = read(evidence)
    else:
        report = {"experiment": "terra61-one-shot", "date": DAY, "status": "incomplete"}
    shadow_root = ROOT / "automation" / "preview"
    primary_path = shadow_root / "production-daily" / PRIMARY_NAME
    run_info_path = shadow_root / DAY / "run-info.json"
    errors: list[str] = []
    if primary_path.is_file() and run_info_path.is_file():
        primary = read(primary_path)
        run_info = read(run_info_path)
        if run_info.get("model_requested") != SHADOW_MODEL:
            errors.append("Shadow requested model mismatch")
        for stage in ("research", "editorial"):
            returned = ((run_info.get(stage) or {}).get("response") or {}).get("model_returned")
            if returned and not str(returned).startswith(SHADOW_MODEL):
                errors.append(f"{stage} provider returned unexpected model {returned}")
        if (primary.get("search_window") or {}) != report.get("frozen_primary_search_window"):
            errors.append("Primary window does not match Terra 5.6")
        if run_info.get("research_cutoff_at") != report.get("frozen_editorial_cutoff"):
            errors.append("Editorial cutoff does not match Terra 5.6")
    else:
        errors.append("Full shadow research files not present")
    coverage_file = shadow_root / "production-daily" / "coverage-audit.json"
    if coverage_file.is_file():
        coverage = read(coverage_file)
        report["coverage_status"] = coverage.get("status")
        if coverage.get("status") in {"error", "partial", "technical_partial"}:
            errors.append("Shadow Coverage was not completed")
    else:
        errors.append("Shadow Coverage report not present")
    hashes: dict[str, str] = {}
    for base in (
        shadow_root / DAY,
        shadow_root / "production-daily",
        ROOT / "automation" / "fixtures" / "research" / ".runtime",
    ):
        if base.is_dir():
            for path in sorted(base.rglob("*")):
                if path.is_file() and path != manifest and not path.is_symlink():
                    hashes[str(path.relative_to(ROOT))] = sha256(path)
    report["saved_output_sha256"] = hashes
    report["saved_file_count"] = len(hashes)
    report["status"] = "complete" if not errors else "partial"
    report["errors"] = errors
    write(manifest, report)
    print(f"Экспериментальный артефакт: {report['status']}; файлов с SHA-256: {len(hashes)}")
    if errors:
        raise RuntimeError("; ".join(errors))


def main() -> None:
    p = argparse.ArgumentParser()
    cmds = p.add_subparsers(dest="command", required=True)
    b = cmds.add_parser("baseline")
    b.add_argument("--output", type=Path, required=True)
    q = cmds.add_parser("prepare")
    q.add_argument("--production-dir", type=Path, required=True)
    q.add_argument("--output", type=Path, required=True)
    q.add_argument("--github-env", type=Path, required=True)
    q.add_argument("--expected-sha", required=True)
    q.add_argument("--run-id", required=True)
    f = cmds.add_parser("finish")
    f.add_argument("--evidence", type=Path, required=True)
    f.add_argument("--manifest", type=Path, required=True)
    a = p.parse_args()
    if a.command == "baseline":
        baseline(a.output)
    elif a.command == "prepare":
        prepare(a.production_dir, a.output, a.github_env, a.expected_sha, a.run_id)
    elif a.command == "finish":
        finish(a.evidence, a.manifest)


if __name__ == "__main__":
    main()
