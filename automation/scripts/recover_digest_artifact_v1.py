#!/usr/bin/env python3
"""Stable recovery v1 surface with bounded stale-validator revalidation.

The established implementation remains byte-for-byte in
``recover_digest_artifact_v1_base.py``. This compatibility layer changes only
saved-stage decisions for validator errors made obsolete by current deterministic
contracts: the pre-#145 ``ambiguous_story_mapping`` error and the Sep-9
``story_headline_order`` false positive caused solely by the required public
``Meta*`` display marker. These artifacts may be restored so current validators
can re-check them. Every non-revalidatable saved normalization/validation error
remains fail-closed.

Consolidate this layer on the next material recovery refactor or after
2026-10-03, after replaying the Sep-3 shared-source and Sep-9 Meta-headline
recovery regressions.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_BASE_PATH = Path(__file__).with_name("recover_digest_artifact_v1_base.py")
_BASE_SPEC = importlib.util.spec_from_file_location(
    "recover_digest_artifact_v1_base", _BASE_PATH
)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)


def __getattr__(name: str) -> Any:
    return getattr(_base, name)


REVALIDATABLE_ARTIFACT_VALIDATION_CODES = frozenset(
    {"ambiguous_story_mapping", "story_headline_order"}
)


def _saved_stage_reports_are_reusable(source_dir: Path) -> tuple[bool, str | None]:
    """Allow only saved validator errors that current code can safely re-check."""

    normalization_path = source_dir / "artifact-normalization.json"
    if normalization_path.is_file():
        payload = _base.read_json(normalization_path)
        if not isinstance(payload, dict):
            return False, "artifact-normalization.json должен содержать объект"
        if payload.get("status") == "error":
            detail = payload.get("error") or payload.get("errors") or "status=error"
            return False, f"artifact-normalization.json уже сообщил ошибку: {detail}"

    validation_path = source_dir / "artifact-validation.json"
    if validation_path.is_file():
        payload = _base.read_json(validation_path)
        if not isinstance(payload, dict):
            return False, "artifact-validation.json должен содержать объект"
        if payload.get("status") == "error":
            errors = payload.get("errors")
            codes = (
                {
                    str(item.get("code") or "")
                    for item in errors
                    if isinstance(item, dict)
                    and str(item.get("code") or "").strip()
                }
                if isinstance(errors, list)
                else set()
            )
            if not codes or not codes.issubset(REVALIDATABLE_ARTIFACT_VALIDATION_CODES):
                detail = payload.get("error") or errors or "status=error"
                return False, f"artifact-validation.json уже сообщил ошибку: {detail}"

    return True, None


_base._saved_stage_reports_are_reusable = _saved_stage_reports_are_reusable


def main() -> int:
    _base._saved_stage_reports_are_reusable = _saved_stage_reports_are_reusable
    return int(_base.main())


if __name__ == "__main__":
    raise SystemExit(main())
