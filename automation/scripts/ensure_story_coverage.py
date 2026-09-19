#!/usr/bin/env python3
"""Stable public compatibility surface for hardened Coverage P3b.

The active runtime guard lives in ``ensure_story_coverage_p3b_v7.py``; v7 adds a
production recovery preflight over preserved v6 semantics, v6 owns current binder
and optional-slot recovery hardening, v5 keeps prior orchestration hardening,
v4/v3 keep historical compatibility seams, v2 preserves the first substantive
Astra exact-binding repairs, v1 is retained for forensic comparison, and
``ensure_story_coverage_p3a.py`` preserves the exact pre-P3b behavior. Direct
imports and the CLI enter the same hardened execute path. The ordinary Coverage
text client still inherits the preserved ``max_retries=2`` policy; protected
optional-slot retry semantics remain isolated in the dedicated slot transport
module.
"""
from __future__ import annotations

import functools
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

_IMPL_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v7.py")
_IMPL_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p3b_v7", _IMPL_PATH)
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
_COMPAT_HOOK_NAMES = (
    "run_audit_request",
    "protected_policy_audit_request",
    "_p3b_signals",
    "STATE_DIR",
)
_SHIM_INTERNALS = frozenset(
    {
        "_impl", "_IMPL_PATH", "_IMPL_SPEC", "_ORIGINAL_EXPORTS",
        "_RUNTIME_PULL_NAMES", "_IDENTITY_EXPORTS", "_COMPAT_HOOK_NAMES",
        "_SHIM_INTERNALS", "_iter_compat_targets", "_iter_compat_namespaces",
        "_propagate_compat_hooks", "_sync_to_impl", "_pull_impl_runtime_state",
        "_make_proxy", "_run_public_main", "main",
    }
)


def _iter_compat_targets() -> list[Any]:
    """Return the active compatibility owners from v7 down to the v8 runtime."""
    targets: list[Any] = []
    seen: set[int] = set()

    def add(value: Any) -> Any:
        if value is None or id(value) in seen:
            return value
        seen.add(id(value))
        targets.append(value)
        return value

    add(_impl)
    add(getattr(_impl, "_v6", None))
    add(getattr(_impl, "_v5", None))
    add(getattr(_impl, "_v3", None))
    v2 = add(getattr(_impl, "_v2", None))
    v1 = add(getattr(v2, "_v1", None)) if v2 is not None else None
    p3a = add(getattr(v1, "_p3a", None)) if v1 is not None else None
    p0 = add(getattr(p3a, "_base", None)) if p3a is not None else None
    quality = add(getattr(p0, "_pre", None)) if p0 is not None else None
    v8 = add(getattr(quality, "_v8", None)) if quality is not None else None
    add(getattr(v8, "_base", None)) if v8 is not None else None
    return targets


def _iter_compat_namespaces() -> list[dict[str, Any]]:
    """Return module and preserved-function global namespaces that can execute.

    Versioned compatibility layers intentionally keep aliases to function objects
    created by separately loaded modules. Those aliases can execute with a
    ``__globals__`` mapping that is not the ``__dict__`` of the module object we
    can reach through the active wrapper chain. Public monkeypatches therefore
    have to follow function ownership, not merely module identity.
    """
    namespaces: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add(namespace: Any) -> None:
        if not isinstance(namespace, dict) or id(namespace) in seen:
            return
        seen.add(id(namespace))
        namespaces.append(namespace)

    for target in _iter_compat_targets():
        namespace = getattr(target, "__dict__", None)
        add(namespace)
        if not isinstance(namespace, dict):
            continue
        for value in tuple(namespace.values()):
            if inspect.isfunction(value):
                add(getattr(value, "__globals__", None))
    return namespaces


def _propagate_compat_hooks() -> None:
    """Push only sanctioned late monkeypatch seams to real execution owners.

    Binder/policy semantics are deliberately excluded. Each allowed hook is
    written only into namespaces that already define that name, including the
    ``__globals__`` of preserved function aliases. This keeps compatibility
    monkeypatches functional without creating new mutable API surface.
    """
    namespaces = _iter_compat_namespaces()
    for name in _COMPAT_HOOK_NAMES:
        try:
            value = getattr(_impl, name)
        except Exception:
            continue
        for namespace in namespaces:
            if name in namespace:
                namespace[name] = value


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
        if (
            original is not None
            and inspect.isfunction(value)
            and getattr(value, "_coverage_public_proxy_target", None) == name
        ):
            setattr(_impl, name, original)
        else:
            setattr(_impl, name, value)
    sync = getattr(_impl, "_sync_p3b_public_hooks", None)
    if callable(sync):
        sync()
    _propagate_compat_hooks()


def _pull_impl_runtime_state() -> None:
    """Pull late runtime diagnostics from the preserved execution owner into v7."""
    preserved = getattr(_impl, "_v6", None)
    pull = getattr(preserved, "_pull_p3b_runtime_state", None)
    if callable(pull):
        pull()
    for name in _RUNTIME_PULL_NAMES:
        if preserved is not None and hasattr(preserved, name):
            value = getattr(preserved, name)
            setattr(_impl, name, value)
            globals()[name] = value
        elif hasattr(_impl, name):
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


def _run_public_main() -> int:
    """Run the v7 pre/postflight while installing the active v7 execute hook."""
    _sync_to_impl()
    publication_date = str(_impl._cli_arg("--publication-date") or "").strip()
    artifact_raw = _impl._cli_arg("--artifact-dir")
    report_raw = _impl._cli_arg("--report")

    artifact_dir: Path | None = None
    report_path: Path | None = None
    context: dict[str, Any] | None = None
    if publication_date and artifact_raw and report_raw:
        artifact_dir = Path(artifact_raw)
        report_path = Path(report_raw)
        context = _impl.recovery_preflight(
            publication_date=publication_date,
            artifact_dir=artifact_dir,
            report_path=report_path,
            state_dir=Path(_impl.STATE_DIR),
        )

    historical_main = _impl._v2._v1._P3A_MAIN
    original_execute = _impl._v2._v1._pre.execute_audit_plan
    _impl._v2._v1._pre.execute_audit_plan = _impl.execute_audit_plan
    try:
        child_code = int(historical_main())
    finally:
        _impl._v2._v1._pre.execute_audit_plan = original_execute
        _pull_impl_runtime_state()

    if artifact_dir is None or report_path is None:
        # Historical argparse/main remains the owner of malformed CLI behavior.
        return child_code
    return int(
        _impl._postflight(
            context,
            child_code=child_code,
            artifact_dir=artifact_dir,
            report_path=report_path,
        )
    )


main = _run_public_main


def __getattr__(name: str) -> Any:
    return getattr(_impl, name)


if __name__ == "__main__":
    raise SystemExit(main())
