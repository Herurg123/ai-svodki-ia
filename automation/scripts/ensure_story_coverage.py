#!/usr/bin/env python3
"""Stable public compatibility surface for hardened Coverage P3b.

The active runtime guard lives in ``ensure_story_coverage_p3b_v4.py``; v3 keeps
historical compatibility seams, v2 contains the substantive Astra exact-binding
repairs, v1 is retained for forensic comparison, and ``ensure_story_coverage_p3a.py``
preserves the exact pre-P3b behavior. Direct imports and the CLI now enter the
same hardened execute path. The ordinary Coverage text client still inherits the
preserved ``max_retries=2`` policy; protected optional-slot retry semantics remain
isolated in the dedicated slot transport module.
"""
from __future__ import annotations

import functools
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

_IMPL_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v4.py")
_IMPL_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p3b_v4", _IMPL_PATH)
assert _IMPL_SPEC and _IMPL_SPEC.loader
_impl = importlib.util.module_from_spec(_IMPL_SPEC)
sys.modules[_IMPL_SPEC.name] = _impl
_IMPL_SPEC.loader.exec_module(_impl)

_ORIGINAL_EXPORTS: dict[str, Any] = {
    name: getattr(_impl, name)
    for name in dir(_impl)
    if not (name.startswith("__") and name.endswith("__"))
}
_RUNTIME_PULL_NAMES = ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE")
_IDENTITY_EXPORTS = frozenset({"completed_prior_audit"})
_SHIM_INTERNALS = frozenset(
    {
        "_impl", "_IMPL_PATH", "_IMPL_SPEC", "_ORIGINAL_EXPORTS",
        "_RUNTIME_PULL_NAMES", "_IDENTITY_EXPORTS", "_SHIM_INTERNALS",
        "_sync_to_impl", "_pull_impl_runtime_state", "_make_proxy",
    }
)


def _sync_to_impl() -> None:
    current = globals()
    for name, value in list(current.items()):
        if name in _SHIM_INTERNALS or (name.startswith("__") and name.endswith("__")):
            continue
        try:
            exists = hasattr(_impl, name)
        except Exception:
            exists = False
        if not exists:
            continue
        original = _ORIGINAL_EXPORTS.get(name)
        if original is not None and getattr(value, "_coverage_public_proxy_target", None) == name:
            setattr(_impl, name, original)
        else:
            setattr(_impl, name, value)
    sync = getattr(_impl, "_sync_p3b_public_hooks", None)
    if callable(sync):
        sync()


def _pull_impl_runtime_state() -> None:
    for name in _RUNTIME_PULL_NAMES:
        if hasattr(_impl, name):
            globals()[name] = getattr(_impl, name)


def _make_proxy(name: str):
    original = _ORIGINAL_EXPORTS[name]

    @functools.wraps(original)
    def proxy(*args: Any, **kwargs: Any) -> Any:
        _sync_to_impl()
        try:
            return getattr(_impl, name)(*args, **kwargs)
        finally:
            _pull_impl_runtime_state()

    proxy._coverage_public_proxy_target = name  # type: ignore[attr-defined]
    return proxy


for _name, _value in _ORIGINAL_EXPORTS.items():
    if inspect.isfunction(_value) and _name not in _IDENTITY_EXPORTS:
        globals()[_name] = _make_proxy(_name)
    else:
        globals()[_name] = _value


def __getattr__(name: str) -> Any:
    return getattr(_impl, name)


if __name__ == "__main__":
    raise SystemExit(main())
