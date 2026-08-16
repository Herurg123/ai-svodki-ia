#!/usr/bin/env python3
"""Retrieval-quality-aware wrapper over the stable artifact recovery engine.

Modern paid research remains reusable, but a full artifact created before the
current retrieval-quality contract is downgraded to partial editorial recovery.
This makes production run Coverage again, where the six already-paid mandatory
passes can be reused and only the missing quality-resolution slot is executed.
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


def recover(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _sync_base()
    return _BASE_RECOVER(*args, **kwargs)


def main() -> int:
    _sync_base()
    return int(_base.main())


if __name__ == "__main__":
    raise SystemExit(main())
