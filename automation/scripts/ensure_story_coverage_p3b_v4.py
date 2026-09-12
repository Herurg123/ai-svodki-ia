#!/usr/bin/env python3
"""P3b v4 runtime guard for hardened CLI and reserved-slot recovery semantics.

The substantive exact-page binding remains in v2 and compatibility bridging in
v3. This narrow layer fixes two orchestration boundaries: a merely reserved slot
must not override a runtime budget already exhausted by other Coverage work, and
the CLI main path must execute the same hardened P3b entrypoint as direct callers.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

_V3_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v3.py")
_V3_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p3b_v3_active", _V3_PATH)
assert _V3_SPEC and _V3_SPEC.loader
_v3 = importlib.util.module_from_spec(_V3_SPEC)
sys.modules[_V3_SPEC.name] = _v3
_V3_SPEC.loader.exec_module(_v3)
_v2 = _v3._v2

for _name in dir(_v3):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_v3, _name)

_V2_RUN_P3B_BINDING = _v2._run_p3b_binding_v2
_V4_INTERNALS = {
    "_v3", "_v2", "_V3_PATH", "_V3_SPEC", "_V2_RUN_P3B_BINDING",
    "_V4_INTERNALS", "_sync_p3b_public_hooks", "_pull_p3b_runtime_state",
    "_guarded_run_p3b_binding_v2", "execute_audit_plan", "main", "__getattr__",
}


def __getattr__(name: str) -> Any:
    return getattr(_v3, name)


def _sync_p3b_public_hooks() -> None:
    # STATE_DIR is part of the historical monkeypatch surface and is security-
    # relevant for the durable optional-slot journal. Keep one exact value across
    # every wrapper layer instead of relying on generic alias propagation.
    state_dir = globals().get("STATE_DIR")
    for name, value in list(globals().items()):
        if name in _V4_INTERNALS or (name.startswith("__") and name.endswith("__")):
            continue
        try:
            exists = hasattr(_v3, name)
        except Exception:
            exists = False
        if exists:
            setattr(_v3, name, value)
    if state_dir is not None:
        _v3.STATE_DIR = state_dir
        _v2.STATE_DIR = state_dir
    _v3._sync_p3b_public_hooks()
    if state_dir is not None:
        # v3/v2 compatibility sync may mirror older aliases back down. Reassert
        # the runtime journal root after that generic pass so recovery observes
        # the exact same durable slot that public callers patched.
        _v3.STATE_DIR = state_dir
        _v2.STATE_DIR = state_dir
        if hasattr(_v2, "_v1"):
            _v2._v1.STATE_DIR = state_dir
    # Keep the reserved-budget guard installed after generic compatibility sync.
    _v2._run_p3b_binding_v2 = _guarded_run_p3b_binding_v2


def _pull_p3b_runtime_state() -> None:
    _v3._pull_p3b_runtime_state()
    for name in ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE"):
        if hasattr(_v3, name):
            globals()[name] = getattr(_v3, name)


def _guarded_run_p3b_binding_v2(*, plan: dict[str, Any], publication_date: str,
                                signal: dict[str, Any], api_key: str, model: str,
                                search_window: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    """Never turn an unspent reservation into an eighth/over-budget wire call."""
    try:
        journal = load_journal(Path(STATE_DIR), publication_date)
    except CoverageSlotError:
        journal = None
    state = str((journal or {}).get("state") or "") if isinstance(journal, dict) else ""
    if state == "reserved":
        budget = plan.get("search_budget")
        remaining = int(budget.get("remaining_calls", 0) or 0) if isinstance(budget, dict) else 0
        if remaining < 1:
            return _v2._annotation(
                plan,
                status="deferred",
                reason="reserved optional slot cannot override exhausted runtime Coverage budget",
                signal=signal,
                query=build_p3b_query(signal),
                disposition="unresolved_deferred",
                slot_state="reserved",
            )
    return _V2_RUN_P3B_BINDING(
        plan=plan,
        publication_date=publication_date,
        signal=signal,
        api_key=api_key,
        model=model,
        search_window=search_window,
        archive=archive,
    )


def execute_audit_plan(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    try:
        return _v3.execute_audit_plan(*args, **kwargs)
    finally:
        _pull_p3b_runtime_state()


def main() -> int:
    """Run the historical CLI shell with the hardened execute entrypoint installed."""
    # Capture the historical CLI callback before generic compatibility sync. That
    # preserves the long-standing monkeypatch seam and prevents an exported stale
    # alias from silently replacing a caller/test override.
    historical_main = _v2._v1._P3A_MAIN
    _sync_p3b_public_hooks()
    original_execute = _v2._v1._pre.execute_audit_plan
    _v2._v1._pre.execute_audit_plan = execute_audit_plan
    try:
        return int(historical_main())
    finally:
        _v2._v1._pre.execute_audit_plan = original_execute
        _pull_p3b_runtime_state()


# Install the guard for direct calls that enter through v3/v2 globals.
_v2._run_p3b_binding_v2 = _guarded_run_p3b_binding_v2


if __name__ == "__main__":
    raise SystemExit(main())
