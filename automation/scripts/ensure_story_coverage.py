#!/usr/bin/env python3
"""Durable optional-slot guard over the preserved P0 Coverage wrapper.

``ensure_story_coverage_p0.py`` is the byte-for-byte pre-guard public wrapper.
This layer changes only the already-existing optional seventh Coverage search:
its owner/request state is persisted before transport so recovery cannot refund
an admitted or ambiguous request. All historical public hooks remain bridged
through the preserved P0 wrapper; semantic matching is intentionally unchanged.
"""
from __future__ import annotations

import contextvars
import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

from coverage_slot_guard import (
    CoverageSlotReservation,
    activate_slot,
    prepare_slot,
    sha256_value,
    slot_is_consumed_or_ambiguous,
)
from coverage_slot_transport import protected_policy_audit_request, replay_result_snapshot

_BASE_PATH = Path(__file__).with_name("ensure_story_coverage_p0.py")
_BASE_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p0", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)


def __getattr__(name: str) -> Any:
    return getattr(_base, name)


_pre = _base._pre
_runtime = _pre._runtime
_policy = _pre._policy
_PRE_RUN_RESOLUTION = _pre._run_resolution
_P0_EXECUTE_AUDIT_PLAN = _base.execute_audit_plan
_P0_PREPARE_PRIOR_FOR_QUALITY = _base._prepare_prior_for_quality
_P0_PRIMARY_SEARCH_DIAGNOSTICS = _base._primary_search_diagnostics
_P0_FINALIZE_QUALITY_REPORT = _base._finalize_quality_report
_P0_MAIN = _base.main

# Materialize the historical private/public compatibility hooks. Tests and
# downstream wrappers monkeypatch these on the public module and expect P0 to
# carry them all the way into v8/runtime.
_BASE_EXECUTE_AUDIT_PLAN = getattr(_base, "_BASE_EXECUTE_AUDIT_PLAN", None)
_LAST_RECALL_SENTINEL = getattr(_base, "_LAST_RECALL_SENTINEL", None)
_LAST_AGENCY_RESCUE = getattr(_base, "_LAST_AGENCY_RESCUE", None)
REPOSITORY_ROOT = _base.REPOSITORY_ROOT
STATE_DIR = _base.STATE_DIR
OPTIONAL_SLOT_OWNER = _pre.UNRESOLVED_RESOLUTION_STRATEGY
OPTIONAL_SLOT_VERSION = 1
_CURRENT_PUBLICATION_DATE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "coverage_publication_date", default=None
)

# Ordinary Coverage transport in the preserved runtime remains
# OpenAI(..., max_retries=2). Only the protected optional-slot transport uses 0.
# max_retries=2

_DELEGATE_EXCLUSIONS = {
    "main",
    "execute_audit_plan",
    "_prepare_prior_for_quality",
    "_primary_search_diagnostics",
    "_finalize_quality_report",
    "_run_resolution",
    "_sync_public_hooks",
    "_sync_slot_hooks",
    "_pull_runtime_state",
    "_LAST_RECALL_SENTINEL",
    "_LAST_AGENCY_RESCUE",
}


def _publication_date(plan: dict[str, Any] | None = None) -> str:
    if isinstance(plan, dict):
        value = str(plan.get("publication_date") or "").strip()
        if value:
            return value
    return str(_CURRENT_PUBLICATION_DATE.get() or "").strip()


def _sync_public_hooks() -> None:
    """Preserve the exact P0 monkeypatch surface before installing slot hooks."""
    current = globals()
    for name, value in list(current.items()):
        if name.startswith("__") and name.endswith("__"):
            continue
        if name in _DELEGATE_EXCLUSIONS or name.startswith("_P0_"):
            continue
        if name in _base.__dict__:
            setattr(_base, name, value)
    _base._sync_p0()


def _sync_slot_hooks() -> None:
    _sync_public_hooks()
    _pre._run_resolution = _run_resolution
    _pre._prepare_prior_for_quality = _prepare_prior_for_quality


