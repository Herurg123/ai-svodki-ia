#!/usr/bin/env python3
"""P3b v5 runtime guard for durable legacy handoff and exact event admission.

v4 remains the preserved orchestration baseline. This layer keeps the same single
optional seventh Coverage slot and same durable request contracts while closing
the second independent Astra findings: every required legacy resolution enters
the protected slot transport, active exact binding uses binder v3, and mutable
archive identity preserves ordered event detail instead of unordered token sets.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

import weak_source_exact_binding_v3 as _binding_v3

_V4_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v4.py")
_V4_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p3b_v4_active", _V4_PATH)
assert _V4_SPEC and _V4_SPEC.loader
_v4 = importlib.util.module_from_spec(_V4_SPEC)
sys.modules[_V4_SPEC.name] = _v4
_V4_SPEC.loader.exec_module(_v4)

for _name in dir(_v4):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_v4, _name)

_v3 = _v4._v3
_v2 = _v4._v2
_P3A = _v2._v1._p3a
_PRE_RECALC_BUDGET_KEY = _v4._PRE_RECALC_BUDGET_KEY

build_p3b_query = _binding_v3.build_query
candidate_exact_binding = _binding_v3.candidate_exact_binding
qualifying_p3b_signals = _binding_v3.qualifying_signals
rejection_exact_terminal_binding = _binding_v3.rejection_exact_terminal_binding
select_p3b_signal = _binding_v3.select_signal
extract_authoritative_event_surface = _binding_v3.extract_authoritative_event_surface
P3B_EXACT_BINDING_VERSION = _binding_v3.VERSION
P3B_MODE = _binding_v3.MODE

_V5_INTERNALS = {
    "_v4", "_v3", "_v2", "_P3A", "_binding_v3", "_V4_PATH", "_V4_SPEC",
    "_PRE_RECALC_BUDGET_KEY", "_V5_INTERNALS", "_install_v5_bindings",
    "_sync_p3b_public_hooks", "_pull_p3b_runtime_state",
    "_archive_discriminator_sequence", "_archive_mutable_event_detail_match_v5",
    "_archive_exact_event_v5", "_journal_matches_current_legacy_intent",
    "_run_required_legacy_durable", "execute_audit_plan", "main", "__getattr__",
}


def __getattr__(name: str) -> Any:
    return getattr(_v4, name)


def _install_v5_bindings() -> None:
    """Install hardened binder/archive hooks after every compatibility sync."""
    _v4._exact_binding = _binding_v3
    _v2._binding_v2 = _binding_v3
    _v3._binding_v2 = _binding_v3

    # v2/v3 compatibility synchronization can restore older aliases. Re-run
    # their explicit active-binder restorers after replacing the binder owner.
    _v2._restore_active_binders()
    _v3._restore_active_binders()

    for module in (_v4, _v3, _v2):
        module.build_p3b_query = _binding_v3.build_query
        module.candidate_exact_binding = _binding_v3.candidate_exact_binding
        module.qualifying_p3b_signals = _binding_v3.qualifying_signals
        module.rejection_exact_terminal_binding = _binding_v3.rejection_exact_terminal_binding
        module.select_p3b_signal = _binding_v3.select_signal
        module.extract_authoritative_event_surface = _binding_v3.extract_authoritative_event_surface
        module.P3B_EXACT_BINDING_VERSION = _binding_v3.VERSION
        module.P3B_MODE = _binding_v3.MODE

    _v2._archive_exact_event = _archive_exact_event_v5
    _v4._archive_exact_event = _archive_exact_event_v5
    _v4._archive_exact_event_v4 = _archive_exact_event_v5
    _v2._run_p3b_binding_v2 = _v4._guarded_run_p3b_binding_v2


def _sync_p3b_public_hooks() -> None:
    """Sync public monkeypatch seams, then restore v5 semantic owners."""
    _v4._sync_p3b_public_hooks()
    _install_v5_bindings()


def _pull_p3b_runtime_state() -> None:
    _v4._pull_p3b_runtime_state()
    for name in ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE"):
        if hasattr(_v4, name):
            globals()[name] = getattr(_v4, name)


def _archive_discriminator_sequence(text: Any, signal: dict[str, Any]) -> tuple[str, ...]:
    stops = _v4._archive_identity_stop_tokens(signal)
    return tuple(
        token.casefold()
        for token in _v4._ARCHIVE_TOKEN_RE.findall(str(text or ""))
        if len(token) > 1 and token.casefold() not in stops
    )


def _archive_mutable_event_detail_match_v5(
    candidate: dict[str, Any],
    story: dict[str, Any],
    signal: dict[str, Any],
) -> bool:
    candidate_text = " ".join(
        str(candidate.get(key) or "") for key in ("title", "event_summary")
    )
    story_text = " ".join(
        str(story.get(key) or "") for key in ("headline", "event_summary")
    )
    candidate_sequence = _archive_discriminator_sequence(candidate_text, signal)
    story_sequence = _archive_discriminator_sequence(story_text, signal)
    if len(candidate_sequence) < 2 or len(story_sequence) < 2:
        return False
    return candidate_sequence == story_sequence


def _archive_exact_event_v5(
    archive: dict[str, Any],
    candidate: dict[str, Any],
    signal: dict[str, Any],
) -> bool:
    """Require exact URL or exact semantic event identity with ordered detail."""
    source = candidate.get("primary_source")
    candidate_url = (
        str(source.get("url") or "").strip() if isinstance(source, dict) else ""
    )
    actions = {
        str(item or "").strip().casefold()
        for item in signal.get("lifecycle_action_anchors") or []
        if str(item or "").strip()
    }
    mutable = bool(actions & _v4._ARCHIVE_MUTABLE_ACTIONS)

    for issue in archive.get("items") or []:
        if not isinstance(issue, dict):
            continue
        if candidate_url and candidate_url in {
            str(url).strip() for url in issue.get("source_urls") or []
        }:
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

            headline = str(story.get("headline") or "").strip()
            organization = str(story.get("organization") or "").strip()
            event_type = str(story.get("event_type") or "").strip()
            signal_org = str(signal.get("organization") or "").strip()
            if organization and (
                _binding_v3.normalized_org(organization)
                != _binding_v3.normalized_org(signal_org)
            ):
                continue

            event_claim = " ".join(part for part in (organization, headline) if part)
            surface = " | ".join(part for part in (event_claim, event_type) if part)
            try:
                matched, _reason = _binding_v3.exact_event_identity(surface, signal)
            except Exception:
                matched = False
            if not matched:
                continue
            if not mutable:
                return True
            if _archive_mutable_event_detail_match_v5(candidate, story, signal):
                return True
    return False


def _journal_matches_current_legacy_intent(
    *,
    journal: dict[str, Any],
    model: str,
    search_window: dict[str, Any],
    archive: dict[str, Any],
    required_signals: list[dict[str, Any]],
) -> bool:
    """Identify only the current required-resolution durable request contract."""
    if not required_signals:
        return False
    try:
        cluster = _v2._pre.resolution_cluster(required_signals)
        if not cluster:
            return False
        query = _v2._pre.build_resolution_query(cluster)
        prompt = _v2._pre.build_resolution_prompt(
            search_window=search_window,
            cluster=cluster,
            archive=archive,
        )
        contract = _P3A._request_contract(
            model=model,
            query=query,
            prompt=prompt,
            cluster=cluster,
        )
    except Exception:
        return False
    return str(journal.get("request_contract_sha256") or "") == _P3A.sha256_value(contract)


def _run_required_legacy_durable(
    result: dict[str, Any],
    *,
    publication_date: str,
    required_signals: list[dict[str, Any]],
    kwargs: dict[str, Any],
    original_maximum: int,
    original_recalculate: Any,
) -> dict[str, Any]:
    """Resume/start required legacy resolution only through P3a's slot guard."""
    if original_maximum < 7 or not required_signals:
        return result
    if set(result.get("checked_directions") or ()) != set(_v2._pre.AUDIT_DIRECTION_IDS):
        return result

    original_recalculate(result, 7)
    budget = result.get("search_budget")
    remaining = int(budget.get("remaining_calls", 0) or 0) if isinstance(budget, dict) else 0

    # Existing legacy journals may be request_started/response_saved/processed.
    # Their durable state, rather than recomputed remaining_calls, owns recovery.
    try:
        journal = _P3A.load_journal(Path(STATE_DIR), publication_date)
    except Exception:
        journal = None
    legacy_journal = bool(
        isinstance(journal, dict)
        and _journal_matches_current_legacy_intent(
            journal=journal,
            model=str(kwargs.get("model") or ""),
            search_window=kwargs.get("search_window") or {},
            archive=kwargs.get("archive") or {},
            required_signals=required_signals,
        )
    )
    if remaining < 1 and not legacy_journal:
        return result

    _P3A.STATE_DIR = STATE_DIR
    resolved = _P3A._run_resolution(
        plan=result,
        signals=required_signals,
        api_key=str(kwargs.get("api_key") or ""),
        model=str(kwargs.get("model") or ""),
        search_window=kwargs.get("search_window") or {},
        archive=kwargs.get("archive") or {},
        maximum_web_search_calls=7,
    )

    # Required legacy owns the slot. P3b stays diagnostic-only/deferred even when
    # the protected legacy resolution found a candidate or definitive negative.
    try:
        signal = select_p3b_signal(_p3b_signals(publication_date))
    except Exception:
        signal = None
    if signal is None:
        return resolved
    return _v2._annotation(
        resolved,
        status="deferred",
        reason="existing required unresolved/unverified resolution has slot priority",
        signal=signal,
        disposition="unresolved_deferred",
    )


