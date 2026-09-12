#!/usr/bin/env python3
"""Coverage optional-slot recovery over the preserved P0 recovery wrapper.

``recover_digest_artifact_p0.py`` is the byte-for-byte pre-slot implementation.
This layer restores only the durable Coverage optional-slot journal/response and
binds them to the exact artifact bundle already selected by P0 recovery.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from coverage_slot_guard import CoverageSlotError, JOURNAL_PREFIX, restore_state_from_bundle


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


_BASE_RECOVER = _base.recover


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
        return restore_state_from_bundle(
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
    report = _BASE_RECOVER(
        recovery_root,
        target_dir,
        publication_date,
        report_path,
        timezone_name,
        image_target_dir,
    )
    report["coverage_optional_slot_recovery"] = _restore_optional_slot(
        recovery_root=recovery_root,
        report_path=report_path,
        publication_date=publication_date,
    )
    write_json(report_path, report)
    return report


def main() -> int:
    original = _base.recover
    _base.recover = recover
    try:
        return int(_base.main())
    finally:
        _base.recover = original


if __name__ == "__main__":
    raise SystemExit(main())
