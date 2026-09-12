#!/usr/bin/env python3
"""P3b exact authoritative binding over the recovery-safe Coverage optional slot.

The complete pre-P3b public implementation is preserved byte-for-byte in
``ensure_story_coverage_p3a.py``. This layer leaves the existing high-signal
``unverified`` resolution path unchanged and opportunistically uses the same
already-existing seventh Coverage slot only when no older required obligation
owns it. Weak-source evidence remains non-blocking unless exact authoritative
same-event evidence is independently found.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

from coverage_slot_guard import (
    CoverageSlotError,
    activate_slot,
    load_journal,
    prepare_slot,
    sha256_value,
    slot_is_consumed_or_ambiguous,
)
from coverage_slot_transport import (
    protected_policy_audit_request,
    replay_raw_response,
    replay_result_snapshot,
)
from weak_source_exact_binding import (
    MODE as P3B_MODE,
    VERSION as P3B_EXACT_BINDING_VERSION,
    build_prompt as build_p3b_prompt,
    build_query as build_p3b_query,
    candidate_exact_binding,
    qualifying_signals as qualifying_p3b_signals,
    rejection_exact_terminal_binding,
    select_signal as select_p3b_signal,
)

_BASE_PATH = Path(__file__).with_name("ensure_story_coverage_p3a.py")
_BASE_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p3a", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
_p3a = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _p3a
_BASE_SPEC.loader.exec_module(_p3a)

for _name in dir(_p3a):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_p3a, _name)


def __getattr__(name: str) -> Any:
    return getattr(_p3a, name)


_P3A_EXECUTE_AUDIT_PLAN = _p3a.execute_audit_plan
_P3A_MAIN = _p3a.main
_P3A_PRIMARY_SEARCH_DIAGNOSTICS = _p3a._primary_search_diagnostics
_P3A_FINALIZE_QUALITY_REPORT = _p3a._finalize_quality_report
_P3A_PREPARE_PRIOR_FOR_QUALITY = _p3a._prepare_prior_for_quality
_P3B_DIAGNOSTIC_KEY = "weak_source_exact_binding"
P3B_SLOT_OWNER = _p3a.OPTIONAL_SLOT_OWNER

_P3B_SYNC_EXCLUSIONS = {
    "main",
    "execute_audit_plan",
    "_p3b_execute",
    "_sync_p3b_public_hooks",
    "_pull_p3b_runtime_state",
    "_P3A_EXECUTE_AUDIT_PLAN",
    "_P3A_MAIN",
    "_P3A_PRIMARY_SEARCH_DIAGNOSTICS",
    "_P3A_FINALIZE_QUALITY_REPORT",
    "_P3A_PREPARE_PRIOR_FOR_QUALITY",
}


def _sync_p3b_public_hooks() -> None:
    """Mirror monkeypatchable public/private state into the preserved P3a layer."""
    current = globals()
    for name, value in list(current.items()):
        if name.startswith("__") and name.endswith("__"):
            continue
        if name in _P3B_SYNC_EXCLUSIONS or name.startswith("_P3B_"):
            continue
        if hasattr(_p3a, name):
            setattr(_p3a, name, value)


def _pull_p3b_runtime_state() -> None:
    for name in ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE"):
        if hasattr(_p3a, name):
            globals()[name] = getattr(_p3a, name)


def _p3b_report(publication_date: str) -> dict[str, Any] | None:
    try:
        value = _pre._primary_quality_report(publication_date)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _p3b_signals(publication_date: str) -> list[dict[str, Any]]:
    return qualifying_p3b_signals(
        _p3b_report(publication_date),
        contract_version=_pre.RETRIEVAL_QUALITY_CONTRACT_VERSION,
    )


def _p3b_annotation(
    plan: dict[str, Any],
    *,
    status: str,
    reason: str,
    signal: dict[str, Any] | None = None,
    query: str | None = None,
    disposition: str | None = None,
    slot_state: str | None = None,
    candidate_count: int = 0,
) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    result[_P3B_DIAGNOSTIC_KEY] = {
        "version": P3B_EXACT_BINDING_VERSION,
        "mode": P3B_MODE,
        "status": status,
        "reason": reason,
        "signal_id": str((signal or {}).get("signal_id") or "") or None,
        "query": query,
        "disposition": disposition,
        "slot_state": slot_state,
        "candidate_count": int(candidate_count),
        "required": False,
        "candidate_eligibility_requires_exact_binding": True,
        "automatic_unverified_closure": False,
        "additional_slot_count": 0,
    }
    return result


def _p3b_request_contract(
    *,
    model: str,
    query: str,
    prompt: str,
    signal: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": P3B_EXACT_BINDING_VERSION,
        "strategy": P3B_SLOT_OWNER,
        "mode": P3B_MODE,
        "model": model,
        "query": query,
        "prompt_sha256": sha256_value(prompt),
        "signal_ids": [str(signal.get("signal_id") or "")],
        "maximum_web_search_calls": 1,
        "allowed_domains": [],
    }


def _p3b_attempt_number(plan: dict[str, Any]) -> int:
    return 1 + max(
        [
            int(item.get("attempt", 0) or 0)
            for item in plan.get("attempts", [])
            if isinstance(item, dict)
            and item.get("direction_id") == "general_coverage_gaps"
        ]
        or [0]
    )


def _p3b_attempt(
    *,
    plan: dict[str, Any],
    signal: dict[str, Any],
    query: str,
    prompt: str,
    status: str,
    outcome: str,
    disposition: str,
    slot_state: str,
    metadata: dict[str, Any] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    rejections: list[dict[str, Any]] | None = None,
    binding_rejections: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    metadata = copy.deepcopy(metadata) if isinstance(metadata, dict) else {
        "status": "indeterminate",
        "web_search_calls_completed": 0,
        "web_search_call_items_total": 0,
    }
    return {
        "direction_id": "general_coverage_gaps",
        "label": "Weak-source exact authoritative binding P3b",
        "required": False,
        "attempt": _p3b_attempt_number(plan),
        "search_strategy": P3B_SLOT_OWNER,
        "p3b_exact_binding_version": P3B_EXACT_BINDING_VERSION,
        "resolution_mode": P3B_MODE,
        "allowed_domains": [],
        "signal_ids": [str(signal.get("signal_id") or "")],
        "required_query": query,
        "prompt": prompt,
        "status": status,
        "outcome": outcome,
        "resolution_disposition": disposition,
        "actual_queries": list(metadata.get("actual_queries") or []),
        "sources": list(metadata.get("consulted_sources") or []),
        "candidate_count": len(candidates or []),
        "candidates": copy.deepcopy(candidates or []),
        "rejections": copy.deepcopy(rejections or []),
        "binding_rejections": copy.deepcopy(binding_rejections or []),
        "api": metadata,
        "error": error,
        "slot_state": slot_state,
        "search_operation_count_contribution": 1,
    }


def _append_p3b_attempt(plan: dict[str, Any], attempt: dict[str, Any]) -> None:
    attempts = plan.setdefault("attempts", [])
    prior = next(
        (
            item
            for item in reversed(attempts)
            if isinstance(item, dict)
            and item.get("search_strategy") == P3B_SLOT_OWNER
            and item.get("p3b_exact_binding_version") == P3B_EXACT_BINDING_VERSION
        ),
        None,
    )
    if prior is None:
        attempts.append(copy.deepcopy(attempt))
    else:
        prior.update(copy.deepcopy(attempt))


def _p3b_force_consumed(plan: dict[str, Any]) -> None:
    _p3a._force_slot_consumed_budget(plan)


def _authoritative_domains() -> tuple[str, ...]:
    return tuple(getattr(_policy, "AUTHORITATIVE_LAST_MILE_DOMAINS", ()) or ())


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, str, str]:
    source_type = str(candidate.get("source_type") or "")
    rank = {
        "official": 0,
        "documentation": 1,
        "government": 1,
        "regulator": 1,
        "court": 1,
        "research": 2,
        "news_agency": 3,
        "business_media": 4,
        "technology_media": 5,
        "industry_media": 6,
    }.get(source_type, 9)
    source = candidate.get("primary_source")
    url = str(source.get("url") or "") if isinstance(source, dict) else ""
    return rank, url, str(candidate.get("title") or "")


def _process_p3b_payload(
    *,
    base_plan: dict[str, Any],
    signal: dict[str, Any],
    query: str,
    prompt: str,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    slot_state: str,
) -> dict[str, Any]:
    result = copy.deepcopy(base_plan)
    domains = _authoritative_domains()
    actual_queries = [
        str(item).strip()
        for item in metadata.get("actual_queries") or []
        if str(item).strip()
    ]
    query_exact = (
        int(metadata.get("web_search_calls_completed", 0) or 0) == 1
        and len(actual_queries) == 1
        and actual_queries[0] == query
    )

    exact_candidates: list[dict[str, Any]] = []
    binding_rejections: list[dict[str, Any]] = []
    for raw in payload.get("candidates") or []:
        ok, reason = candidate_exact_binding(
            raw,
            signal,
            authoritative_domains=domains,
        )
        if ok and query_exact:
            item = copy.deepcopy(raw)
            item["audit_direction"] = "weak_source_exact_binding"
            item["resolution_signal_ids"] = [str(signal.get("signal_id") or "")]
            item["p3b_exact_binding_version"] = P3B_EXACT_BINDING_VERSION
            exact_candidates.append(item)
        else:
            binding_rejections.append({
                "title": str(raw.get("title") or "") if isinstance(raw, dict) else "",
                "reason": reason if query_exact else "actual_query_mismatch",
            })
    exact_candidates.sort(key=_candidate_sort_key)
    exact_candidates = exact_candidates[:1]

    exact_terminal: list[dict[str, Any]] = []
    for rejection in payload.get("rejections") or []:
        ok, reason = rejection_exact_terminal_binding(
            rejection,
            signal,
            authoritative_domains=domains,
        )
        if ok and query_exact:
            exact_terminal.append(copy.deepcopy(rejection))
        elif isinstance(rejection, dict):
            binding_rejections.append({
                "title": str(rejection.get("title") or ""),
                "reason": reason if query_exact else "actual_query_mismatch",
            })

    contradictory = bool(exact_candidates and exact_terminal)
    if contradictory:
        exact_candidates = []
        disposition = "unresolved"
        outcome = "contradictory_exact_evidence"
        reason = "provider output contained both exact positive and exact terminal-negative evidence"
    elif exact_candidates:
        disposition = "positive_exact_binding"
        outcome = "candidate_bound"
        reason = "exact same-event authoritative candidate bound"
        result.setdefault("candidates", []).extend(copy.deepcopy(exact_candidates))
    elif exact_terminal:
        disposition = "terminal_negative_exact_binding"
        outcome = "resolved_no_candidate"
        reason = "exact same-event authoritative terminal negative bound"
    else:
        disposition = "unresolved_deferred"
        outcome = "unresolved"
        reason = (
            "actual search query differed from the exact P3b request"
            if not query_exact
            else "no exact same-event authoritative binding was proven"
        )

    attempt = _p3b_attempt(
        plan=result,
        signal=signal,
        query=query,
        prompt=prompt,
        status="checked" if payload.get("status") == "complete" else "checked_with_gaps",
        outcome=outcome,
        disposition=disposition,
        slot_state=slot_state,
        metadata=metadata,
        candidates=exact_candidates,
        rejections=[item for item in payload.get("rejections") or [] if isinstance(item, dict)],
        binding_rejections=binding_rejections,
        error=None,
    )
    _append_p3b_attempt(result, attempt)
    maximum = int((result.get("search_budget") or {}).get("maximum_calls", 7) or 7)
    _pre._recalculate_budget(result, maximum)
    _p3b_force_consumed(result)
    result = _p3b_annotation(
        result,
        status=(
            "bound_candidate"
            if exact_candidates
            else ("terminal_negative" if exact_terminal and not contradictory else "unresolved")
        ),
        reason=reason,
        signal=signal,
        query=query,
        disposition=disposition,
        slot_state=slot_state,
        candidate_count=len(exact_candidates),
    )
    return result


def _p3b_nonblocking_failure(
    *,
    base_plan: dict[str, Any],
    signal: dict[str, Any],
    query: str,
    prompt: str,
    reservation: Any,
    reason: str,
    error: BaseException | None = None,
) -> dict[str, Any]:
    result = copy.deepcopy(base_plan)
    state = str(getattr(reservation, "state", "") or "")
    snapshot = reservation.result_snapshot() if state in {"response_saved", "processed"} else None
    metadata = snapshot.get("metadata") if isinstance(snapshot, dict) else None
    attempt = _p3b_attempt(
        plan=result,
        signal=signal,
        query=query,
        prompt=prompt,
        status="indeterminate" if state == "request_started" else "checked_with_gaps",
        outcome="transport_indeterminate" if state == "request_started" else "response_unusable",
        disposition="unresolved_deferred",
        slot_state=state,
        metadata=metadata if isinstance(metadata, dict) else None,
        candidates=[],
        rejections=[],
        binding_rejections=[],
        error=(
            f"{type(error).__name__}: {error}"
            if error is not None
            else reason
        ),
    )
    _append_p3b_attempt(result, attempt)
    _p3b_force_consumed(result)
    result = _p3b_annotation(
        result,
        status="indeterminate" if state == "request_started" else "unresolved",
        reason=reason,
        signal=signal,
        query=query,
        disposition="unresolved_deferred",
        slot_state=state,
    )
    return result


def _run_p3b_binding(
    *,
    plan: dict[str, Any],
    signal: dict[str, Any],
    api_key: str,
    model: str,
    search_window: dict[str, Any],
    archive: dict[str, Any],
) -> dict[str, Any]:
    publication_date = str(plan.get("publication_date") or "").strip()
    query = build_p3b_query(signal)
    prompt = build_p3b_prompt(
        search_window=search_window,
        signal=signal,
        archive=_runtime._compact_recent_archive(archive),
    )
    contract = _p3b_request_contract(
        model=model,
        query=query,
        prompt=prompt,
        signal=signal,
    )
    try:
        reservation = prepare_slot(
            state_dir=Path(STATE_DIR),
            publication_date=publication_date,
            owner=P3B_SLOT_OWNER,
            search_window=search_window,
            request_contract=contract,
            bundle_identity=_p3a._bundle_identity(plan),
        )
    except Exception as exc:
        result = _p3b_annotation(
            plan,
            status="deferred",
            reason=f"optional slot reserved for a different exact intent or invalid: {type(exc).__name__}: {exc}",
            signal=signal,
            query=query,
            disposition="unresolved_deferred",
            slot_state=None,
        )
        _p3b_force_consumed(result)
        return result

    state = reservation.state
    if state == "request_started":
        return _p3b_nonblocking_failure(
            base_plan=plan,
            signal=signal,
            query=query,
            prompt=prompt,
            reservation=reservation,
            reason="optional slot request outcome is unknown; automatic retry forbidden",
        )
    if state == "processed":
        saved = reservation.processed_snapshot()
        if isinstance(saved, dict):
            result = copy.deepcopy(saved)
            _p3b_force_consumed(result)
            return result
        return _p3b_nonblocking_failure(
            base_plan=plan,
            signal=signal,
            query=query,
            prompt=prompt,
            reservation=reservation,
            reason="processed P3b slot is missing its deterministic processed snapshot",
        )

    try:
        if state == "response_saved":
            snapshot = reservation.result_snapshot()
            if not isinstance(snapshot, dict):
                parsed, snapshot = replay_raw_response(
                    _runtime,
                    reservation.raw_response(),
                    maximum_web_search_calls=1,
                )
                reservation.save_result_snapshot(snapshot)
                request_result = parsed
            else:
                request_result = replay_result_snapshot(_runtime, snapshot)
        else:
            request_result = protected_policy_audit_request(
                _runtime,
                reservation,
                api_key=api_key,
                model=model,
                prompt=prompt,
                maximum_web_search_calls=1,
                allowed_domains=(),
            )
    except BaseException as exc:
        result = _p3b_nonblocking_failure(
            base_plan=plan,
            signal=signal,
            query=query,
            prompt=prompt,
            reservation=reservation,
            reason="P3b exact-binding response is unavailable or unusable",
            error=exc,
        )
        if reservation.state == "response_saved":
            reservation.mark_processed(copy.deepcopy(result))
        return result

    payload = request_result.payload if isinstance(request_result.payload, dict) else {}
    metadata = request_result.metadata if isinstance(request_result.metadata, dict) else {}
    result = _process_p3b_payload(
        base_plan=plan,
        signal=signal,
        query=query,
        prompt=prompt,
        payload=payload,
        metadata=metadata,
        slot_state=reservation.state,
    )
    if reservation.state == "response_saved":
        reservation.mark_processed(copy.deepcopy(result))
    if reservation.state == "processed":
        _p3b_force_consumed(result)
    return result


def _p3b_execute(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    try:
        result = _P3A_EXECUTE_AUDIT_PLAN(*args, **kwargs)
        if not isinstance(result, dict):
            return result

        publication_date = str(
            kwargs.get("publication_date") or result.get("publication_date") or ""
        ).strip()
        if not publication_date:
            return result

        legacy_required = _pre._required_signals(publication_date)
        weak_signals = _p3b_signals(publication_date)
        signal = select_p3b_signal(weak_signals)
        if signal is None:
            return _p3b_annotation(
                result,
                status="not_applicable",
                reason="no qualified weak-source product signal",
            )
        if legacy_required:
            return _p3b_annotation(
                result,
                status="deferred",
                reason="existing required unresolved/unverified resolution has slot priority",
                signal=signal,
                disposition="unresolved_deferred",
            )

        existing = result.get(_P3B_DIAGNOSTIC_KEY)
        if isinstance(existing, dict) and existing.get("version") == P3B_EXACT_BINDING_VERSION:
            if existing.get("status") in {
                "bound_candidate",
                "terminal_negative",
                "unresolved",
                "indeterminate",
            }:
                return result

        checked = set(result.get("checked_directions") or ())
        if checked != set(_pre.AUDIT_DIRECTION_IDS):
            return _p3b_annotation(
                result,
                status="deferred",
                reason="mandatory Coverage is incomplete",
                signal=signal,
                disposition="unresolved_deferred",
            )

        budget = result.get("search_budget")
        remaining = int(budget.get("remaining_calls", 0) or 0) if isinstance(budget, dict) else 0
        if remaining < 1:
            return _p3b_annotation(
                result,
                status="deferred",
                reason="existing Coverage optional slot is unavailable",
                signal=signal,
                disposition="unresolved_deferred",
            )

        try:
            existing_journal = load_journal(Path(STATE_DIR), publication_date)
            if isinstance(existing_journal, dict) and slot_is_consumed_or_ambiguous(
                Path(STATE_DIR), publication_date
            ):
                deferred = _p3b_annotation(
                    result,
                    status="deferred",
                    reason="existing Coverage optional slot is already consumed or ambiguous",
                    signal=signal,
                    disposition="unresolved_deferred",
                    slot_state=str(existing_journal.get("state") or ""),
                )
                _p3b_force_consumed(deferred)
                return deferred
        except CoverageSlotError as exc:
            deferred = _p3b_annotation(
                result,
                status="deferred",
                reason=f"Coverage optional-slot state is invalid and treated as unavailable: {exc}",
                signal=signal,
                disposition="unresolved_deferred",
            )
            _p3b_force_consumed(deferred)
            return deferred

        return _run_p3b_binding(
            plan=result,
            signal=signal,
            api_key=str(kwargs.get("api_key") or ""),
            model=str(kwargs.get("model") or ""),
            search_window=kwargs.get("search_window") or {},
            archive=kwargs.get("archive") or {},
        )
    finally:
        _pull_p3b_runtime_state()


def execute_audit_plan(*args: Any, **kwargs: Any) -> Any:
    return _p3b_execute(*args, **kwargs)


def _primary_search_diagnostics(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    try:
        return _P3A_PRIMARY_SEARCH_DIAGNOSTICS(*args, **kwargs)
    finally:
        _pull_p3b_runtime_state()


def _finalize_quality_report(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    try:
        return _P3A_FINALIZE_QUALITY_REPORT(*args, **kwargs)
    finally:
        _pull_p3b_runtime_state()


def _prepare_prior_for_quality(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    try:
        return _P3A_PREPARE_PRIOR_FOR_QUALITY(*args, **kwargs)
    finally:
        _pull_p3b_runtime_state()


def main() -> int:
    _sync_p3b_public_hooks()
    original_execute = _pre.execute_audit_plan
    _pre.execute_audit_plan = execute_audit_plan
    try:
        return int(_P3A_MAIN())
    finally:
        _pre.execute_audit_plan = original_execute
        _pull_p3b_runtime_state()


if __name__ == "__main__":
    raise SystemExit(main())
