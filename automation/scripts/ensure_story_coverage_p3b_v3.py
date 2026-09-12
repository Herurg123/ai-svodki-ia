#!/usr/bin/env python3
"""P3b v3 compatibility wrapper over the hardened v2 runtime.

v2 contains the substantive Astra fixes. v3 repairs the historical public/private
Coverage import and monkeypatch surface without weakening those fixes. It also
keeps the preserved v1 binder isolated so old compatibility helpers cannot be
silently reinterpreted by the hardened v2 binder.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import weak_source_exact_binding_v2 as _binding_v2

_V2_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v2.py")
_V2_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p3b_v2_active", _V2_PATH)
assert _V2_SPEC and _V2_SPEC.loader
_v2 = importlib.util.module_from_spec(_V2_SPEC)
sys.modules[_V2_SPEC.name] = _v2
_V2_SPEC.loader.exec_module(_v2)

# Preserve the exact v1 binder surface before restoring the hardened v2 symbols.
# Historical helper tests and callers may still exercise v1 directly, but the
# active orchestration below never uses those weaker semantics.
_V1_BINDER_EXPORTS = {
    "build_p3b_query": _v2._v1.build_p3b_query,
    "candidate_exact_binding": _v2._v1.candidate_exact_binding,
    "qualifying_p3b_signals": _v2._v1.qualifying_p3b_signals,
    "select_p3b_signal": _v2._v1.select_p3b_signal,
}

# v2 deliberately re-exported the whole v1 module before defining its hardened
# runtime. Restore the active binder explicitly before any hardened call.
_v2.build_p3b_query = _binding_v2.build_query
_v2.candidate_exact_binding = _binding_v2.candidate_exact_binding
_v2.qualifying_p3b_signals = _binding_v2.qualifying_signals
_v2.select_p3b_signal = _binding_v2.select_signal
_v2.P3B_EXACT_BINDING_VERSION = _binding_v2.VERSION
_v2.P3B_MODE = _binding_v2.MODE

# Preserve the real hardened entrypoints before this wrapper exports its own.
# They must never be overwritten by compatibility-state synchronization.
_V2_EXECUTE_AUDIT_PLAN = _v2.execute_audit_plan
_V2_MAIN = _v2.main


def _v2_lazy_getattr(name: str) -> Any:
    return getattr(_v2._v1, name)


_v2.__getattr__ = _v2_lazy_getattr

for _name in dir(_v2):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_v2, _name)

_COMPAT_INTERNALS = {
    "_v2", "_V2_PATH", "_V2_SPEC", "_binding_v2", "_v2_lazy_getattr",
    "_V1_BINDER_EXPORTS", "_V2_EXECUTE_AUDIT_PLAN", "_V2_MAIN",
    "_COMPAT_INTERNALS", "_sync_p3b_public_hooks", "_pull_p3b_runtime_state",
    "execute_audit_plan", "main", "__getattr__",
}


def __getattr__(name: str) -> Any:
    return getattr(_v2, name)


def _restore_active_binders() -> None:
    _v2.build_p3b_query = _binding_v2.build_query
    _v2.candidate_exact_binding = _binding_v2.candidate_exact_binding
    _v2.qualifying_p3b_signals = _binding_v2.qualifying_signals
    _v2.select_p3b_signal = _binding_v2.select_signal
    for name, value in _V1_BINDER_EXPORTS.items():
        setattr(_v2._v1, name, value)


def _sync_p3b_public_hooks() -> None:
    """Push monkeypatchable state while keeping v1/v2 binder semantics separate."""
    for name, value in list(globals().items()):
        if name in _COMPAT_INTERNALS or (name.startswith("__") and name.endswith("__")):
            continue
        try:
            exists = hasattr(_v2, name)
        except Exception:
            exists = False
        if exists:
            setattr(_v2, name, value)
    _restore_active_binders()
    _v2._sync_p3b_public_hooks()
    # v2's generic compatibility sync intentionally mirrors most names into v1;
    # restore the binder boundary immediately afterwards.
    _restore_active_binders()


def _pull_p3b_runtime_state() -> None:
    _v2._pull_p3b_runtime_state()
    for name in ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE"):
        if hasattr(_v2, name):
            globals()[name] = getattr(_v2, name)


def execute_audit_plan(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    try:
        return _V2_EXECUTE_AUDIT_PLAN(*args, **kwargs)
    finally:
        _pull_p3b_runtime_state()


def main() -> int:
    _sync_p3b_public_hooks()
    try:
        return int(_V2_MAIN())
    finally:
        _pull_p3b_runtime_state()


if __name__ == "__main__":
    raise SystemExit(main())
