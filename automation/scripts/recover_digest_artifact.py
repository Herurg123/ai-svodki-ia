#!/usr/bin/env python3
"""P0 recovery guard layered over the established recovery wrapper.

The pre-P0 wrapper is retained verbatim in ``recover_digest_artifact_pre_p0.py``.
This seam keeps all existing retrieval-quality and agency-rescue recovery behavior
while adding three fail-closed rules:

* Coverage evidence must come from the same extracted artifact bundle that
  supplied the selected dated artifact;
* a full artifact is downgraded to ``partial_editorial`` whenever its saved
  Coverage state can still require editorial completion, which makes the
  workflow install/validate the pinned text runtime without repeating research;
* durable repair journal/response/merged research are restored only from that
  same selected bundle.

Compatibility seam removal target: after 2026-10-03, once saved-artifact recovery
fixtures prove the consolidated implementation preserves public import hooks.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from editorial_repair_guard import (
    EditorialRepairError,
    recovery_pending,
    restore_state_from_bundle,
)

_PRE_PATH = Path(__file__).with_name("recover_digest_artifact_pre_p0.py")
_PRE_SPEC = importlib.util.spec_from_file_location(
    "recover_digest_artifact_pre_p0", _PRE_PATH
)
assert _PRE_SPEC and _PRE_SPEC.loader
_pre = importlib.util.module_from_spec(_PRE_SPEC)
sys.modules[_PRE_SPEC.name] = _pre
_PRE_SPEC.loader.exec_module(_pre)

for _name in dir(_pre):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_pre, _name)


def __getattr__(name: str) -> Any:
    return getattr(_pre, name)


_PRE_CHOOSE_SOURCE = _pre.choose_source
_PRE_RESTORE_MERGED = _pre._base.restore_merged_coverage_research
_PRE_RESTORE_AUDIT = _pre._base.restore_prior_coverage_audit
_ACTIVE_EVIDENCE_ROOT: Path | None = None
_DELEGATE_EXCLUSIONS = {
    "main",
    "recover",
    "choose_source",
    "_sync_p0",
    "_sync_public_hooks",
    "_restore_merged_same_bundle",
    "_restore_audit_same_bundle",
    "_restore_durable_p0_state",
}


def _sync_public_hooks() -> None:
    """Preserve historical monkeypatch hooks exposed by the public entrypoint."""
    current = globals()
    for name, value in list(current.items()):
        if name.startswith("__") and name.endswith("__"):
            continue
        if name in _DELEGATE_EXCLUSIONS or name.startswith("_PRE_"):
            continue
        if name in _pre.__dict__:
            setattr(_pre, name, value)


def _selected_evidence_root(source_dir: Path, recovery_root: Path) -> Path:
    source = source_dir.resolve()
    root = recovery_root.resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise RecoveryError(
            "Selected recovery source is outside the requested recovery root"
        ) from exc
    # Artifact uploads store preview/YYYY-MM-DD and preview/production-daily as
    # siblings. Any Coverage/journal evidence used to continue this source must
    # come from that exact preview bundle, never a second same-date subtree.
    return source.parent


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _coverage_may_require_editorial(
    evidence_root: Path, publication_date: str
) -> bool:
    """Whether Coverage positively proves a same-day text runtime obligation.

    This is a runtime-readiness decision only. Returning True installs/validates
    the text runtime; it does not itself authorize or execute an API call.
    Missing optional Coverage diagnostics are not positive evidence and must not
    downgrade an otherwise current full recovery artifact.
    """
    state_dir = evidence_root / "production-daily"
    report = _read_optional_json(state_dir / "coverage-audit.json")
    if report is None:
        return False
    if report.get("publication_date") not in {None, publication_date}:
        return False
    if (
        report.get("editorial_rerun_required") is True
        and report.get("editorial_rerun_performed") is not True
    ) or (
        report.get("editorial_completion_required") is True
        and report.get("editorial_completion_performed") is not True
    ):
        return True
    if report.get("audit_status") not in {"complete", "complete_with_gaps"}:
        return True
    quality = report.get("retrieval_quality")
    if (
        report.get("retrieval_quality_contract_version") != 1
        or not isinstance(quality, dict)
        or quality.get("status") != "complete"
    ):
        return True
    return False


def choose_source(
    recovery_root: Path,
    publication_date: str,
) -> tuple[Path, str, list[dict[str, Any]]]:
    global _ACTIVE_EVIDENCE_ROOT
    _sync_public_hooks()
    source_dir, mode, diagnostics = _PRE_CHOOSE_SOURCE(
        recovery_root, publication_date
    )
    evidence_root = _selected_evidence_root(source_dir, recovery_root)
    _ACTIVE_EVIDENCE_ROOT = evidence_root

    reasons: list[dict[str, Any]] = []
    if mode == "full" and _pre._modern_primary_artifact(source_dir, evidence_root):
        if _pre._current_quality_report(evidence_root, publication_date) is None:
            reasons.append(
                {
                    "status": "same-bundle-quality-contract-upgrade",
                    "retrieval_quality_contract_version": _pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
                    "reason": "current Retrieval Quality report is missing from selected artifact bundle",
                }
            )
        agency_needed, agency_reason = _pre.agency_discovery_upgrade_needed(
            source_dir, evidence_root, publication_date
        )
        if agency_needed:
            reasons.append(
                {
                    "status": "same-bundle-agency-discovery-contract-upgrade",
                    "agency_discovery_rescue_version": 5,
                    "agency_health_trigger_version": _pre.AGENCY_HEALTH_TRIGGER_VERSION,
                    "reason": agency_reason,
                }
            )

    if mode == "full" and _coverage_may_require_editorial(
        evidence_root, publication_date
    ):
        reasons.append(
            {
                "status": "editorial-runtime-required",
                "reason": (
                    "selected artifact bundle has positive same-day Coverage "
                    "evidence that saved-research editorial completion may still run"
                ),
            }
        )

    if mode == "full" and recovery_pending(evidence_root, publication_date):
        reasons.append(
            {
                "status": "editorial-repair-pending",
                "reason": (
                    "selected artifact bundle contains an unresolved Coverage "
                    "editorial repair/completion obligation"
                ),
            }
        )

    if reasons:
        mode = "partial_editorial"
        diagnostics = copy.deepcopy(diagnostics)
        for reason in reasons:
            diagnostics.append(
                {
                    "directory": str(source_dir),
                    **reason,
                    "action": (
                        "downgrade full recovery to partial_editorial; reuse paid "
                        "research and make pinned text runtime available without "
                        "repeating full research"
                    ),
                }
            )
    return source_dir, mode, diagnostics


def _restore_merged_same_bundle(
    recovery_root: Path,
    target_dir: Path,
    publication_date: str,
) -> dict[str, Any] | None:
    evidence_root = _ACTIVE_EVIDENCE_ROOT or recovery_root
    return _PRE_RESTORE_MERGED(
        evidence_root, target_dir, publication_date
    )


def _restore_audit_same_bundle(
    recovery_root: Path,
    report_path: Path,
    publication_date: str,
) -> dict[str, Any] | None:
    evidence_root = _ACTIVE_EVIDENCE_ROOT or recovery_root
    return _PRE_RESTORE_AUDIT(
        evidence_root, report_path, publication_date
    )


def _sync_p0() -> None:
    _sync_public_hooks()
    _pre.choose_source = choose_source
    _pre._sync_base()
    _pre._base.restore_merged_coverage_research = _restore_merged_same_bundle
    _pre._base.restore_prior_coverage_audit = _restore_audit_same_bundle
    _pre._base.restore_completed_coverage_audit = _restore_audit_same_bundle


def _bundle_has_p0_journal(recovery_root: Path, publication_date: str) -> bool:
    name = f"editorial-repair-{publication_date}.json"
    return any(path.is_file() for path in recovery_root.rglob(name))


def _restore_durable_p0_state(
    report: dict[str, Any],
    publication_date: str,
    report_path: Path,
    recovery_root: Path,
) -> dict[str, Any]:
    evidence_root = _ACTIVE_EVIDENCE_ROOT
    if evidence_root is None:
        # Historical and ordinary recovery artifacts predate the P0 journal. Do
        # not make those fixtures unusable merely because they have nothing P0
        # to restore. If a P0 journal is actually present, however, source
        # identity is mandatory and recovery remains fail-closed.
        if _bundle_has_p0_journal(recovery_root, publication_date):
            raise RecoveryError("selected recovery evidence root was not recorded")
        return {
            "repair_state": {
                "status": "not_present",
                "copied": [],
                "publication_date": publication_date,
            },
            "persisted_merged_research": None,
        }

    state_dir = report_path.parent.resolve()
    try:
        repair = restore_state_from_bundle(
            bundle_root=evidence_root,
            target_state_dir=state_dir,
            publication_date=publication_date,
        )
    except EditorialRepairError as exc:
        raise RecoveryError(str(exc)) from exc

    merged = report.get("merged_coverage_research")
    copied_research = None
    if isinstance(merged, dict):
        source_value = merged.get("source")
        if isinstance(source_value, str) and source_value.strip():
            source = Path(source_value)
            source = source.resolve() if source.is_absolute() else (Path.cwd() / source).resolve()
            try:
                source.relative_to(evidence_root.resolve())
            except ValueError as exc:
                raise RecoveryError(
                    "merged Coverage research came from a different artifact bundle"
                ) from exc
            if source.is_file():
                target = state_dir / f"coverage-audit-merged-candidates-{publication_date}.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied_research = str(target)
    return {
        "repair_state": repair,
        "persisted_merged_research": copied_research,
    }


def recover(
    recovery_root: Path,
    target_dir: Path,
    publication_date: str,
    report_path: Path,
    timezone_name: str = "Europe/Moscow",
    image_target_dir: Path | None = None,
) -> dict[str, Any]:
    global _ACTIVE_EVIDENCE_ROOT
    _ACTIVE_EVIDENCE_ROOT = None
    _sync_p0()
    report = _pre.recover(
        recovery_root,
        target_dir,
        publication_date,
        report_path,
        timezone_name,
        image_target_dir,
    )
    report["editorial_repair_recovery"] = _restore_durable_p0_state(
        report, publication_date, report_path, recovery_root
    )
    write_json(report_path, report)
    return report


def main() -> int:
    global _ACTIVE_EVIDENCE_ROOT
    _ACTIVE_EVIDENCE_ROOT = None
    _sync_p0()
    args = _pre._base.parse_args()
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
        f"{report.get('agency_discovery_rescue_recovery', {}).get('status')}; "
        "editorial_repair_state="
        f"{report.get('editorial_repair_recovery', {}).get('repair_state', {}).get('status')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
