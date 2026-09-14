#!/usr/bin/env python3
"""P3b v6: third independent-review hardening over preserved v5.

v6 keeps the durable request contract at VERSION=2 while separately versioning
binder evidence. It replaces unlink-based P3b->legacy preemption with an atomic
durable ownership transfer, applies binder v4 only on the active path, preserves
single-digit mutable archive detail, and refuses to reuse positive processed
snapshots produced before the active binder-evidence contract.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

from coverage_slot_guard import CoverageSlotError, load_journal, sha256_value
from coverage_slot_handoff import install_locked_slot_transitions, transfer_reserved_slot
import weak_source_exact_binding_v4 as _binding_v4

_V5_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v5.py")
_V5_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_p3b_v5_preserved", _V5_PATH)
assert _V5_SPEC and _V5_SPEC.loader
_v5 = importlib.util.module_from_spec(_V5_SPEC)
sys.modules[_V5_SPEC.name] = _v5
_V5_SPEC.loader.exec_module(_v5)

for _name in dir(_v5):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_v5, _name)

_v4 = _v5._v4
_v3 = _v5._v3
_v2 = _v5._v2
_P3A = _v5._P3A
_PRE_RECALC_BUDGET_KEY = _v5._PRE_RECALC_BUDGET_KEY

install_locked_slot_transitions()

_exact_binding = _binding_v4
build_p3b_query = _binding_v4.build_query
candidate_exact_binding = _binding_v4.candidate_exact_binding
qualifying_p3b_signals = _binding_v4.qualifying_signals
rejection_exact_terminal_binding = _binding_v4.rejection_exact_terminal_binding
select_p3b_signal = _binding_v4.select_signal
extract_authoritative_event_surface = _binding_v4.extract_authoritative_event_surface
P3B_EXACT_BINDING_VERSION = _binding_v4.VERSION
P3B_MODE = _binding_v4.MODE
P3B_BINDER_EVIDENCE_VERSION = _binding_v4.EVIDENCE_VERSION

_V6_SEMANTIC_EXPORTS = {
    "_exact_binding", "build_p3b_query", "candidate_exact_binding",
    "qualifying_p3b_signals", "rejection_exact_terminal_binding",
    "select_p3b_signal", "extract_authoritative_event_surface",
    "P3B_EXACT_BINDING_VERSION", "P3B_MODE", "P3B_BINDER_EVIDENCE_VERSION",
    "_archive_exact_event", "_process_p3b_payload_v2",
}
_V6_INTERNALS = {
    "_v5", "_v4", "_v3", "_v2", "_P3A", "_binding_v4", "_V5_PATH", "_V5_SPEC",
    "_PRE_RECALC_BUDGET_KEY", "_V6_SEMANTIC_EXPORTS", "_V6_INTERNALS",
    "_sync_p3b_public_hooks", "_pull_p3b_runtime_state", "_stamp_binder_evidence",
    "_archive_discriminator_sequence", "_archive_mutable_event_detail_match_v6",
    "_archive_exact_event_v6", "_with_v4_processing", "_process_p3b_payload_v2",
    "_processed_positive_snapshot_is_stale", "_run_p3b_binding_v4",
    "_priority_deferred_runner", "_journal_matches_current_legacy_intent_v6",
    "_legacy_contract", "_transfer_p3b_to_legacy", "_after_handoff_transfer",
    "_run_handed_off_required_legacy", "execute_audit_plan", "main", "__getattr__",
}


def __getattr__(name: str) -> Any:
    return getattr(_v5, name)


def _sync_p3b_public_hooks() -> None:
    """Mirror ordinary monkeypatch seams without exporting active v6 semantics."""
    state_dir = globals().get("STATE_DIR")
    for name, value in list(globals().items()):
        if (
            name in _V6_INTERNALS
            or name in _V6_SEMANTIC_EXPORTS
            or (name.startswith("__") and name.endswith("__"))
        ):
            continue
        try:
            exists = hasattr(_v5, name)
        except Exception:
            exists = False
        if exists:
            setattr(_v5, name, value)
    if state_dir is not None:
        _v5.STATE_DIR = state_dir
    _v5._sync_p3b_public_hooks()


def _pull_p3b_runtime_state() -> None:
    _v5._pull_p3b_runtime_state()
    for name in ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE"):
        if hasattr(_v5, name):
            globals()[name] = getattr(_v5, name)


def _stamp_binder_evidence(result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    diagnostic = result.get(_v2._P3B_DIAGNOSTIC_KEY)
    if isinstance(diagnostic, dict):
        diagnostic["binder_evidence_version"] = P3B_BINDER_EVIDENCE_VERSION
        diagnostic["binder_implementation"] = "weak_source_exact_binding_v4"
    return result


def _archive_discriminator_sequence(text: Any, signal: dict[str, Any]) -> tuple[str, ...]:
    stops = _v4._archive_identity_stop_tokens(signal)
    return tuple(
        token.casefold()
        for token in _v4._ARCHIVE_TOKEN_RE.findall(str(text or ""))
        if (len(token) > 1 or token.isdigit()) and token.casefold() not in stops
    )


def _archive_mutable_event_detail_match_v6(
    candidate: dict[str, Any], story: dict[str, Any], signal: dict[str, Any]
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


def _archive_exact_event_v6(
    archive: dict[str, Any], candidate: dict[str, Any], signal: dict[str, Any]
) -> bool:
    source = candidate.get("primary_source")
    candidate_url = str(source.get("url") or "").strip() if isinstance(source, dict) else ""
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
                _binding_v4.normalized_org(organization)
                != _binding_v4.normalized_org(signal_org)
            ):
                continue
            event_claim = " ".join(part for part in (organization, headline) if part)
            surface = " | ".join(part for part in (event_claim, event_type) if part)
            try:
                matched, _reason = _binding_v4.exact_event_identity(surface, signal)
            except Exception:
                matched = False
            if not matched:
                continue
            if not mutable:
                return True
            if _archive_mutable_event_detail_match_v6(candidate, story, signal):
                return True
    return False


def _with_v4_processing(callback: Callable[[], Any]) -> Any:
    """Install binder v4 and evidence stamping only during the active processing call."""
    saved = {
        "candidate_exact_binding": _v2.candidate_exact_binding,
        "rejection_exact_terminal_binding": _v2.rejection_exact_terminal_binding,
        "extract_authoritative_event_surface": _v2.extract_authoritative_event_surface,
        "_archive_exact_event": _v2._archive_exact_event,
        "_process_p3b_payload_v2": _v2._process_p3b_payload_v2,
    }

    def active_process(*args: Any, **kwargs: Any) -> Any:
        return _stamp_binder_evidence(saved["_process_p3b_payload_v2"](*args, **kwargs))

    try:
        _v2.candidate_exact_binding = _binding_v4.candidate_exact_binding
        _v2.rejection_exact_terminal_binding = _binding_v4.rejection_exact_terminal_binding
        _v2.extract_authoritative_event_surface = _binding_v4.extract_authoritative_event_surface
        _v2._archive_exact_event = _archive_exact_event_v6
        _v2._process_p3b_payload_v2 = active_process
        return callback()
    finally:
        for name, value in saved.items():
            setattr(_v2, name, value)


def _process_p3b_payload_v2(*args: Any, **kwargs: Any) -> Any:
    return _with_v4_processing(lambda: _v2._process_p3b_payload_v2(*args, **kwargs))


def _processed_positive_snapshot_is_stale(publication_date: str) -> bool:
    try:
        journal = load_journal(Path(STATE_DIR), publication_date)
    except CoverageSlotError:
        return False
    if not isinstance(journal, dict) or str(journal.get("state") or "") != "processed":
        return False
    saved = journal.get("processed_snapshot")
    if not isinstance(saved, dict):
        return False
    diagnostic = saved.get(_v2._P3B_DIAGNOSTIC_KEY)
    if not isinstance(diagnostic, dict):
        return bool(saved.get("candidates"))
    positive = (
        diagnostic.get("status") == "bound_candidate"
        or diagnostic.get("disposition") == "positive_exact_binding"
        or int(diagnostic.get("candidate_count", 0) or 0) > 0
        or any(
            isinstance(item, dict)
            and item.get("audit_direction") == "weak_source_exact_binding"
            for item in saved.get("candidates") or []
        )
    )
    if not positive:
        return False
    return int(diagnostic.get("binder_evidence_version", 0) or 0) != P3B_BINDER_EVIDENCE_VERSION


def _run_p3b_binding_v4(*args: Any, **kwargs: Any) -> Any:
    publication_date = str(kwargs.get("publication_date") or "")
    if publication_date and _processed_positive_snapshot_is_stale(publication_date):
        plan = kwargs.get("plan") if isinstance(kwargs.get("plan"), dict) else {}
        signal = kwargs.get("signal") if isinstance(kwargs.get("signal"), dict) else None
        result = _v2._annotation(
            plan,
            status="unresolved",
            reason=(
                "processed positive optional-slot proof predates the active binder evidence "
                "version; automatic reuse is forbidden without a new slot"
            ),
            signal=signal,
            query=build_p3b_query(signal or {}),
            disposition="unresolved_deferred",
            slot_state="processed",
        )
        _v2._v1._p3b_force_consumed(result)
        return _stamp_binder_evidence(result)
    return _with_v4_processing(lambda: _v4._guarded_run_p3b_binding_v2(*args, **kwargs))


def _priority_deferred_runner(*args: Any, **kwargs: Any) -> dict[str, Any]:
    plan = kwargs.get("plan") if isinstance(kwargs.get("plan"), dict) else {}
    signal = kwargs.get("signal") if isinstance(kwargs.get("signal"), dict) else None
    return _stamp_binder_evidence(
        _v2._annotation(
            plan,
            status="deferred",
            reason="existing required unresolved/unverified resolution has slot priority",
            signal=signal,
            query=build_p3b_query(signal or {}),
            disposition="unresolved_deferred",
            slot_state="reserved",
        )
    )


def _journal_matches_current_legacy_intent_v6(
    *,
    journal: dict[str, Any],
    model: str,
    search_window: dict[str, Any],
    archive: dict[str, Any],
    required_signals: list[dict[str, Any]],
) -> bool:
    if str(journal.get("owner") or "") != str(_P3A.OPTIONAL_SLOT_OWNER):
        return False
    if str(journal.get("search_window_sha256") or "") != sha256_value(search_window):
        return False
    return _v5._journal_matches_current_legacy_intent(
        journal=journal,
        model=model,
        search_window=search_window,
        archive=archive,
        required_signals=required_signals,
    )


def _legacy_contract(
    *,
    plan: dict[str, Any],
    required_signals: list[dict[str, Any]],
    model: str,
    search_window: dict[str, Any],
    archive: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    try:
        cluster = _v2._pre.resolution_cluster(required_signals)
        if not cluster:
            return None
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
        bundle_identity = _P3A._bundle_identity(plan)
    except Exception:
        return None
    return contract, bundle_identity


def _transfer_p3b_to_legacy(
    *,
    plan: dict[str, Any],
    publication_date: str,
    expected_journal: dict[str, Any],
    required_signals: list[dict[str, Any]],
    model: str,
    search_window: dict[str, Any],
    archive: dict[str, Any],
) -> Any:
    target = _legacy_contract(
        plan=plan,
        required_signals=required_signals,
        model=model,
        search_window=search_window,
        archive=archive,
    )
    if target is None:
        return None
    contract, bundle_identity = target
    return transfer_reserved_slot(
        state_dir=Path(STATE_DIR),
        publication_date=publication_date,
        expected_journal=expected_journal,
        target_owner=_P3A.OPTIONAL_SLOT_OWNER,
        target_search_window=search_window,
        target_request_contract=contract,
        target_bundle_identity=bundle_identity,
    )


def _after_handoff_transfer(_reservation: Any) -> None:
    """Deterministic crash-test seam after durable ownership commit, before transport."""
    return None


def _run_handed_off_required_legacy(
    plan: dict[str, Any],
    *,
    required_signals: list[dict[str, Any]],
    kwargs: dict[str, Any],
    original_maximum: int,
    original_recalculate: Any,
) -> dict[str, Any]:
    # v5 already fixed publication-date ContextVar lifetime and durable P3a call.
    return _v5._run_handed_off_required_legacy(
        plan,
        required_signals=required_signals,
        kwargs=kwargs,
        original_maximum=original_maximum,
        original_recalculate=original_recalculate,
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
    try:
        active_p3b_signal = (
            select_p3b_signal(_p3b_signals(publication_date))
            if publication_date
            else None
        )
    except Exception:
        active_p3b_signal = None

    legacy_journal = bool(
        required_before
        and isinstance(journal, dict)
        and _journal_matches_current_legacy_intent_v6(
            journal=journal,
            model=model,
            search_window=search_window,
            archive=archive,
            required_signals=required_before,
        )
    )
    p3b_handoff = bool(
        publication_date
        and required_before
        and isinstance(journal, dict)
        and not legacy_journal
        and _v5._journal_matches_current_p3b_intent_v5(
            publication_date=publication_date,
            journal=journal,
            model=model,
            search_window=search_window,
            archive=archive,
            signal=active_p3b_signal,
        )
    )
    slot_occupied_or_unknown = invalid_journal or isinstance(journal, dict)

    call_kwargs = dict(kwargs)
    original_maximum = int(call_kwargs.get("maximum_web_search_calls", 7) or 7)
    if slot_occupied_or_unknown:
        call_kwargs["maximum_web_search_calls"] = min(original_maximum, 6)

    original_recalculate = _v2._pre._recalculate_budget
    original_runner = _v2._run_p3b_binding_v2

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
    _v2._run_p3b_binding_v2 = _priority_deferred_runner if p3b_handoff else _run_p3b_binding_v4
    try:
        result = _v3.execute_audit_plan(*args, **call_kwargs)
        if not isinstance(result, dict):
            return result

        handoff_recovery = legacy_journal
        if p3b_handoff and publication_date and isinstance(journal, dict):
            transferred = _transfer_p3b_to_legacy(
                plan=result,
                publication_date=publication_date,
                expected_journal=journal,
                required_signals=required_before,
                model=model,
                search_window=search_window,
                archive=archive,
            )
            if transferred is not None:
                _after_handoff_transfer(transferred)
                handoff_recovery = True
            else:
                try:
                    latest = load_journal(Path(STATE_DIR), publication_date)
                except CoverageSlotError:
                    latest = None
                handoff_recovery = bool(
                    isinstance(latest, dict)
                    and _journal_matches_current_legacy_intent_v6(
                        journal=latest,
                        model=model,
                        search_window=search_window,
                        archive=archive,
                        required_signals=required_before,
                    )
                )
                if not handoff_recovery:
                    _v4._seal_existing_optional_slot_budget(
                        result,
                        original_maximum=original_maximum,
                        recalculate=original_recalculate,
                    )
                    result = _v2._annotation(
                        result,
                        status="deferred",
                        reason=(
                            "required resolution could not atomically acquire the optional slot; "
                            "changed or consumed ownership fails closed"
                        ),
                        signal=active_p3b_signal,
                        disposition="unresolved_deferred",
                        slot_state=str((latest or {}).get("state") or "") if isinstance(latest, dict) else None,
                    )

        if handoff_recovery:
            result = _run_handed_off_required_legacy(
                result,
                required_signals=required_before,
                kwargs=dict(kwargs),
                original_maximum=original_maximum,
                original_recalculate=original_recalculate,
            )
        elif slot_occupied_or_unknown and not p3b_handoff:
            _v4._seal_existing_optional_slot_budget(
                result,
                original_maximum=original_maximum,
                recalculate=original_recalculate,
            )

        result.pop(_PRE_RECALC_BUDGET_KEY, None)
        return result
    finally:
        _v2._pre._recalculate_budget = original_recalculate
        _v2._run_p3b_binding_v2 = original_runner
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


_archive_exact_event = _archive_exact_event_v6


if __name__ == "__main__":
    raise SystemExit(main())
