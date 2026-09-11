#!/usr/bin/env python3
"""P0 publication guard layered over the established artifact validator.

The pre-P0 validator is retained verbatim in
``validate_digest_artifact_pre_p0.py``. After all established artifact checks
pass, this wrapper refuses publication while Mandatory Coverage still has an
unapplied editorial repair/completion obligation. A saved repair response is
marked applied only when it exactly matches the current raw editorial artifact.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from editorial_repair_journal import (
    EditorialRepairJournalError,
    assert_publication_safe,
)

_PRE_PATH = Path(__file__).with_name("validate_digest_artifact_pre_p0.py")
_PRE_SPEC = importlib.util.spec_from_file_location(
    "validate_digest_artifact_pre_p0", _PRE_PATH
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


def _arg_value(flag: str) -> str | None:
    for index, value in enumerate(sys.argv):
        if value == flag and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        prefix = flag + "="
        if value.startswith(prefix):
            return value[len(prefix):]
    return None


def _record_guard_failure(report_path: Path | None, error: Exception) -> None:
    if report_path is None:
        return
    try:
        payload: dict[str, Any] = {}
        if report_path.is_file():
            loaded = json.loads(report_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        payload["status"] = "error"
        payload["editorial_repair_guard"] = {
            "status": "error",
            "error_type": type(error).__name__,
            "error": str(error),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        # Validation already failed. A diagnostics write must never convert that
        # failure into publication permission.
        pass


def main() -> int:
    result = int(_pre.main())
    if result != 0:
        return result

    artifact_value = _arg_value("--artifact-dir")
    if not artifact_value:
        # The established parser owns the CLI contract; reaching this point
        # without artifact-dir would already have failed there.
        return result
    report_value = _arg_value("--report")
    report_path = Path(report_value).resolve() if report_value else None
    try:
        assert_publication_safe(Path(artifact_value))
    except EditorialRepairJournalError as exc:
        _record_guard_failure(report_path, exc)
        print(f"Digest artifact validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