def execute_audit_plan(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    publication_date = _v2._valid_publication_date(kwargs.get("publication_date"))
    journal, invalid_journal = _v4._load_optional_journal(publication_date)
    required_before = (
        list(_v2._pre._required_signals(publication_date))
        if publication_date
        else []
    )
    search_window = kwargs.get("search_window") or {}
    archive = kwargs.get("archive") or {}
    model = str(kwargs.get("model") or "")

    legacy_journal = bool(
        required_before
        and isinstance(journal, dict)
        and _journal_matches_current_legacy_intent(
            journal=journal,
            model=model,
            search_window=search_window,
            archive=archive,
            required_signals=required_before,
        )
    )

    released_for_required = False
    if (
        publication_date
        and required_before
        and isinstance(journal, dict)
        and not legacy_journal
        and _v4._journal_matches_current_p3b_intent(
            publication_date=publication_date,
            journal=journal,
            model=model,
            search_window=search_window,
            archive=archive,
        )
        and _v4._release_unstarted_reservation_for_required(publication_date, journal)
    ):
        journal = None
        released_for_required = True

    # Required legacy may take the seventh slot only when there is no ambiguous
    # foreign/P3b owner, or when it is resuming its own durable journal.
    protected_legacy_allowed = bool(
        publication_date
        and required_before
        and not invalid_journal
        and (journal is None or legacy_journal)
    )
    slot_occupied_or_unknown = invalid_journal or (
        isinstance(journal, dict) and not legacy_journal
    )

    call_kwargs = dict(kwargs)
    original_maximum = int(call_kwargs.get("maximum_web_search_calls", 7) or 7)

    # Never let the delegated compatibility scheduler spend slot seven while a
    # required legacy obligation is pending. It can reset the hook during prior
    # preparation. We run six mandatory passes there, then invoke the protected
    # P3a resolver directly for the seventh durable operation.
    if slot_occupied_or_unknown or protected_legacy_allowed:
        call_kwargs["maximum_web_search_calls"] = min(original_maximum, 6)

    original_recalculate = _v2._pre._recalculate_budget

    def preserving_recalculate(plan: dict[str, Any], maximum_calls: int) -> Any:
        budget = plan.get("search_budget") if isinstance(plan, dict) else None
        if isinstance(budget, dict):
            consumed = max(
                int(budget.get("completed_calls", 0) or 0),
                int(budget.get("effective_consumed_calls", 0) or 0),
            )
            if consumed >= 7:
                plan[_PRE_RECALC_BUDGET_KEY] = copy.deepcopy(budget)
        return original_recalculate(plan, maximum_calls)

    _v2._pre._recalculate_budget = preserving_recalculate
    try:
        result = _v3.execute_audit_plan(*args, **call_kwargs)
        if not isinstance(result, dict):
            return result

        if protected_legacy_allowed and publication_date:
            result = _run_required_legacy_durable(
                result,
                publication_date=publication_date,
                required_signals=required_before,
                kwargs=dict(kwargs),
                original_maximum=original_maximum,
                original_recalculate=original_recalculate,
            )
        elif slot_occupied_or_unknown:
            _v4._seal_existing_optional_slot_budget(
                result,
                original_maximum=original_maximum,
                recalculate=original_recalculate,
            )

        result.pop(_PRE_RECALC_BUDGET_KEY, None)
        return result
    finally:
        _v2._pre._recalculate_budget = original_recalculate
        _pull_p3b_runtime_state()


def main() -> int:
    historical_main = _v2._v1._P3A_MAIN
    _sync_p3b_public_hooks()
    original_execute = _v2._v1._pre.execute_audit_plan
    _v2._v1._pre.execute_audit_plan = execute_audit_plan
    try:
        return int(historical_main())
    finally:
        _v2._v1._pre.execute_audit_plan = original_execute
        _pull_p3b_runtime_state()


_archive_exact_event = _archive_exact_event_v5
_install_v5_bindings()


if __name__ == "__main__":
    raise SystemExit(main())
