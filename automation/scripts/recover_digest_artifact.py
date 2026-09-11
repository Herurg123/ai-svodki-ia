#!/usr/bin/env python3
"""P0 recovery guard layered over the established recovery wrapper.

The pre-P0 wrapper is retained verbatim in ``recover_digest_artifact_pre_p0.py``.
This seam narrows recovery evidence to the same artifact bundle that supplied
``candidates.json`` and makes unresolved Coverage editorial repair force
``partial_editorial`` mode, which in turn makes the pinned text runtime available.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

from editorial_repair_journal import recovery_has_pending_editorial_repair

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


def _selected_evidence_root(source_dir: Path, recovery_root: Path) -> Path:
    source = source_dir.resolve()
    root = recovery_root.resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise RecoveryError(
            "Selected recovery source is outside the requested recovery root"
        ) from exc
    # The artifact upload stores preview/YYYY-MM-DD and preview/production-daily
    # as siblings. Evidence used to continue this source must come from that
    # exact preview bundle, never from another same-date subtree.
    return source.parent


def choose_source(
    recovery_root: Path,
    publication_date: str,
) -> tuple[Path, str, list[dict[str, Any]]]:
    global _ACTIVE_EVIDENCE_ROOT
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

    if mode == "full" and recovery_has_pending_editorial_repair(
        evidence_root, publication_date
    ):
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
    # Let the established wrapper wire all of its current recovery hooks first.
    _pre.choose_source = choose_source
    _pre._sync_base()
    # Then constrain the two historically global evidence restorers to the
    # bundle selected by choose_source(). This is deliberately fail-closed:
    # another same-date subtree can no longer lend candidates/audit state.
    _pre._base.restore_merged_coverage_research = _restore_merged_same_bundle
    _pre._base.restore_prior_coverage_audit = _restore_audit_same_bundle
    _pre._base.restore_completed_coverage_audit = _restore_audit_same_bundle


def recover(
    recovery_root: Path,
    target_dir: Path,
    publication_date: str,
    report_path: Path,
    timezone_name: str = "Europe/Moscow",
    image_target_dir: Path | None = None,
) -> dict[str, Any]:
    _sync_p0()
    return _pre.recover(
        recovery_root,
        target_dir,
        publication_date,
        report_path,
        timezone_name,
        image_target_dir,
    )


def main() -> int:
    _sync_p0()
    # _pre.main() performs the stable argument parsing, error reporting and
    # diagnostics. Its own _sync_base() sees our overridden choose_source.
    return int(_pre.main())


if __name__ == "__main__":
    raise SystemExit(main())