def _pull_runtime_state() -> None:
    for name in ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE"):
        if name in _base.__dict__:
            globals()[name] = getattr(_base, name)
        elif name in _pre.__dict__:
            globals()[name] = getattr(_pre, name)


def _request_contract(
    *,
    model: str,
    query: str,
    prompt: str,
    cluster: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "version": OPTIONAL_SLOT_VERSION,
        "strategy": OPTIONAL_SLOT_OWNER,
        "model": model,
        "query": query,
        "prompt_sha256": sha256_value(prompt),
        "signal_ids": [str(item.get("signal_id") or "") for item in cluster],
        "maximum_web_search_calls": 1,
        "allowed_domains": list(_pre.UNRESOLVED_RESOLUTION_DOMAINS),
    }


def _bundle_identity(plan: dict[str, Any]) -> dict[str, Any]:
    mandatory = [
        {
            "direction_id": item.get("direction_id"),
            "attempt": item.get("attempt"),
            "status": item.get("status"),
            "response_id": (item.get("api") or {}).get("response_id")
            if isinstance(item.get("api"), dict)
            else None,
        }
        for item in plan.get("attempts", [])
        if isinstance(item, dict) and item.get("direction_id") in _pre.AUDIT_DIRECTION_IDS
    ]
    return {
        "publication_date": _publication_date(plan),
        "checked_directions": list(plan.get("checked_directions") or []),
        "mandatory_attempts": mandatory,
    }


def _legacy_slot_attempt(attempts: Any) -> dict[str, Any] | None:
    if not isinstance(attempts, list):
        return None
    matches = [
        item
        for item in attempts
        if isinstance(item, dict) and item.get("search_strategy") == OPTIONAL_SLOT_OWNER
    ]
    return copy.deepcopy(matches[-1]) if matches else None


def _force_slot_consumed_budget(plan: dict[str, Any]) -> None:
    budget = plan.get("search_budget")
    if not isinstance(budget, dict):
        return
    configured = int(budget.get("maximum_calls", 7) or 7)
    hard_maximum = int(getattr(_pre, "DEFAULT_MAXIMUM_AUDIT_CALLS", 7) or 7)
    maximum = min(configured, hard_maximum)
    completed = int(budget.get("completed_calls", 0) or 0)
    effective = max(completed, min(maximum, len(_pre.AUDIT_DIRECTION_IDS) + 1))
    budget["maximum_calls"] = maximum
    budget["reserved_or_spent_calls"] = max(0, effective - completed)
    budget["effective_consumed_calls"] = effective
    budget["remaining_calls"] = max(0, maximum - effective)
    budget["exhausted"] = effective >= maximum
    budget["search_budget_exhausted"] = effective >= maximum
    if effective >= maximum and plan.get("audit_state") != "completed_usable":
        budget["stop_reason"] = "coverage_optional_slot_consumed_or_ambiguous"


def _append_slot_attempt_if_missing(
    plan: dict[str, Any],
    *,
    reservation: CoverageSlotReservation,
    cluster: list[dict[str, Any]],
    query: str,
) -> None:
    attempts = plan.setdefault("attempts", [])
    current = next(
        (
            item
            for item in reversed(attempts)
            if isinstance(item, dict) and item.get("search_strategy") == OPTIONAL_SLOT_OWNER
        ),
        None,
    )
    journal = reservation.journal
    if current is None:
        snapshot = reservation.result_snapshot() or {}
        metadata = snapshot.get("metadata") if isinstance(snapshot, dict) else None
        attempts.append(
            {
                "direction_id": "general_coverage_gaps",
                "label": "Unresolved high-signal resolution v1",
                "required": True,
                "attempt": 1
                + max(
                    [
                        int(item.get("attempt", 0) or 0)
                        for item in attempts
                        if isinstance(item, dict)
                        and item.get("direction_id") == "general_coverage_gaps"
                    ]
                    or [0]
                ),
                "search_strategy": OPTIONAL_SLOT_OWNER,
                "unresolved_resolution_version": _pre.UNRESOLVED_RESOLUTION_VERSION,
                "allowed_domains": [],
                "signal_ids": [str(item.get("signal_id") or "") for item in cluster],
                "required_query": query,
                "status": "indeterminate"
                if journal.get("state") == "request_started"
                else "checked_with_gaps",
                "outcome": "transport_indeterminate"
                if journal.get("state") == "request_started"
                else "response_unusable",
                "resolution_disposition": "unresolved",
                "candidate_count": 0,
                "candidates": [],
                "rejections": [],
                "api": copy.deepcopy(metadata)
                if isinstance(metadata, dict)
                else {
                    "status": "indeterminate",
                    "web_search_calls_completed": 0,
                    "web_search_call_items_total": 0,
                },
                "error": (
                    "optional Coverage slot request outcome is unknown"
                    if journal.get("state") == "request_started"
                    else "optional Coverage slot response could not produce usable resolution"
                ),
                "slot_state": journal.get("state"),
                "search_operation_count_contribution": 1,
            }
        )
    else:
        current["slot_state"] = journal.get("state")
        current["search_operation_count_contribution"] = 1
    _force_slot_consumed_budget(plan)


