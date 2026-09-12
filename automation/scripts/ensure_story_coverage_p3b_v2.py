#!/usr/bin/env python3
"""P3b v2: exact page-bound admission over the shared durable Coverage slot.

The first P3b implementation is preserved in ensure_story_coverage_p3b.py for
forensic comparison. v2 fixes the independent Astra findings: it protects an
existing P3b journal before legacy optional search routing, passes publication
date explicitly, binds identity to the fetched authoritative page, runs the
existing deterministic Event/Source Freshness gate before positive admission,
and never treats model-supplied terminal labels as independent proof.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import source_freshness as _source_freshness
from coverage_slot_guard import CoverageSlotError, load_journal, prepare_slot, sha256_value
from coverage_slot_transport import protected_policy_audit_request, replay_raw_response, replay_result_snapshot
from weak_source_exact_binding_v2 import (
    MODE as P3B_MODE,
    VERSION as P3B_EXACT_BINDING_VERSION,
    build_prompt as _build_prompt_v1,
    build_query as build_p3b_query,
    candidate_exact_binding,
    extract_authoritative_event_surface,
    qualifying_signals as qualifying_p3b_signals,
    select_signal as select_p3b_signal,
)

_V1_PATH = Path(__file__).with_name("ensure_story_coverage_p3b.py")
_V1_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p3b_v1", _V1_PATH)
assert _V1_SPEC and _V1_SPEC.loader
_v1 = importlib.util.module_from_spec(_V1_SPEC)
sys.modules[_V1_SPEC.name] = _v1
_V1_SPEC.loader.exec_module(_v1)

for _name in dir(_v1):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_v1, _name)

# Restore v2 symbols overwritten by the compatibility export above.
P3B_EXACT_BINDING_VERSION = 2
P3B_MODE = "weak_source_exact_authoritative_binding"

_SYNC_EXCLUSIONS = {
    "main", "execute_audit_plan", "_p3b_execute", "_sync_p3b_public_hooks",
    "_pull_p3b_runtime_state", "_run_p3b_binding_v2", "_process_p3b_payload_v2",
}


def _sync_p3b_public_hooks() -> None:
    current = globals()
    for name, value in list(current.items()):
        if name in _SYNC_EXCLUSIONS or (name.startswith("__") and name.endswith("__")):
            continue
        if hasattr(_v1, name):
            setattr(_v1, name, value)
    _v1._sync_p3b_public_hooks()


def _pull_p3b_runtime_state() -> None:
    _v1._pull_p3b_runtime_state()
    for name in ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE"):
        if hasattr(_v1, name):
            globals()[name] = getattr(_v1, name)


def build_p3b_prompt(*, search_window: dict[str, Any], signal: dict[str, Any], archive: list[dict[str, Any]]) -> str:
    prompt = _build_prompt_v1(search_window=search_window, signal=signal, archive=archive)
    prompt = prompt.replace("Версия exact binding: 1", "Версия exact binding: 2")
    return prompt + (
        "\n\nP3b v2 verification note: model output is still not proof. The runtime will "
        "fetch the claimed authoritative primary URL and independently verify exact current-event "
        "identity plus Event/Source Freshness before candidate admission."
    )


def _request_contract_v2(*, model: str, query: str, prompt: str, signal: dict[str, Any]) -> dict[str, Any]:
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


def _annotation(
    plan: dict[str, Any], *, status: str, reason: str,
    signal: dict[str, Any] | None = None, query: str | None = None,
    disposition: str | None = None, slot_state: str | None = None,
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
        "authoritative_page_proof_required": True,
        "deterministic_freshness_required": True,
        "additional_slot_count": 0,
    }
    return result


def _valid_publication_date(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return raw if parsed.isoformat() == raw else None


def _parse_window(search_window: dict[str, Any]) -> tuple[datetime, datetime] | None:
    try:
        start = datetime.fromisoformat(str(search_window.get("start_at") or "").replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(search_window.get("end_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None or end.tzinfo is None or end < start:
        return None
    return start, end


def _archive_exact_event(archive: dict[str, Any], candidate: dict[str, Any], signal: dict[str, Any]) -> bool:
    source = candidate.get("primary_source")
    candidate_url = str(source.get("url") or "").strip() if isinstance(source, dict) else ""
    for issue in archive.get("items") or []:
        if not isinstance(issue, dict):
            continue
        if candidate_url and candidate_url in {str(url).strip() for url in issue.get("source_urls") or []}:
            return True
        for story in issue.get("stories") or []:
            if not isinstance(story, dict):
                continue
            story_urls = {
                str(row.get("url") or "").strip()
                for row in story.get("sources") or []
                if isinstance(row, dict)
            }
            if candidate_url and candidate_url in story_urls:
                return True
            surface = " ".join(
                str(story.get(key) or "")
                for key in ("headline", "organization", "event_type")
            )
            try:
                from weak_source_exact_binding_v2 import exact_event_identity
                matched, _reason = exact_event_identity(surface, signal)
            except Exception:
                matched = False
            if matched:
                return True
    return False


def _append_attempt_v2(plan: dict[str, Any], attempt: dict[str, Any]) -> None:
    attempts = plan.setdefault("attempts", [])
    prior = next((
        item for item in reversed(attempts)
        if isinstance(item, dict)
        and item.get("search_strategy") == P3B_SLOT_OWNER
        and item.get("resolution_mode") == P3B_MODE
        and item.get("p3b_exact_binding_version") == P3B_EXACT_BINDING_VERSION
    ), None)
    if prior is None:
        attempts.append(copy.deepcopy(attempt))
    else:
        prior.update(copy.deepcopy(attempt))


def _attempt_v2(
    *, plan: dict[str, Any], signal: dict[str, Any], query: str, prompt: str,
    metadata: dict[str, Any], candidates: list[dict[str, Any]],
    binding_rejections: list[dict[str, Any]], slot_state: str,
    outcome: str, disposition: str, status: str = "checked",
) -> dict[str, Any]:
    attempt = _v1._p3b_attempt(
        plan=plan, signal=signal, query=query, prompt=prompt, status=status,
        outcome=outcome, disposition=disposition, slot_state=slot_state,
        metadata=metadata, candidates=candidates, rejections=[],
        binding_rejections=binding_rejections, error=None,
    )
    attempt["p3b_exact_binding_version"] = P3B_EXACT_BINDING_VERSION
    attempt["authoritative_page_proof_required"] = True
    attempt["terminal_negative_model_labels_accepted"] = False
    return attempt


def _process_p3b_payload_v2(
    *, base_plan: dict[str, Any], signal: dict[str, Any], query: str, prompt: str,
    payload: dict[str, Any], metadata: dict[str, Any], slot_state: str,
    search_window: dict[str, Any], archive: dict[str, Any],
    allow_page_fetch: bool,
    page_fetcher: Callable[[str], tuple[str, str, int]] | None = None,
) -> dict[str, Any]:
    result = copy.deepcopy(base_plan)
    actual_queries = [str(item).strip() for item in metadata.get("actual_queries") or [] if str(item).strip()]
    query_exact = (
        int(metadata.get("web_search_calls_completed", 0) or 0) == 1
        and len(actual_queries) == 1 and actual_queries[0] == query
    )
    domains = tuple(getattr(_policy, "AUTHORITATIVE_LAST_MILE_DOMAINS", ()) or ())
    window = _parse_window(search_window)
    fetcher = page_fetcher or _source_freshness.fetch_source_html
    cache: dict[str, tuple[str, str, int]] = {}

    def cached_fetch(url: str) -> tuple[str, str, int]:
        if url not in cache:
            cache[url] = fetcher(url)
        return cache[url]

    accepted: list[dict[str, Any]] = []
    binding_rejections: list[dict[str, Any]] = []
    for raw in payload.get("candidates") or []:
        title = str(raw.get("title") or "") if isinstance(raw, dict) else ""
        if not query_exact:
            binding_rejections.append({"title": title, "reason": "actual_query_mismatch"})
            continue
        if not isinstance(raw, dict):
            binding_rejections.append({"title": title, "reason": "candidate_not_object"})
            continue
        if not allow_page_fetch:
            binding_rejections.append({"title": title, "reason": "authoritative_page_proof_not_saved_for_offline_replay"})
            continue
        source = raw.get("primary_source")
        source_url = str(source.get("url") or "").strip() if isinstance(source, dict) else ""
        try:
            html, final_url, http_status = cached_fetch(source_url)
        except Exception as exc:
            binding_rejections.append({"title": title, "reason": f"authoritative_page_fetch_failed:{type(exc).__name__}"})
            continue
        if http_status != 200:
            binding_rejections.append({"title": title, "reason": f"authoritative_page_http_status:{http_status}"})
            continue
        surface = extract_authoritative_event_surface(html)
        ok, reason = candidate_exact_binding(
            raw, signal, authoritative_domains=domains,
            authoritative_page_surface=surface,
            authoritative_final_url=final_url,
        )
        if not ok:
            binding_rejections.append({"title": title, "reason": reason})
            continue
        if window is None:
            binding_rejections.append({"title": title, "reason": "invalid_search_window_for_deterministic_freshness"})
            continue
        item = copy.deepcopy(raw)
        item["supporting_sources"] = []
        freshness = _source_freshness.verify_candidate(
            item, start_at=window[0], end_at=window[1], fetcher=cached_fetch
        )
        if freshness.get("status") != "verified_fresh" or item.get("recommendation") not in {"include", "consider"}:
            binding_rejections.append({
                "title": title,
                "reason": f"deterministic_freshness_rejected:{freshness.get('status')}",
            })
            continue
        if _archive_exact_event(archive, item, signal):
            binding_rejections.append({"title": title, "reason": "archive_exact_event_duplicate"})
            continue
        item["audit_direction"] = "weak_source_exact_binding"
        item["resolution_signal_ids"] = [str(signal.get("signal_id") or "")]
        item["p3b_exact_binding_version"] = P3B_EXACT_BINDING_VERSION
        item["p3b_authoritative_page_url"] = final_url
        item["p3b_authoritative_page_proof"] = "current-event surface + deterministic Source/Event Freshness"
        accepted.append(item)

    accepted.sort(key=_v1._candidate_sort_key)
    accepted = accepted[:1]
    if accepted:
        result.setdefault("candidates", []).extend(copy.deepcopy(accepted))
        status, disposition, outcome = "bound_candidate", "positive_exact_binding", "candidate_bound"
        reason = "exact current-event authoritative page and deterministic freshness were proven"
    else:
        status, disposition, outcome = "unresolved", "unresolved_deferred", "unresolved"
        reason = (
            "actual search query differed from the exact P3b request"
            if not query_exact else
            "no candidate survived exact authoritative-page identity, deterministic freshness and archive checks"
        )

    # Provider rejection labels are diagnostic only. They cannot close the signal.
    for rejection in payload.get("rejections") or []:
        if isinstance(rejection, dict):
            binding_rejections.append({
                "title": str(rejection.get("title") or ""),
                "reason": "terminal_negative_requires_independent_proof",
            })

    attempt = _attempt_v2(
        plan=result, signal=signal, query=query, prompt=prompt, metadata=metadata,
        candidates=accepted, binding_rejections=binding_rejections,
        slot_state=slot_state, outcome=outcome, disposition=disposition,
        status="checked" if payload.get("status") == "complete" else "checked_with_gaps",
    )
    _append_attempt_v2(result, attempt)
    maximum = max(7, int((result.get("search_budget") or {}).get("maximum_calls", 7) or 7))
    _pre._recalculate_budget(result, maximum)
    _v1._p3b_force_consumed(result)
    return _annotation(
        result, status=status, reason=reason, signal=signal, query=query,
        disposition=disposition, slot_state=slot_state, candidate_count=len(accepted),
    )


def _run_p3b_binding_v2(
    *, plan: dict[str, Any], publication_date: str, signal: dict[str, Any],
    api_key: str, model: str, search_window: dict[str, Any], archive: dict[str, Any],
) -> dict[str, Any]:
    if _valid_publication_date(publication_date) is None:
        return _annotation(
            plan, status="deferred", reason="invalid publication_date before optional-slot reservation",
            signal=signal, disposition="unresolved_deferred",
        )
    query = build_p3b_query(signal)
    prompt = build_p3b_prompt(
        search_window=search_window, signal=signal,
        archive=_runtime._compact_recent_archive(archive),
    )
    contract = _request_contract_v2(model=model, query=query, prompt=prompt, signal=signal)
    try:
        reservation = prepare_slot(
            state_dir=Path(STATE_DIR), publication_date=publication_date,
            owner=P3B_SLOT_OWNER, search_window=search_window,
            request_contract=contract, bundle_identity=_v1._p3a._bundle_identity(plan),
        )
    except Exception as exc:
        # Pre-transport reservation/config failures are not evidence of spent capacity.
        return _annotation(
            plan, status="deferred",
            reason=f"optional slot reservation unavailable before transport: {type(exc).__name__}: {exc}",
            signal=signal, query=query, disposition="unresolved_deferred",
        )

    initial_state = reservation.state
    if initial_state == "request_started":
        result = _annotation(
            plan, status="indeterminate",
            reason="optional slot request outcome is unknown; automatic retry forbidden",
            signal=signal, query=query, disposition="unresolved_deferred", slot_state=initial_state,
        )
        _v1._p3b_force_consumed(result)
        return result
    if initial_state == "processed":
        saved = reservation.processed_snapshot()
        if isinstance(saved, dict) and (saved.get(_P3B_DIAGNOSTIC_KEY) or {}).get("version") == P3B_EXACT_BINDING_VERSION:
            result = copy.deepcopy(saved)
            _v1._p3b_force_consumed(result)
            return result
        result = _annotation(
            plan, status="unresolved",
            reason="processed optional slot lacks a safe P3b v2 processed snapshot",
            signal=signal, query=query, disposition="unresolved_deferred", slot_state=initial_state,
        )
        _v1._p3b_force_consumed(result)
        return result

    try:
        if initial_state == "response_saved":
            snapshot = reservation.result_snapshot()
            if not isinstance(snapshot, dict):
                parsed, snapshot = replay_raw_response(_runtime, reservation.raw_response(), maximum_web_search_calls=1)
                reservation.save_result_snapshot(snapshot)
                request_result = parsed
            else:
                request_result = replay_result_snapshot(_runtime, snapshot)
            allow_page_fetch = False
        else:
            request_result = protected_policy_audit_request(
                _runtime, reservation, api_key=api_key, model=model, prompt=prompt,
                maximum_web_search_calls=1, allowed_domains=(),
            )
            allow_page_fetch = True
    except BaseException as exc:
        result = _annotation(
            plan, status="indeterminate" if reservation.state == "request_started" else "unresolved",
            reason=f"P3b exact-binding response unavailable: {type(exc).__name__}: {exc}",
            signal=signal, query=query, disposition="unresolved_deferred", slot_state=reservation.state,
        )
        if reservation.state in {"request_started", "response_saved", "processed"}:
            _v1._p3b_force_consumed(result)
        if reservation.state == "response_saved":
            reservation.mark_processed(copy.deepcopy(result))
        return result

    payload = request_result.payload if isinstance(request_result.payload, dict) else {}
    metadata = request_result.metadata if isinstance(request_result.metadata, dict) else {}
    result = _process_p3b_payload_v2(
        base_plan=plan, signal=signal, query=query, prompt=prompt,
        payload=payload, metadata=metadata, slot_state=reservation.state,
        search_window=search_window, archive=archive,
        allow_page_fetch=allow_page_fetch,
    )
    if reservation.state == "response_saved":
        reservation.mark_processed(copy.deepcopy(result))
    if reservation.state == "processed":
        _v1._p3b_force_consumed(result)
    return result


def _p3b_contract_hashes(
    *, signal: dict[str, Any], model: str, search_window: dict[str, Any], archive: dict[str, Any]
) -> set[str]:
    query = build_p3b_query(signal)
    compact = _runtime._compact_recent_archive(archive)
    v1_prompt = _build_prompt_v1(search_window=search_window, signal=signal, archive=compact)
    v2_prompt = build_p3b_prompt(search_window=search_window, signal=signal, archive=compact)
    v1_contract = _v1._p3b_request_contract(model=model, query=query, prompt=v1_prompt, signal=signal)
    v2_contract = _request_contract_v2(model=model, query=query, prompt=v2_prompt, signal=signal)
    return {sha256_value(v1_contract), sha256_value(v2_contract)}


def _p3b_execute(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    try:
        publication_date = _valid_publication_date(kwargs.get("publication_date"))
        search_window = kwargs.get("search_window") or {}
        archive = kwargs.get("archive") or {}
        model = str(kwargs.get("model") or "")
        pre_signal = select_p3b_signal(_v1._p3b_signals(publication_date)) if publication_date else None
        journal = None
        journal_is_p3b = False
        journal_is_v2 = False
        invalid_journal = False
        if publication_date:
            try:
                journal = load_journal(Path(STATE_DIR), publication_date)
            except CoverageSlotError:
                invalid_journal = True
            if isinstance(journal, dict) and pre_signal is not None:
                hashes = _p3b_contract_hashes(
                    signal=pre_signal, model=model, search_window=search_window, archive=archive
                )
                saved_hash = str(journal.get("request_contract_sha256") or "")
                journal_is_p3b = saved_hash in hashes
                if journal_is_p3b:
                    query = build_p3b_query(pre_signal)
                    v2_prompt = build_p3b_prompt(
                        search_window=search_window, signal=pre_signal,
                        archive=_runtime._compact_recent_archive(archive),
                    )
                    journal_is_v2 = saved_hash == sha256_value(
                        _request_contract_v2(model=model, query=query, prompt=v2_prompt, signal=pre_signal)
                    )

        call_kwargs = dict(kwargs)
        original_max = int(call_kwargs.get("maximum_web_search_calls", 7) or 7)
        if journal_is_p3b or invalid_journal:
            call_kwargs["maximum_web_search_calls"] = min(original_max, 6)
        result = _v1._P3A_EXECUTE_AUDIT_PLAN(*args, **call_kwargs)
        if not isinstance(result, dict):
            return result
        if publication_date is None:
            return result

        # Restore the architectural 6+1 accounting after temporarily suppressing
        # all legacy optional routing around an already-owned P3b slot.
        if journal_is_p3b:
            _pre._recalculate_budget(result, max(7, original_max))

        signal = select_p3b_signal(_v1._p3b_signals(publication_date))
        if signal is None:
            return _annotation(result, status="not_applicable", reason="no qualified weak-source product signal")
        legacy_required = _pre._required_signals(publication_date)
        if legacy_required and not journal_is_p3b:
            return _annotation(
                result, status="deferred",
                reason="existing required unresolved/unverified resolution has slot priority",
                signal=signal, disposition="unresolved_deferred",
            )
        if invalid_journal:
            return _annotation(
                result, status="deferred",
                reason="Coverage optional-slot journal is invalid; optional capacity fails closed",
                signal=signal, disposition="unresolved_deferred",
            )
        if journal_is_p3b and not journal_is_v2:
            deferred = _annotation(
                result, status="deferred",
                reason="pre-v2 P3b slot is consumed/reserved but cannot be reinterpreted under the hardened binding contract",
                signal=signal, disposition="unresolved_deferred",
                slot_state=str((journal or {}).get("state") or ""),
            )
            if (journal or {}).get("state") in {"request_started", "response_saved", "processed"}:
                _v1._p3b_force_consumed(deferred)
            return deferred

        checked = set(result.get("checked_directions") or ())
        if checked != set(_pre.AUDIT_DIRECTION_IDS):
            return _annotation(
                result, status="deferred", reason="mandatory Coverage is incomplete",
                signal=signal, disposition="unresolved_deferred",
            )

        if journal_is_v2:
            return _run_p3b_binding_v2(
                plan=result, publication_date=publication_date, signal=signal,
                api_key=str(kwargs.get("api_key") or ""), model=model,
                search_window=search_window, archive=archive,
            )

        budget = result.get("search_budget")
        remaining = int(budget.get("remaining_calls", 0) or 0) if isinstance(budget, dict) else 0
        if remaining < 1:
            return _annotation(
                result, status="deferred", reason="existing Coverage optional slot is unavailable",
                signal=signal, disposition="unresolved_deferred",
            )
        return _run_p3b_binding_v2(
            plan=result, publication_date=publication_date, signal=signal,
            api_key=str(kwargs.get("api_key") or ""), model=model,
            search_window=search_window, archive=archive,
        )
    finally:
        _pull_p3b_runtime_state()


def execute_audit_plan(*args: Any, **kwargs: Any) -> Any:
    return _p3b_execute(*args, **kwargs)


def main() -> int:
    # CLI compatibility remains delegated to v1/P3a until P3b is invoked through
    # the policy entrypoint; direct tests and runtime imports use execute_audit_plan.
    return int(_v1.main())


if __name__ == "__main__":
    raise SystemExit(main())
