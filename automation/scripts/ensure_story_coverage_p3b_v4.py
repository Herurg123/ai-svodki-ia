#!/usr/bin/env python3
"""P3b v4 runtime guard for hardened CLI and durable optional-slot ownership.

The substantive exact-page binding remains in v2 and compatibility bridging in
v3. This layer protects orchestration boundaries around durable slot ownership,
required-signal priority, exhausted Coverage budget, and exact archive admission.
For mutable product lifecycles, archive semantic dedupe additionally requires an
exact event-detail fingerprint so distinct updates of one model are not collapsed
merely because organization, version, lifecycle, or generic update words match.
The CLI and direct callers execute the same hardened path.
"""
from __future__ import annotations

import copy
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

from coverage_slot_guard import (
    CoverageSlotError,
    journal_path,
    load_journal,
    response_path,
    sha256_value,
)
import weak_source_exact_binding_v2 as _exact_binding

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
_PRE_RECALC_BUDGET_KEY = "_p3b_pre_recalc_budget"
_ARCHIVE_MUTABLE_ACTIONS = frozenset({"update", "upgrade", "rollout"})
_ARCHIVE_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.+-][a-z0-9]+)*", re.I)
_ARCHIVE_GENERIC_TOKENS = frozenset({
    "a", "add", "added", "adds", "an", "and", "ai", "announced", "announces",
    "announcement", "are", "as", "at", "bring", "brings", "brought", "by",
    "enable", "enabled", "enables", "expand", "expanded", "expands", "feature",
    "features", "for", "from", "in", "into", "introduce", "introduced",
    "introduces", "is", "its", "latest", "model", "models", "new", "now", "of",
    "official", "on", "product", "release", "released", "releases", "rollout",
    "rolled", "out", "support", "supported", "supports", "the", "to", "today",
    "update", "updated", "updates", "upgrade", "upgraded", "upgrades", "version",
    "with",
})
_V4_INTERNALS = {
    "_v3", "_v2", "_exact_binding", "_V3_PATH", "_V3_SPEC", "_V2_RUN_P3B_BINDING",
    "_PRE_RECALC_BUDGET_KEY", "_ARCHIVE_MUTABLE_ACTIONS", "_ARCHIVE_TOKEN_RE",
    "_ARCHIVE_GENERIC_TOKENS", "_V4_INTERNALS", "_sync_p3b_public_hooks",
    "_pull_p3b_runtime_state", "_archive_identity_stop_tokens",
    "_archive_discriminator_tokens", "_archive_mutable_event_detail_match",
    "_archive_exact_event_v4", "_guarded_run_p3b_binding_v2",
    "_load_optional_journal", "_journal_matches_current_p3b_intent",
    "_release_unstarted_reservation_for_required",
    "_seal_existing_optional_slot_budget",
    "_run_p3b_binding_v2", "_P3A_MAIN", "execute_audit_plan", "main",
    "__getattr__",
}


def __getattr__(name: str) -> Any:
    return getattr(_v3, name)


def _sync_p3b_public_hooks() -> None:
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
        _v3.STATE_DIR = state_dir
        _v2.STATE_DIR = state_dir
        if hasattr(_v2, "_v1"):
            _v2._v1.STATE_DIR = state_dir
    _v2._run_p3b_binding_v2 = _guarded_run_p3b_binding_v2


def _pull_p3b_runtime_state() -> None:
    _v3._pull_p3b_runtime_state()
    for name in ("_LAST_RECALL_SENTINEL", "_LAST_AGENCY_RESCUE"):
        if hasattr(_v3, name):
            globals()[name] = getattr(_v3, name)


def _archive_identity_stop_tokens(signal: dict[str, Any]) -> set[str]:
    stops = set(_ARCHIVE_GENERIC_TOKENS)
    values = [signal.get("organization")]
    values.extend(signal.get("product_version_anchors") or [])
    values.extend(signal.get("lifecycle_action_anchors") or [])
    for value in values:
        stops.update(
            token.casefold()
            for token in _ARCHIVE_TOKEN_RE.findall(str(value or ""))
        )
    return stops


def _archive_discriminator_tokens(text: Any, signal: dict[str, Any]) -> set[str]:
    stops = _archive_identity_stop_tokens(signal)
    return {
        token.casefold()
        for token in _ARCHIVE_TOKEN_RE.findall(str(text or ""))
        if len(token) > 1 and token.casefold() not in stops
    }


def _archive_mutable_event_detail_match(
    candidate: dict[str, Any], story: dict[str, Any], signal: dict[str, Any]
) -> bool:
    candidate_text = " ".join(
        str(candidate.get(key) or "") for key in ("title", "event_summary")
    )
    story_text = " ".join(
        str(story.get(key) or "") for key in ("headline", "event_summary")
    )
    candidate_tokens = _archive_discriminator_tokens(candidate_text, signal)
    story_tokens = _archive_discriminator_tokens(story_text, signal)
    if len(candidate_tokens) < 2 or len(story_tokens) < 2:
        return False
    return candidate_tokens == story_tokens