def _blocked_quality_plan(
    plan: dict[str, Any],
    *,
    signals: list[dict[str, Any]],
    cluster: list[dict[str, Any]],
    query: str,
    reason: str,
    reservation: CoverageSlotReservation,
) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    result["retrieval_quality_contract_version"] = _pre.RETRIEVAL_QUALITY_CONTRACT_VERSION
    result["retrieval_quality"] = _pre._quality(
        "incomplete", signals, cluster, query=query, reason=reason
    )
    result["audit_status"] = "partial"
    _append_slot_attempt_if_missing(
        result, reservation=reservation, cluster=cluster, query=query
    )
    return result


def _run_resolution(
    *,
    plan: dict[str, Any],
    signals: list[dict[str, Any]],
    api_key: str,
    model: str,
    search_window: dict[str, Any],
    archive: dict[str, Any],
    maximum_web_search_calls: int,
) -> dict[str, Any]:
    publication_date = _publication_date(plan)
    if not publication_date:
        return _PRE_RUN_RESOLUTION(
            plan=plan,
            signals=signals,
            api_key=api_key,
            model=model,
            search_window=search_window,
            archive=archive,
            maximum_web_search_calls=maximum_web_search_calls,
        )

    cluster = _pre.resolution_cluster(signals)
    query = _pre.build_resolution_query(cluster)
    prompt = _pre.build_resolution_prompt(
        search_window=search_window, cluster=cluster, archive=archive
    )
    try:
        reservation = prepare_slot(
            state_dir=Path(STATE_DIR),
            publication_date=publication_date,
            owner=OPTIONAL_SLOT_OWNER,
            search_window=search_window,
            request_contract=_request_contract(
                model=model, query=query, prompt=prompt, cluster=cluster
            ),
            bundle_identity=_bundle_identity(plan),
        )
    except Exception as exc:
        result = copy.deepcopy(plan)
        result["retrieval_quality_contract_version"] = _pre.RETRIEVAL_QUALITY_CONTRACT_VERSION
        result["retrieval_quality"] = _pre._quality(
            "incomplete",
            signals,
            cluster,
            query=query,
            reason=f"optional slot reservation failure: {type(exc).__name__}: {exc}",
        )
        result["audit_status"] = "partial"
        return result

    state = reservation.state
    if state == "request_started":
        return _blocked_quality_plan(
            plan,
            signals=signals,
            cluster=cluster,
            query=query,
            reason="optional slot request previously started with unknown outcome; automatic retry forbidden",
            reservation=reservation,
        )
    if state == "processed":
        saved = reservation.processed_snapshot()
        if isinstance(saved, dict):
            result = copy.deepcopy(saved)
            _force_slot_consumed_budget(result)
            return result
        return _blocked_quality_plan(
            plan,
            signals=signals,
            cluster=cluster,
            query=query,
            reason="processed optional slot is missing its deterministic processed snapshot",
            reservation=reservation,
        )

    original_policy_request = _runtime._policy_audit_request
    try:
        if state == "response_saved":
            snapshot = reservation.result_snapshot()
            if not isinstance(snapshot, dict):
                return _blocked_quality_plan(
                    plan,
                    signals=signals,
                    cluster=cluster,
                    query=query,
                    reason="saved optional-slot response has no parse/result snapshot",
                    reservation=reservation,
                )
            _runtime._policy_audit_request = lambda **_kwargs: replay_result_snapshot(
                _runtime, snapshot
            )
        else:
            _runtime._policy_audit_request = lambda **kwargs: protected_policy_audit_request(
                _runtime, reservation, **kwargs
            )
        with activate_slot(reservation):
            result = _PRE_RUN_RESOLUTION(
                plan=plan,
                signals=signals,
                api_key=api_key,
                model=model,
                search_window=search_window,
                archive=archive,
                maximum_web_search_calls=maximum_web_search_calls,
            )
    finally:
        _runtime._policy_audit_request = original_policy_request

    if reservation.state in {"request_started", "response_saved"}:
        _append_slot_attempt_if_missing(
            result, reservation=reservation, cluster=cluster, query=query
        )
    if reservation.state == "response_saved":
        reservation.mark_processed(copy.deepcopy(result))
    if reservation.state == "processed":
        _force_slot_consumed_budget(result)
    return result


