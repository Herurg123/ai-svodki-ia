#!/usr/bin/env python3
"""Retrieval-quality-aware wrapper over the stable artifact recovery engine.

Modern paid research remains reusable, but a full artifact created before the
current retrieval-quality contract is downgraded to partial editorial recovery.
This makes production run Coverage again, where the six already-paid mandatory
passes can be reused and only the missing quality-resolution slot is executed.

Agency-discovery rescue recovery is deliberately at-most-once. A saved
``search_completed``/``merge_failed`` response may finish merge without an API
call. A saved ``search_started`` state is never retried automatically because
whether the provider consumed the one allowed search is unknowable. A zero-spend
``not_triggered`` state may be deterministically reconsidered when the current
post-freshness/editorial pool proves that the formerly accepted Primary
major-agency candidate no longer has a viable survivor.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

from agency_health_viability import (
    AGENCY_HEALTH_TRIGGER_VERSION,
    evaluate_agency_health,
    prior_not_triggered_recheck_allowed,
)

_BASE_PATH = Path(__file__).with_name("recover_digest_artifact_v1.py")
_BASE_SPEC = importlib.util.spec_from_file_location("recover_digest_artifact_v1", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)


def __getattr__(name: str) -> Any:
    """Preserve the historical module surface for tests and recovery hooks."""
    return getattr(_base, name)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_BASE_CHOOSE_SOURCE = _base.choose_source
_BASE_RECOVER = _base.recover
RETRIEVAL_QUALITY_CONTRACT_VERSION = 1
_AGENCY_DISCOVERY_TERMINAL_STATES = {
    "not_triggered",
    "completed",
    "completed_no_addition",
    "search_failed",
    "indeterminate_after_interruption",
    "diagnostics_missing",
}


def _modern_primary_artifact(source_dir: Path, recovery_root: Path) -> bool:
    if (source_dir / "primary-recall.json").is_file():
        return True
    return any(path.is_file() for path in recovery_root.rglob("primary-recall*.json"))


def _current_quality_report(recovery_root: Path, publication_date: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for path in recovery_root.rglob("coverage-audit.json"):
        if not path.is_file():
            continue
        try:
            payload = read_json(path)
        except Exception:
            continue
        if not isinstance(payload, dict) or payload.get("publication_date") != publication_date:
            continue
        candidates.append(payload)
    for payload in candidates:
        quality = payload.get("retrieval_quality")
        if (
            payload.get("retrieval_quality_contract_version") == RETRIEVAL_QUALITY_CONTRACT_VERSION
            and isinstance(quality, dict)
            and quality.get("status") == "complete"
        ):
            return payload
    return None


def _primary_report(
    source_dir: Path, recovery_root: Path, publication_date: str
) -> dict[str, Any] | None:
    paths = [source_dir / "primary-recall.json"]
    paths.extend(sorted(recovery_root.rglob(f"primary-recall-{publication_date}.json")))
    paths.extend(sorted(recovery_root.rglob("primary-recall.json")))
    seen: set[Path] = set()
    for path in paths:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            payload = read_json(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        found_date = payload.get("publication_date")
        if found_date not in {None, publication_date}:
            continue
        return payload
    return None


def _major_agencies_requires_discovery(primary: dict[str, Any] | None) -> bool:
    """Preserved early-trigger helper used by older tests/recovery artifacts."""
    if not isinstance(primary, dict):
        return False
    rows = primary.get("directions")
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict) or row.get("direction_id") != "major_agencies":
            continue
        if row.get("status") not in {"complete", "complete_with_gaps"}:
            return False
        raw = row.get("raw_candidates")
        raw_count = len(raw) if isinstance(raw, list) else 0
        accepted_count = int(row.get("accepted_count", 0) or 0)
        return raw_count == 0 or accepted_count == 0
    return False


def _current_research(source_dir: Path) -> dict[str, Any] | None:
    path = source_dir / "candidates.json"
    if not path.is_file():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _agency_health_requires_discovery(
    primary: dict[str, Any] | None,
    current_research: dict[str, Any] | None,
) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(primary, dict):
        return False, "major_agencies_not_triggered", {
            "version": AGENCY_HEALTH_TRIGGER_VERSION,
            "status": "primary_missing",
            "paid_api_calls": 0,
            "web_search_operations": 0,
        }
    if isinstance(current_research, dict):
        triggered, reason, _facts, diagnostics = evaluate_agency_health(
            primary_report=primary,
            current_research=current_research,
        )
        return (
            triggered,
            reason or "major_agencies_not_triggered",
            diagnostics,
        )
    early = _major_agencies_requires_discovery(primary)
    return early, (
        "major_agencies_early_gap" if early else "major_agencies_not_triggered"
    ), {
        "version": AGENCY_HEALTH_TRIGGER_VERSION,
        "status": "current_research_missing_early_trigger_only",
        "paid_api_calls": 0,
        "web_search_operations": 0,
    }


def _agency_state(
    source_dir: Path, recovery_root: Path, publication_date: str
) -> dict[str, Any] | None:
    paths = [source_dir / "agency-discovery-rescue.json"]
    paths.extend(
        sorted(recovery_root.rglob(f"agency-discovery-rescue-{publication_date}.json"))
    )
    paths.extend(sorted(recovery_root.rglob("agency-discovery-rescue.json")))
    seen: set[Path] = set()
    for path in paths:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            payload = read_json(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("publication_date") not in {None, publication_date}:
            continue
        if payload.get("search_strategy") not in {None, "agency_discovery_rescue"}:
            continue
        return payload
    return None


def agency_discovery_upgrade_needed(
    source_dir: Path, recovery_root: Path, publication_date: str
) -> tuple[bool, str]:
    """Whether full recovery still needs text runtime for agency discovery work."""
    primary = _primary_report(source_dir, recovery_root, publication_date)
    triggered, trigger_reason, _health = _agency_health_requires_discovery(
        primary, _current_research(source_dir)
    )
    if not triggered:
        return False, "major_agencies_not_triggered"
    state = _agency_state(source_dir, recovery_root, publication_date)
    if not isinstance(state, dict):
        return True, f"agency_discovery_first_attempt_pending:{trigger_reason}"
    value = str(state.get("state") or "")
    if value == "not_triggered" and prior_not_triggered_recheck_allowed(state):
        return True, f"agency_discovery_not_triggered_recheck:{trigger_reason}"
    if value in _AGENCY_DISCOVERY_TERMINAL_STATES:
        return False, f"agency_discovery_terminal:{value}"
    if value == "search_started":
        # Outcome is unknowable. At-most-once semantics prohibit another search.
        return False, "agency_discovery_indeterminate_no_retry"
    if value in {"search_completed", "merge_failed"}:
        # No second search is needed, but merge/freshness/editorial may still be.
        return True, f"agency_discovery_resume_pending:{value}"
    return True, f"agency_discovery_unknown_state:{value or 'missing'}"


def choose_source(
    recovery_root: Path,
    publication_date: str,
) -> tuple[Path, str, list[dict[str, Any]]]:
    source_dir, mode, diagnostics = _BASE_CHOOSE_SOURCE(recovery_root, publication_date)
    downgrade_reasons: list[dict[str, Any]] = []
    if mode == "full" and _modern_primary_artifact(source_dir, recovery_root):
        if _current_quality_report(recovery_root, publication_date) is None:
            downgrade_reasons.append(
                {
                    "status": "quality-contract-upgrade",
                    "retrieval_quality_contract_version": RETRIEVAL_QUALITY_CONTRACT_VERSION,
                    "reason": "current Retrieval Quality report is missing",
                }
            )
        agency_needed, agency_reason = agency_discovery_upgrade_needed(
            source_dir, recovery_root, publication_date
        )
        if agency_needed:
            downgrade_reasons.append(
                {
                    "status": "agency-discovery-contract-upgrade",
                    "agency_discovery_rescue_version": 5,
                    "agency_health_trigger_version": AGENCY_HEALTH_TRIGGER_VERSION,
                    "reason": agency_reason,
                }
            )
    if downgrade_reasons:
        mode = "partial_editorial"
        diagnostics = copy.deepcopy(diagnostics)
        for reason in downgrade_reasons:
            diagnostics.append(
                {
                    "directory": str(source_dir),
                    **reason,
                    "action": (
                        "downgrade full recovery to partial_editorial; reuse paid "
                        "research and make text runtime available for pending quality work"
                    ),
                }
            )
    return source_dir, mode, diagnostics


def _sync_base() -> None:
    _base.choose_source = choose_source


def _resume_agency_discovery_without_search(
    *, target_dir: Path, publication_date: str
) -> dict[str, Any]:
    """Repair a persisted rescue state without ever issuing Web Search."""
    state_path = target_dir / "agency-discovery-rescue.json"
    primary_path = target_dir / "primary-recall.json"
    if not primary_path.is_file():
        return {"status": "not_applicable", "reason": "primary_recall_missing"}
    if not state_path.is_file():
        return {
            "status": "pending_first_attempt",
            "reason": "primary checkpoint recovered before agency discovery rescue started",
            "search_performed": False,
        }
    try:
        saved = read_json(state_path)
    except Exception as exc:
        return {
            "status": "state_unreadable",
            "error": f"{type(exc).__name__}: {exc}",
            "search_performed": False,
        }
    if not isinstance(saved, dict):
        return {
            "status": "state_unreadable",
            "reason": "agency-discovery-rescue.json is not an object",
            "search_performed": False,
        }
    state = str(saved.get("state") or "")
    if state not in {"search_started", "search_completed", "merge_failed"}:
        return {
            "status": "reused",
            "state": state,
            "search_performed": False,
            "search_operation_count_contribution": int(
                saved.get("search_operation_count_contribution", 0) or 0
            ),
        }

    from agency_discovery_rescue import run_agency_discovery_rescue

    def forbidden_search(**_kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        raise RuntimeError("recovery must never repeat agency discovery Web Search")

    try:
        repaired = run_agency_discovery_rescue(
            artifact_dir=target_dir,
            archive_path=REPOSITORY_ROOT / "automation" / "archive" / "index.json",
            publication_date=publication_date,
            api_key="",
            model="",
            search_runner=forbidden_search,
        )
    except Exception as exc:
        return {
            "status": "repair_error",
            "state": state,
            "error": f"{type(exc).__name__}: {exc}",
            "search_performed": False,
        }
    return {
        "status": "repaired" if state in {"search_completed", "merge_failed"} else "reused",
        "prior_state": state,
        "state": repaired.get("state"),
        "search_performed": False,
        "search_operation_count_contribution": int(
            repaired.get("search_operation_count_contribution", 0) or 0
        ),
        "added_count": int(repaired.get("added_count", 0) or 0),
        "resumed": bool(repaired.get("resumed")),
    }


def recover(
    recovery_root: Path,
    target_dir: Path,
    publication_date: str,
    report_path: Path,
    timezone_name: str = "Europe/Moscow",
    image_target_dir: Path | None = None,
) -> dict[str, Any]:
    _sync_base()
    report = _BASE_RECOVER(
        recovery_root,
        target_dir,
        publication_date,
        report_path,
        timezone_name,
        image_target_dir,
    )
    report["agency_discovery_rescue_recovery"] = _resume_agency_discovery_without_search(
        target_dir=target_dir,
        publication_date=publication_date,
    )
    write_json(report_path, report)
    return report


def main() -> int:
    _sync_base()
    args = _base.parse_args()
    try:
        report = recover(
            args.recovery_root,
            args.target_dir,
            args.publication_date,
            args.report,
            args.timezone,
            args.image_target_dir,
        )
    except RecoveryError as exc:
        write_json(
            args.report,
            {
                "status": "error",
                "publication_date": args.publication_date,
                "recovery_root": str(args.recovery_root),
                "error": str(exc),
            },
        )
        print(f"Digest recovery failed: {exc}")
        return 1
    print(
        "Digest recovery: ok; "
        f"mode={report['recovery_mode']}; selected {report['selected_source']}; "
        "agency_discovery_rescue="
        f"{report.get('agency_discovery_rescue_recovery', {}).get('status')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
