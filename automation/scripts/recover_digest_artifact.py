#!/usr/bin/env python3
"""Retrieval-quality-aware wrapper over the stable artifact recovery engine.

Modern paid research remains reusable, but a full artifact created before the
current retrieval-quality contract is downgraded to partial editorial recovery.
This makes production run Coverage again, where the six already-paid mandatory
passes can be reused and only the missing quality-resolution slot is executed.

Agency-discovery rescue recovery is deliberately at-most-once.  A saved
``search_completed``/``merge_failed`` response may finish merge without an API
call.  A saved ``search_started`` state is never retried automatically because
whether the provider consumed the one allowed search is unknowable.  If Primary
was saved but the rescue had not started yet, recovery reports a pending first
attempt for the later quality-layer entrypoint instead of spending API here.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

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


_BASE_CHOOSE_SOURCE = _base.choose_source
_BASE_RECOVER = _base.recover
RETRIEVAL_QUALITY_CONTRACT_VERSION = 1


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


def choose_source(
    recovery_root: Path,
    publication_date: str,
) -> tuple[Path, str, list[dict[str, Any]]]:
    source_dir, mode, diagnostics = _BASE_CHOOSE_SOURCE(recovery_root, publication_date)
    if (
        mode == "full"
        and _modern_primary_artifact(source_dir, recovery_root)
        and _current_quality_report(recovery_root, publication_date) is None
    ):
        mode = "partial_editorial"
        diagnostics = copy.deepcopy(diagnostics)
        diagnostics.append(
            {
                "directory": str(source_dir),
                "status": "quality-contract-upgrade",
                "retrieval_quality_contract_version": RETRIEVAL_QUALITY_CONTRACT_VERSION,
                "action": "downgrade full recovery to partial_editorial; reuse paid research and rerun Coverage quality stage",
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
            archive_path=Path(REPOSITORY_ROOT) / "automation" / "archive" / "index.json",
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
