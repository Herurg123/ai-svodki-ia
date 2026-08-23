#!/usr/bin/env python3
"""Resume the bounded agency discovery stage when Coverage follows recovery.

Fresh runs execute agency discovery before Hybrid.  Recovery intentionally does
not repeat Hybrid, so a recovered Primary checkpoint needs one idempotent entry
before Coverage: reuse/repair a saved rescue response, never retry an uncertain
``search_started`` state, or perform the first rescue search if the crash
happened before the rescue began.

If a rescue-origin candidate is present, this helper stages the recovered pool
through the unchanged Source Freshness Proof and normal editorial rerun before
Coverage decides whether the numerical story target is already satisfied.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

import agency_discovery_rescue as rescue
from source_freshness import verify_research_file
from story_coverage import read_json, write_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RECOVERY_REPORT = REPOSITORY_ROOT / "automation" / "preview" / "production-daily" / "recovery.json"
RECOVERY_RUNTIME_ROOT = (
    REPOSITORY_ROOT / "automation" / "fixtures" / "research" / ".runtime"
)


def _argv_value(flag: str, default: str | None = None) -> str | None:
    try:
        index = sys.argv.index(flag)
    except ValueError:
        return default
    if index + 1 >= len(sys.argv):
        return default
    return sys.argv[index + 1]


def _int_option(flag: str, default: int) -> int:
    raw = _argv_value(flag)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def recovery_active() -> bool:
    if not RECOVERY_REPORT.is_file():
        return False
    try:
        payload = json.loads(RECOVERY_REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("status") == "ok"


def _rescue_candidates_present(research: dict[str, Any]) -> bool:
    return any(
        isinstance(item, dict)
        and item.get("audit_direction") == rescue.AGENCY_DISCOVERY_RESCUE_DIRECTION
        and item.get("recommendation") in {"include", "consider"}
        for item in research.get("candidates", [])
    )


def _without_rescue_candidates(research: dict[str, Any]) -> dict[str, Any]:
    """Drop supplemental rescue rows if their freshness gate itself fails."""
    clean = copy.deepcopy(research)
    rows = clean.get("candidates")
    if isinstance(rows, list):
        clean["candidates"] = [
            item
            for item in rows
            if not (
                isinstance(item, dict)
                and item.get("audit_direction")
                == rescue.AGENCY_DISCOVERY_RESCUE_DIRECTION
            )
        ]
        for index, item in enumerate(clean["candidates"], start=1):
            if isinstance(item, dict):
                item["id"] = f"cand-{index:03d}"
    return clean


def _persist_runtime_report(
    report: dict[str, Any], *, artifact_dir: Path, publication_date: str
) -> None:
    rescue._persist_report(
        report,
        artifact_dir=artifact_dir,
        output_root=rescue.PRODUCTION_PREVIEW_ROOT,
        publication_date=publication_date,
    )


def run_recovery_entry(
    *,
    rerun_editorial_fn: Callable[..., None],
) -> dict[str, Any]:
    """Run the recovered quality stage. Never raises for rescue-only failure."""
    if not recovery_active():
        return {"status": "not_recovery", "search_performed": False}

    artifact_raw = _argv_value("--artifact-dir")
    archive_raw = _argv_value("--archive")
    publication_date = _argv_value("--publication-date")
    model = _argv_value("--model") or os.getenv("OPENAI_TEXT_MODEL", "gpt-5.6-terra")
    if not artifact_raw or not archive_raw or not publication_date:
        return {
            "status": "invalid_coverage_arguments",
            "search_performed": False,
        }

    artifact_dir = (REPOSITORY_ROOT / artifact_raw).resolve()
    archive_path = (REPOSITORY_ROOT / archive_raw).resolve()
    candidates_path = artifact_dir / "candidates.json"
    source_freshness_report = (
        REPOSITORY_ROOT
        / "automation"
        / "preview"
        / "production-daily"
        / f"source-freshness-{publication_date}.json"
    )
    try:
        original_research = read_json(candidates_path)
    except Exception as exc:
        return {
            "status": "invalid_recovered_candidates",
            "error": f"{type(exc).__name__}: {exc}",
            "search_performed": False,
        }
    if not isinstance(original_research, dict):
        return {
            "status": "invalid_recovered_candidates",
            "search_performed": False,
        }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    try:
        report = rescue.run_agency_discovery_rescue(
            artifact_dir=artifact_dir,
            archive_path=archive_path,
            publication_date=publication_date,
            api_key=api_key,
            model=model,
            maximum_candidates=_int_option("--maximum-candidates", 20),
        )
    except Exception as exc:
        return {
            "status": "rescue_integration_error",
            "error": f"{type(exc).__name__}: {exc}",
            "search_performed": False,
        }

    report["coverage_recovery_entry"] = True
    try:
        current_research = read_json(candidates_path)
    except Exception:
        current_research = original_research
    if not isinstance(current_research, dict) or not _rescue_candidates_present(current_research):
        report["coverage_recovery_editorial_rerun"] = "not_needed"
        _persist_runtime_report(report, artifact_dir=artifact_dir, publication_date=publication_date)
        return report

    RECOVERY_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    runtime_path = RECOVERY_RUNTIME_ROOT / f"agency-discovery-recovery-{publication_date}.json"
    write_json(runtime_path, copy.deepcopy(current_research))
    try:
        freshness_run = verify_research_file(
            runtime_path,
            publication_date=publication_date,
            report_path=source_freshness_report,
        )
        verified_research = read_json(runtime_path)
        if not isinstance(verified_research, dict):
            raise RuntimeError("verified recovery research is not an object")
        # Persist the exact freshness-verified pool before editorial. If the
        # editor later fails, Coverage can continue from a safe research state.
        write_json(candidates_path, verified_research)
        report["coverage_recovery_source_freshness"] = {
            "status": "complete",
            "eligible_before": freshness_run.get("eligible_before"),
            "eligible_after": freshness_run.get("eligible_after"),
            "verified_fresh": freshness_run.get("verified_fresh"),
            "excluded_outside_window": freshness_run.get("excluded_outside_window"),
            "excluded_unverified_freshness": freshness_run.get("excluded_unverified_freshness"),
        }
    except Exception as exc:
        # Rescue is supplemental and cannot poison a previously usable artifact.
        # Remove every rescue-origin row rather than restoring a possibly
        # pre-existing but never freshness-verified rescue candidate.
        write_json(candidates_path, _without_rescue_candidates(original_research))
        report["coverage_recovery_source_freshness"] = {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        report["coverage_recovery_editorial_rerun"] = "skipped_after_freshness_error"
        _persist_runtime_report(report, artifact_dir=artifact_dir, publication_date=publication_date)
        try:
            runtime_path.unlink()
        except OSError:
            pass
        return report

    try:
        rerun_editorial_fn(
            publication_date=publication_date,
            merged_research_path=runtime_path,
            minimum_total=_int_option("--minimum-total", _int_option("--usual-total", 7)),
            maximum_candidates=_int_option("--maximum-candidates", 20),
            maximum_selected_stories=_int_option("--maximum-selected-stories", 12),
        )
    except Exception as exc:
        # Keep the freshness-verified research and the pre-existing digest.
        # Coverage may still complete from that safe state.
        report["coverage_recovery_editorial_rerun"] = "error_nonfatal"
        report["coverage_recovery_editorial_error"] = f"{type(exc).__name__}: {exc}"
    else:
        report["coverage_recovery_editorial_rerun"] = "completed"
    finally:
        try:
            runtime_path.unlink()
        except OSError:
            pass

    _persist_runtime_report(report, artifact_dir=artifact_dir, publication_date=publication_date)
    return report