def _archive_exact_event_v4(
    archive: dict[str, Any], candidate: dict[str, Any], signal: dict[str, Any]
) -> bool:
    """Require independent duplicate proof, especially for mutable model updates.

    Exact source URL remains conclusive. Semantic matching first requires the
    existing strict organization/version/lifecycle identity. Mutable lifecycle
    actions can recur for one model, so their core identity is insufficient on
    its own; normalized event-specific discriminator sets must match exactly.
    Partial lexical overlap is deliberately non-terminal and does not block a
    fresh candidate.
    """
    source = candidate.get("primary_source")
    candidate_url = str(source.get("url") or "").strip() if isinstance(source, dict) else ""
    actions = {
        str(item or "").strip().casefold()
        for item in signal.get("lifecycle_action_anchors") or []
        if str(item or "").strip()
    }
    mutable = bool(actions & _ARCHIVE_MUTABLE_ACTIONS)

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
            surface = " | ".join(
                str(story.get(key) or "")
                for key in ("headline", "organization", "event_type")
            )
            try:
                matched, _reason = _exact_binding.exact_event_identity(surface, signal)
            except Exception:
                matched = False
            if not matched:
                continue
            if not mutable:
                return True
            if _archive_mutable_event_detail_match(candidate, story, signal):
                return True
    return False


def _load_optional_journal(publication_date: str | None) -> tuple[dict[str, Any] | None, bool]:
    if not publication_date:
        return None, False
    try:
        return load_journal(Path(STATE_DIR), publication_date), False
    except CoverageSlotError:
        return None, True


def _journal_matches_current_p3b_intent(
    *,
    publication_date: str,
    journal: dict[str, Any],
    model: str,
    search_window: dict[str, Any],
    archive: dict[str, Any],
) -> bool:
    """Prove a reserved journal is P3b before allowing priority preemption.

    Foreign/mismatched reservations remain fail-closed. The request hash is used
    only for intent identity here, never as a proxy for whether the slot exists
    or is already occupied.
    """
    if str(journal.get("state") or "") != "reserved":
        return False
    try:
        signal = _v2.select_p3b_signal(_v2._p3b_signals(publication_date))
        if signal is None:
            return False
        hashes = _v2._p3b_contract_hashes(
            signal=signal,
            model=model,
            search_window=search_window,
            archive=archive,
        )
    except Exception:
        return False
    return str(journal.get("request_contract_sha256") or "") in hashes


def _release_unstarted_reservation_for_required(
    publication_date: str,
    journal: dict[str, Any],
) -> bool:
    if str(journal.get("state") or "") != "reserved":
        return False
    if journal.get("wire_attempt_admitted") is True:
        return False
    if journal.get("slot_consumed_or_ambiguous") is True:
        return False
    if str(journal.get("response_sha256") or "").strip():
        return False
    state_dir = Path(STATE_DIR)
    if response_path(state_dir, publication_date).exists():
        return False
    try:
        latest = load_journal(state_dir, publication_date)
    except CoverageSlotError:
        return False
    if not isinstance(latest, dict):
        return False
    if sha256_value(latest) != sha256_value(journal):
        return False
    try:
        journal_path(state_dir, publication_date).unlink()
    except FileNotFoundError:
        return False
    return True


def _seal_existing_optional_slot_budget(
    result: dict[str, Any], *, original_maximum: int, recalculate: Any,
) -> None:
    recalculate(result, max(7, original_maximum))
    _v2._v1._p3b_force_consumed(result)


def _guarded_run_p3b_binding_v2(*, plan: dict[str, Any], publication_date: str,
                                signal: dict[str, Any], api_key: str, model: str,
                                search_window: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    preserved_budget = plan.pop(_PRE_RECALC_BUDGET_KEY, None)
    try:
        journal = load_journal(Path(STATE_DIR), publication_date)
    except CoverageSlotError:
        journal = None
    state = str((journal or {}).get("state") or "") if isinstance(journal, dict) else ""
    if state == "reserved":
        budget = plan.get("search_budget")
        remaining = int(budget.get("remaining_calls", 0) or 0) if isinstance(budget, dict) else 0
        prior_completed = 0
        if isinstance(preserved_budget, dict):
            prior_completed = max(
                int(preserved_budget.get("completed_calls", 0) or 0),
                int(preserved_budget.get("effective_consumed_calls", 0) or 0),
            )
        if remaining < 1 or prior_completed >= 7:
            base = copy.deepcopy(plan)
            if isinstance(preserved_budget, dict) and prior_completed >= 7:
                base["search_budget"] = copy.deepcopy(preserved_budget)
            return _v2._annotation(
                base,
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
    publication_date = _v2._valid_publication_date(kwargs.get("publication_date"))
    journal, invalid_journal = _load_optional_journal(publication_date)
    required_before = list(_v2._pre._required_signals(publication_date)) if publication_date else []
    search_window = kwargs.get("search_window") or {}
    archive = kwargs.get("archive") or {}
    model = str(kwargs.get("model") or "")
    if (
        publication_date
        and required_before
        and isinstance(journal, dict)
        and _journal_matches_current_p3b_intent(
            publication_date=publication_date,
            journal=journal,
            model=model,
            search_window=search_window,
            archive=archive,
        )
        and _release_unstarted_reservation_for_required(publication_date, journal)
    ):
        journal = None

    slot_occupied_or_unknown = invalid_journal or isinstance(journal, dict)
    call_kwargs = dict(kwargs)
    original_maximum = int(call_kwargs.get("maximum_web_search_calls", 7) or 7)
    if slot_occupied_or_unknown:
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
        if isinstance(result, dict):
            if slot_occupied_or_unknown:
                _seal_existing_optional_slot_budget(
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


_archive_exact_event = _archive_exact_event_v4
_v2._archive_exact_event = _archive_exact_event_v4
_v2._run_p3b_binding_v2 = _guarded_run_p3b_binding_v2


if __name__ == "__main__":
    raise SystemExit(main())