def _legacy_slot_was_consumed_or_ambiguous(prior: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(prior, dict)
        and _legacy_slot_attempt(prior.get("attempts")) is not None
    )


def _prepare_prior_for_quality(
    prior_plan: dict[str, Any] | None,
    search_window: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    _sync_public_hooks()
    prior_copy = copy.deepcopy(prior_plan) if isinstance(prior_plan, dict) else prior_plan
    publication_date = _publication_date(
        prior_copy if isinstance(prior_copy, dict) else None
    )
    legacy_spent = _legacy_slot_was_consumed_or_ambiguous(
        prior_copy if isinstance(prior_copy, dict) else None
    )
    journal_spent = bool(
        publication_date
        and slot_is_consumed_or_ambiguous(Path(STATE_DIR), publication_date)
    )
    try:
        prepared = _P0_PREPARE_PRIOR_FOR_QUALITY(prior_plan, search_window)
    finally:
        _pull_runtime_state()
    if not isinstance(prepared, dict) or not (legacy_spent or journal_spent):
        return prepared

    saved_attempt = _legacy_slot_attempt(
        prior_copy.get("attempts") if isinstance(prior_copy, dict) else None
    )
    if saved_attempt is not None and _legacy_slot_attempt(prepared.get("attempts")) is None:
        saved_attempt["search_operation_count_contribution"] = 1
        saved_attempt.setdefault("slot_state", "legacy_spent_or_ambiguous")
        prepared.setdefault("attempts", []).append(saved_attempt)
    _force_slot_consumed_budget(prepared)
    return prepared


def execute_audit_plan(*args: Any, **kwargs: Any) -> Any:
    publication_date = str(kwargs.get("publication_date") or "").strip() or None
    token = _CURRENT_PUBLICATION_DATE.set(publication_date)
    _sync_slot_hooks()
    try:
        return _P0_EXECUTE_AUDIT_PLAN(*args, **kwargs)
    finally:
        _pull_runtime_state()
        _CURRENT_PUBLICATION_DATE.reset(token)


def _primary_search_diagnostics(*args: Any, **kwargs: Any) -> Any:
    _sync_public_hooks()
    try:
        return _P0_PRIMARY_SEARCH_DIAGNOSTICS(*args, **kwargs)
    finally:
        _pull_runtime_state()


def _finalize_quality_report(*args: Any, **kwargs: Any) -> Any:
    _sync_public_hooks()
    try:
        return _P0_FINALIZE_QUALITY_REPORT(*args, **kwargs)
    finally:
        _pull_runtime_state()


def main() -> int:
    publication_date = str(_base._arg("--publication-date") or "").strip() or None
    token = _CURRENT_PUBLICATION_DATE.set(publication_date)
    _sync_slot_hooks()
    try:
        return int(_P0_MAIN())
    finally:
        _pull_runtime_state()
        _CURRENT_PUBLICATION_DATE.reset(token)


if __name__ == "__main__":
    raise SystemExit(main())
