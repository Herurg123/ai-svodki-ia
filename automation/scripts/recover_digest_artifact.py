#!/usr/bin/env python3
"""Coverage optional-slot recovery over the preserved P0 recovery wrapper.

``recover_digest_artifact_p0.py`` is the byte-for-byte pre-slot implementation.
This layer preserves its public monkeypatch/recovery surface and adds two bounded
rules above it:

* optional seventh-slot journal/response state may be restored only from the exact
  artifact bundle already selected by P0 recovery;
* P3b v7 quarantine state is restored from that same bundle, and a full artifact
  carrying an unresolved stale-positive revocation obligation is downgraded to
  ``partial_editorial`` so the clean downstream rebuild can actually run.

Neither rule performs provider I/O or refunds/reopens the optional seventh slot.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from coverage_slot_guard import (
    CoverageSlotError,
    JOURNAL_PREFIX,
    restore_state_from_bundle as restore_coverage_slot_state_from_bundle,
)

_BASE_PATH = Path(__file__).with_name("recover_digest_artifact_p0.py")
_BASE_SPEC = importlib.util.spec_from_file_location("recover_digest_artifact_p0", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)


def __getattr__(name: str) -> Any:
    return getattr(_base, name)


_P0_CHOOSE_SOURCE = _base.choose_source
_P0_RECOVER = _base.recover
_P0_MAIN = _base.main
_ACTIVE_EVIDENCE_ROOT = getattr(_base, "_ACTIVE_EVIDENCE_ROOT", None)
# Historical direct tests patch this public hook. It lives two wrappers down,
# so materialize and bridge it explicitly instead of relying on __getattr__.
_BASE_CHOOSE_SOURCE = _base._pre._BASE_CHOOSE_SOURCE

_P3B_V7_PREFIX = "coverage-p3b-v7-revocation-"
_P3B_DIAGNOSTIC_KEY = "weak_source_exact_binding"
_P3B_CURRENT_BINDER_EVIDENCE_VERSION = 6
_P3B_V7_BACKUP_KINDS = (
    "candidates",
    "merged-research",
    "coverage-report",
    "stories",
)

_DELEGATE_EXCLUSIONS = {
    "main",
    "recover",
    "choose_source",
    "_restore_optional_slot",
    "_sync_public_hooks",
    "_pull_runtime_state",
    "_ACTIVE_EVIDENCE_ROOT",
    "restore_coverage_slot_state_from_bundle",
    "_read_json_object",
    "_p3b_v7_state_dir",
    "_p3b_v7_marker_path",
    "_p3b_v7_rebuild_reason",
    "_stale_positive_p3b_journal",
    "_bundle_has_p3b_v7_state",
    "_restore_p3b_v7_state",
}


def _sync_public_hooks() -> None:
    current = globals()
    for name, value in list(current.items()):
        if name.startswith("__") and name.endswith("__"):
            continue
        if name in _DELEGATE_EXCLUSIONS or name.startswith("_P0_"):
            continue
        if name in _base.__dict__:
            setattr(_base, name, value)
    # This private hook is exposed only through nested compatibility __getattr__
    # layers. Keep the public monkeypatch seam intact for direct choose_source
    # tests and older recovery consumers.
    _base._pre._BASE_CHOOSE_SOURCE = globals()["_BASE_CHOOSE_SOURCE"]
    if hasattr(_base, "_sync_p0"):
        _base._sync_p0()


def _pull_runtime_state() -> None:
    globals()["_ACTIVE_EVIDENCE_ROOT"] = getattr(
        _base, "_ACTIVE_EVIDENCE_ROOT", None
    )


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _p3b_v7_state_dir(evidence_root: Path) -> Path:
    return Path(evidence_root) / "production-daily"


def _p3b_v7_marker_path(evidence_root: Path, publication_date: str) -> Path:
    return _p3b_v7_state_dir(evidence_root) / (
        f"{_P3B_V7_PREFIX}{publication_date}.json"
    )


def _stale_positive_p3b_journal(
    evidence_root: Path,
    publication_date: str,
) -> bool:
    """Recognize the same pre-v7 stale-positive class for runtime readiness only.

    This helper never deletes candidates and never rewrites the journal. It exists
    only so a pre-v7 full recovery bundle gets a text runtime before active v7
    quarantines its old complete digest. Exact candidate revocation remains owned
    by v7/v6 and their narrow provenance predicate.
    """
    path = _p3b_v7_state_dir(evidence_root) / (
        f"{JOURNAL_PREFIX}{publication_date}.json"
    )
    journal = _read_json_object(path)
    if not isinstance(journal, dict) or str(journal.get("state") or "") != "processed":
        return False
    snapshot = journal.get("processed_snapshot")
    if not isinstance(snapshot, dict):
        return False
    diagnostic = snapshot.get(_P3B_DIAGNOSTIC_KEY)
    if not isinstance(diagnostic, dict):
        # Historical v1 snapshots may predate the diagnostic contract. Matching
        # v6, a processed snapshot with candidate content remains a stale-positive
        # readiness signal; v7 later applies the exact revocation predicate.
        return bool(snapshot.get("candidates"))
    positive = (
        diagnostic.get("status") == "bound_candidate"
        or diagnostic.get("disposition") == "positive_exact_binding"
        or int(diagnostic.get("candidate_count", 0) or 0) > 0
        or any(
            isinstance(item, dict)
            and item.get("audit_direction") == "weak_source_exact_binding"
            for item in snapshot.get("candidates") or []
        )
    )
    if not positive:
        return False
    try:
        evidence_version = int(diagnostic.get("binder_evidence_version", 0) or 0)
    except (TypeError, ValueError):
        evidence_version = 0
    return evidence_version != _P3B_CURRENT_BINDER_EVIDENCE_VERSION


def _p3b_v7_rebuild_reason(
    evidence_root: Path,
    publication_date: str,
) -> str | None:
    """Return a same-bundle reason that a recovered full digest needs text runtime."""
    marker_path = _p3b_v7_marker_path(evidence_root, publication_date)
    if marker_path.is_file():
        marker = _read_json_object(marker_path)
        if marker is None:
            raise RecoveryError("P3b v7 recovery marker is unreadable")
        if str(marker.get("publication_date") or "") != publication_date:
            raise RecoveryError("P3b v7 recovery marker publication date mismatch")
        state = str(marker.get("state") or "")
        if state not in {"pending", "blocked", "completed"}:
            raise RecoveryError(f"P3b v7 recovery marker has invalid state: {state!r}")
        if (
            state in {"pending", "blocked"}
            and marker.get("publication_snapshot_invalidated") is not False
        ):
            return f"p3b_v7_{state}_publication_rebuild"
        # A valid marker supersedes the historical stale journal. Completed means
        # the old journal was deliberately retained but its publication snapshot
        # has already been rebuilt/sanitized; a non-invalidating pending marker is
        # only finishing recovery-input sanitation.
        return None
    if _stale_positive_p3b_journal(evidence_root, publication_date):
        return "pre_v7_stale_positive_processed_evidence"
    return None


def choose_source(
    recovery_root: Path,
    publication_date: str,
) -> tuple[Path, str, list[dict[str, Any]]]:
    _sync_public_hooks()
    try:
        source_dir, mode, diagnostics = _P0_CHOOSE_SOURCE(
            recovery_root, publication_date
        )
    finally:
        _pull_runtime_state()

    evidence_root = getattr(_base, "_ACTIVE_EVIDENCE_ROOT", None)
    if mode == "full" and evidence_root is not None:
        reason = _p3b_v7_rebuild_reason(Path(evidence_root), publication_date)
        if reason:
            mode = "partial_editorial"
            diagnostics = copy.deepcopy(diagnostics)
            diagnostics.append(
                {
                    "directory": str(source_dir),
                    "status": "p3b-v7-recovery-rebuild-required",
                    "reason": reason,
                    "action": (
                        "downgrade full recovery to partial_editorial; keep paid "
                        "research, make the pinned text runtime available, and let "
                        "active v7 sanitize/rebuild without repeating retrieval"
                    ),
                }
            )
    return source_dir, mode, diagnostics


def _bundle_has_slot_journal(recovery_root: Path, publication_date: str) -> bool:
    name = f"{JOURNAL_PREFIX}{publication_date}.json"
    return any(path.is_file() for path in Path(recovery_root).rglob(name))


def _restore_optional_slot(
    *,
    recovery_root: Path,
    report_path: Path,
    publication_date: str,
) -> dict[str, Any]:
    evidence_root = getattr(_base, "_ACTIVE_EVIDENCE_ROOT", None)
    if evidence_root is None:
        if _bundle_has_slot_journal(recovery_root, publication_date):
            raise RecoveryError(
                "Coverage optional-slot journal exists but selected artifact bundle identity is unavailable"
            )
        return {
            "status": "not_present",
            "publication_date": publication_date,
            "copied": [],
        }
    try:
        return restore_coverage_slot_state_from_bundle(
            bundle_root=Path(evidence_root),
            target_state_dir=Path(report_path).parent.resolve(),
            publication_date=publication_date,
        )
    except CoverageSlotError as exc:
        raise RecoveryError(str(exc)) from exc


def _bundle_has_p3b_v7_state(recovery_root: Path, publication_date: str) -> bool:
    marker_name = f"{_P3B_V7_PREFIX}{publication_date}.json"
    return any(path.is_file() for path in Path(recovery_root).rglob(marker_name))


def _restore_p3b_v7_state(
    *,
    recovery_root: Path,
    report_path: Path,
    publication_date: str,
) -> dict[str, Any]:
    """Restore v7 marker/forensic backups only from the selected evidence bundle."""
    evidence_root = getattr(_base, "_ACTIVE_EVIDENCE_ROOT", None)
    if evidence_root is None:
        if _bundle_has_p3b_v7_state(recovery_root, publication_date):
            raise RecoveryError(
                "P3b v7 recovery marker exists but selected artifact bundle identity is unavailable"
            )
        return {
            "status": "not_present",
            "publication_date": publication_date,
            "copied": [],
        }

    evidence_root = Path(evidence_root)
    source_state = _p3b_v7_state_dir(evidence_root)
    source_marker = _p3b_v7_marker_path(evidence_root, publication_date)
    if not source_marker.is_file():
        return {
            "status": "not_present",
            "publication_date": publication_date,
            "copied": [],
        }

    marker = _read_json_object(source_marker)
    if marker is None:
        raise RecoveryError("P3b v7 recovery marker is unreadable")
    if str(marker.get("publication_date") or "") != publication_date:
        raise RecoveryError("P3b v7 recovery marker publication date mismatch")
    state = str(marker.get("state") or "")
    if state not in {"pending", "blocked", "completed"}:
        raise RecoveryError(f"P3b v7 recovery marker has invalid state: {state!r}")

    target_state = Path(report_path).parent.resolve()
    target_state.mkdir(parents=True, exist_ok=True)
    marker_name = source_marker.name
    names = [marker_name]
    stem = source_marker.stem
    names.extend(
        f"{stem}.{kind}.original.json" for kind in _P3B_V7_BACKUP_KINDS
    )

    copied: list[str] = []
    for name in names:
        source = source_state / name
        if not source.is_file():
            continue
        target = target_state / name
        source_bytes = source.read_bytes()
        if target.is_file():
            if target.read_bytes() != source_bytes:
                raise RecoveryError(
                    f"P3b v7 recovery state conflicts with selected artifact bundle: {name}"
                )
            continue
        shutil.copy2(source, target)
        copied.append(str(target))

    return {
        "status": "restored" if copied else "already_present",
        "publication_date": publication_date,
        "marker_state": state,
        "publication_snapshot_invalidated": marker.get(
            "publication_snapshot_invalidated"
        ),
        "copied": copied,
    }


def recover(
    recovery_root: Path,
    target_dir: Path,
    publication_date: str,
    report_path: Path,
    timezone_name: str = "Europe/Moscow",
    image_target_dir: Path | None = None,
) -> dict[str, Any]:
    _sync_public_hooks()
    original_choose = _base.choose_source
    _base.choose_source = choose_source
    try:
        report = _P0_RECOVER(
            recovery_root,
            target_dir,
            publication_date,
            report_path,
            timezone_name,
            image_target_dir,
        )
    finally:
        _base.choose_source = original_choose
        _pull_runtime_state()
    report["coverage_optional_slot_recovery"] = _restore_optional_slot(
        recovery_root=recovery_root,
        report_path=report_path,
        publication_date=publication_date,
    )
    report["p3b_v7_recovery"] = _restore_p3b_v7_state(
        recovery_root=recovery_root,
        report_path=report_path,
        publication_date=publication_date,
    )
    write_json(report_path, report)
    return report


def main() -> int:
    _sync_public_hooks()
    original = _base.recover
    _base.recover = recover
    try:
        return int(_P0_MAIN())
    finally:
        _base.recover = original
        _pull_runtime_state()


if __name__ == "__main__":
    raise SystemExit(main())
