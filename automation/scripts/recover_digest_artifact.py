#!/usr/bin/env python3
"""Coverage optional-slot recovery over the preserved P0 recovery wrapper.

``recover_digest_artifact_p0.py`` is the byte-for-byte pre-slot implementation.
This layer preserves its public monkeypatch/recovery surface and adds one rule:
optional seventh-slot journal/response state may be restored only from the exact
artifact bundle already selected by P0 recovery.
"""
from __future__ import annotations

import importlib.util
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

_DELEGATE_EXCLUSIONS = {
    "main",
    "recover",
    "choose_source",
    "_restore_optional_slot",
    "_sync_public_hooks",
    "_pull_runtime_state",
    "_ACTIVE_EVIDENCE_ROOT",
    "restore_coverage_slot_state_from_bundle",
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


def choose_source(
    recovery_root: Path,
    publication_date: str,
) -> tuple[Path, str, list[dict[str, Any]]]:
    _sync_public_hooks()
    try:
        return _P0_CHOOSE_SOURCE(recovery_root, publication_date)
    finally:
        _pull_runtime_state()


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
