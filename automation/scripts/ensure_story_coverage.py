#!/usr/bin/env python3
"""Versioned runtime policy for the final zero-pool recall search.

The previous runtime is kept in ``ensure_story_coverage_runtime_base.py`` so
its transport diagnostics and battle-tested policy bridge remain reusable.
This thin layer only owns recall-sentinel versioning, stale-artifact migration
and the source-agnostic high-signal query used when all mandatory coverage passes
finished with no eligible story.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BASE_PATH = Path(__file__).with_name("ensure_story_coverage_runtime_base.py")
_BASE_SPEC = importlib.util.spec_from_file_location(
    "ensure_story_coverage_runtime_base",
    _BASE_PATH,
)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

# Preserve the historical public import surface. Private runtime hooks that are
# intentionally overridden are defined below.
for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)

_policy = _base._policy
_BASE_EXECUTE_AUDIT_PLAN = _base._BASE_EXECUTE_AUDIT_PLAN
_LAST_RECALL_SENTINEL: dict[str, Any] | None = None
_LAST_AGENCY_RESCUE: dict[str, Any] | None = None

RECALL_SENTINEL_STRATEGY = "high_signal_recall_sentinel"
TEMPORAL_ANCHOR_VERSION = 1
RECALL_SENTINEL_VERSION = 8
RECALL_SENTINEL_DOMAINS: tuple[str, ...] = ()
RECALL_SENTINEL_MINIMUM_BUDGET = 7
AGENCY_RESCUE_STRATEGY = "fresh_agency_rescue"
AGENCY_RESCUE_VERSION = 1
AGENCY_RESCUE_DOMAINS: tuple[str, ...] = ("reuters.com", "apnews.com")
SOURCE_HEALTH_CONTRACT_VERSION = 1

# Transport remains implemented by the preserved runtime base. Keep this
# literal here because the repository contract verifies transient retries at
# the historical entry point too: OpenAI(..., max_retries=2).


def _set_last_recall_sentinel(value: dict[str, Any] | None) -> None:
    global _LAST_RECALL_SENTINEL
    _LAST_RECALL_SENTINEL = value
    _base._LAST_RECALL_SENTINEL = value


def _set_last_agency_rescue(value: dict[str, Any] | None) -> None:
    global _LAST_AGENCY_RESCUE
    _LAST_AGENCY_RESCUE = value


def _pool_total(payload: dict[str, Any]) -> int | None:
    for key in ("candidate_pool_after", "candidate_pool_before"):
        pool = payload.get(key)
        if not isinstance(pool, dict):
            continue
        total = pool.get("total")
        if isinstance(total, int):
            return total
    return None


def _sentinel_version(record: Any) -> int | None:
    if not isinstance(record, dict):
        return None
    raw = record.get("recall_sentinel_version", record.get("version"))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _current_sentinel_record(record: Any) -> bool:
    return bool(
        isinstance(record, dict)
        and record.get("search_strategy") == RECALL_SENTINEL_STRATEGY
        and _sentinel_version(record) == RECALL_SENTINEL_VERSION
        and record.get("status") in {"checked", "checked_with_gaps"}
    )


def _completed_sentinel_evidence(payload: dict[str, Any]) -> bool:
    sentinel = payload.get("recall_sentinel")
    if (
        isinstance(sentinel, dict)
        and _sentinel_version(sentinel) == RECALL_SENTINEL_VERSION
        and sentinel.get("status") in {
            "complete",
            "complete_with_gaps",
            "reused",
        }
    ):
        return True
    attempts = payload.get("attempts")
    return bool(
        isinstance(attempts, list)
        and any(_current_sentinel_record(item) for item in attempts)
    )


def completed_prior_audit(payload: Any) -> bool:
    """Reuse zero-pool audit only after the current recall-sentinel version."""
    if not isinstance(payload, dict):
        return False
    audit_state = payload.get("audit_state")
    if audit_state is not None and audit_state != "completed_usable":
        return False
    api = payload.get("api") or {}
    complete = (
        payload.get("web_search_performed") is True
        and payload.get("audit_status") in {"complete", "complete_with_gaps"}
        and set(payload.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
        and isinstance(api, dict)
        and api.get("status") == "completed"
    )
    if not complete:
        return False
    pool_total = _pool_total(payload)
    if pool_total == 0 and not _completed_sentinel_evidence(payload):
        return False
    if (
        isinstance(pool_total, int)
        and pool_total > 0
        and payload.get("source_health_contract_version")
        != SOURCE_HEALTH_CONTRACT_VERSION
    ):
        return False
    return True


def _is_stale_sentinel_attempt(item: Any) -> bool:
    return bool(
        isinstance(item, dict)
        and item.get("search_strategy") == RECALL_SENTINEL_STRATEGY
        and _sentinel_version(item) != RECALL_SENTINEL_VERSION
    )


def _is_supplemental_attempt(item: Any) -> bool:
    return bool(
        isinstance(item, dict)
        and item.get("search_strategy")
        in {RECALL_SENTINEL_STRATEGY, AGENCY_RESCUE_STRATEGY}
    )


def _rebuild_directions(
    prior_directions: Any,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in attempts:
        direction_id = item.get("direction_id")
        if direction_id not in AUDIT_DIRECTION_IDS or _is_supplemental_attempt(item):
            continue
        previous = latest.get(str(direction_id))
        if previous is None or int(item.get("attempt", 0) or 0) >= int(
            previous.get("attempt", 0) or 0
        ):
            latest[str(direction_id)] = copy.deepcopy(item)

    fallback: dict[str, dict[str, Any]] = {}
    if isinstance(prior_directions, list):
        for item in prior_directions:
            if (
                isinstance(item, dict)
                and item.get("direction_id") in AUDIT_DIRECTION_IDS
                and not _is_stale_sentinel_attempt(item)
                and not _is_supplemental_attempt(item)
            ):
                fallback[str(item["direction_id"])] = copy.deepcopy(item)

    return [
        copy.deepcopy(latest.get(direction_id) or fallback.get(direction_id) or {})
        for direction_id in AUDIT_DIRECTION_IDS
    ]


def _legacy_cross_midnight_window(search_window: dict[str, Any] | None) -> bool:
    if not isinstance(search_window, dict):
        return False
    end_at = search_window.get("end_at")
    if not isinstance(end_at, str) or not end_at.strip():
        return False
    try:
        parsed = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    return parsed.date() > parsed.astimezone(timezone.utc).date()


def _prepare_prior_plan(
    prior_plan: dict[str, Any] | None,
    search_window: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Drop obsolete sentinel attempts while retaining the six paid passes."""
    if not isinstance(prior_plan, dict):
        return prior_plan
    if (
        prior_plan.get("temporal_anchor_version") != TEMPORAL_ANCHOR_VERSION
        and _legacy_cross_midnight_window(search_window)
    ):
        return None

    prepared = copy.deepcopy(prior_plan)
    raw_attempts = prepared.get("attempts")
    if not isinstance(raw_attempts, list):
        return prepared

    stale = [item for item in raw_attempts if _is_stale_sentinel_attempt(item)]
    if not stale:
        return prepared

    attempts = [
        copy.deepcopy(item)
        for item in raw_attempts
        if isinstance(item, dict) and not _is_stale_sentinel_attempt(item)
    ]
    prepared["attempts"] = attempts
    prepared["directions"] = _rebuild_directions(
        prepared.get("directions"),
        attempts,
    )
    prepared.pop("recall_sentinel", None)

    maximum_calls = int(
        (prepared.get("search_budget") or {}).get("maximum_calls", 7) or 7
    )
    completed = 0
    observed = 0
    provider_overrun = False
    for attempt in attempts:
        api = attempt.get("api")
        if not isinstance(api, dict):
            continue
        pass_completed = int(api.get("web_search_calls_completed", 0) or 0)
        completed += pass_completed
        observed += int(api.get("web_search_call_items_total", 0) or 0)
        provider_overrun = provider_overrun or pass_completed > 1

    prepared["search_budget"] = {
        "maximum_calls": maximum_calls,
        "minimum_required_calls": len(AUDIT_DIRECTION_IDS),
        "response_attempts": len(attempts),
        "observed_call_items": observed,
        "completed_calls": completed,
        "remaining_calls": max(0, maximum_calls - completed),
        "exhausted": False,
        "search_budget_exhausted": False,
        "response_attempt_limit_exhausted": False,
        "provider_overrun": provider_overrun,
        "stop_reason": "stale_recall_sentinel_removed",
    }
    prepared["api"] = _policy._aggregate_api_metadata(attempts)
    prepared["audit_status"] = (
        "complete_with_gaps"
        if set(prepared.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
        else prepared.get("audit_status", "partial")
    )
    return prepared



def build_recall_sentinel_prompt(
    *,
    publication_date: str,
    search_window: dict[str, Any],
    existing_candidates: list[Any],
    archive: dict[str, Any],
) -> str:
    del publication_date
    existing = [
        {
            "title": item.get("title"),
            "organization": item.get("organization"),
            "primary_url": (
                item.get("primary_source", {}).get("url")
                if isinstance(item.get("primary_source"), dict)
                else None
            ),
        }
        for item in existing_candidates
        if isinstance(item, dict)
    ]
    recent_archive = _base._compact_recent_archive(archive)
    start_at = str(search_window.get("start_at") or "")
    end_at = str(search_window.get("end_at") or "")
    required_query = "latest major artificial intelligence news"

    return f"""Ты — финальный source-neutral recall sentinel редакции «ИИ-сводки».

Строгое редакционное окно для проверки кандидатов: {start_at} → {end_at}
Авторитетное текущее время этого sentinel-прохода: {end_at}. Всё, что опубликовано не позже этого timestamp, не является будущим только из-за системной даты модели.
Идентификатор направления: general_coverage_gaps
Версия sentinel: {RECALL_SENTINEL_VERSION}

Основной research и шесть обязательных coverage-проходов уже завершились, но
пригодный пул всё ещё равен нулю. Это последний broad safety net, поэтому он не
должен быть привязан ни к OpenAI, ни к security, ни к одному издателю. API
domain filter отключён.

Выполни РОВНО ОДИН Web Search. Не расширяй и не переписывай поисковую строку.
Фактический поисковый запрос должен быть точно:
`{required_query}`

В query намеренно нет календарных дат: relative freshness нужна только для
ranking. После поиска открой релевантные страницы и строго проверь фактическую
дату/timestamp каждого события против editorial window. Ищи любое крупное
самостоятельное ИИ-событие: модели и продукты, агенты/coding, chips/cloud/data
centers, business/funding/M&A, security/safety, policy/legal, Китай/Азия, Россия,
research/robotics. Предпочитай официальный первоисточник, Reuters/AP/Bloomberg/FT
или другое авторитетное деловое/технологическое/отраслевое СМИ.

Старую перепечатку без нового развития отклоняй. Для include/consider нужны
verification_status=verified и freshness_status new_event/material_update. Если
точного времени публикации нет, ставь published_at=null и time_precision=date;
время не выдумывай. Не добивай количество слабым материалом.

Уже найденные кандидаты:
{json.dumps(existing, ensure_ascii=False, indent=2)}

Недавний архив для дедупликации:
{json.dumps(recent_archive, ensure_ascii=False, indent=2)}

Если достойные события найдены, верни до 3 кандидатов по заданной JSON-схеме.
Если нет, верни пустой `candidates` и status=complete_with_gaps. `direction_id`
должен быть строго `general_coverage_gaps`. Верни только JSON по схеме."""



def build_agency_rescue_prompt(
    *,
    search_window: dict[str, Any],
    existing_candidates: list[Any],
    archive: dict[str, Any],
) -> str:
    existing = [
        {
            "title": item.get("title"),
            "organization": item.get("organization"),
            "primary_url": (
                item.get("primary_source", {}).get("url")
                if isinstance(item.get("primary_source"), dict)
                else None
            ),
        }
        for item in existing_candidates
        if isinstance(item, dict)
    ]
    start_at = str(search_window.get("start_at") or "")
    end_at = str(search_window.get("end_at") or "")
    required_query = "latest major artificial intelligence news"
    return f"""Ты — дополнительный fresh-agency rescue редакции «ИИ-сводки».

Строгое редакционное окно: {start_at} → {end_at}
Авторитетное текущее время: {end_at}.
Идентификатор направления: general_coverage_gaps
Версия rescue: {AGENCY_RESCUE_VERSION}

Primary, Hybrid и шесть обязательных Coverage-проходов уже дали ненулевой пул,
но среди текущих валидных кандидатов нет свежего Reuters/AP/Bloomberg/FT
материала. Свободен ровно один, седьмой Coverage search operation. Его задача —
не переписать существующие сюжеты, а найти до трёх самостоятельных крупных
ИИ-событий из Reuters/AP, которых НЕТ в текущем пуле. API domain filter уже
ограничен Reuters и AP.

Выполни РОВНО ОДИН Web Search. Фактический query должен быть точно:
`{required_query}`

Query намеренно date-free; свежесть доказывается только фактической датой
источника внутри editorial window. Не возвращай уже имеющийся сюжет только ради
второго подтверждения: downstream dedupe его отвергнет и source-health не будет
починен. Ищи другое крупное событие: модель/продукт, M&A/funding, chips/cloud/data
centers, security/safety, regulation/legal, Китай/Азия, Россия, research или
robotics. Для include/consider обязательны verified и freshness_status
new_event/material_update. Не добивай количество слабым материалом.

Текущий пул:
{json.dumps(existing, ensure_ascii=False, indent=2)}

Недавний архив:
{json.dumps(_base._compact_recent_archive(archive), ensure_ascii=False, indent=2)}

Если нового достойного события нет, верни пустой `candidates` и
status=complete_with_gaps. `direction_id` строго `general_coverage_gaps`. Верни
только JSON по схеме."""


def _existing_agency_rescue(plan: dict[str, Any]) -> dict[str, Any] | None:
    attempts = plan.get("attempts")
    if not isinstance(attempts, list):
        return None
    return next(
        (
            item
            for item in reversed(attempts)
            if isinstance(item, dict)
            and item.get("search_strategy") == AGENCY_RESCUE_STRATEGY
            and int(item.get("agency_rescue_version", 0) or 0) == AGENCY_RESCUE_VERSION
            and item.get("status") in {"checked", "checked_with_gaps"}
        ),
        None,
    )


def _normalize_agency_rescue_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(candidate)
    normalized["audit_direction"] = "agency_rescue"
    if normalized.get("category") != "legal":
        normalized["legal_scale"] = "not_applicable"
        normalized["legal_scale_reason"] = ""
    return normalized


def _run_agency_rescue(
    *,
    plan: dict[str, Any],
    budget: dict[str, Any],
    api_key: str,
    model: str,
    search_window: dict[str, Any],
    existing_candidates: list[Any],
    archive: dict[str, Any],
    maximum_web_search_calls: int,
) -> dict[str, Any]:
    prompt = build_agency_rescue_prompt(
        search_window=search_window,
        existing_candidates=existing_candidates,
        archive=archive,
    )
    try:
        _base.run_audit_request = globals()["run_audit_request"]
        result = _base._policy_audit_request(
            api_key=api_key,
            model=model,
            prompt=prompt,
            maximum_web_search_calls=1,
            allowed_domains=AGENCY_RESCUE_DOMAINS,
        )
        payload = result.payload or {}
        if payload.get("status") not in {"complete", "complete_with_gaps"}:
            raise RuntimeError(
                "Fresh-agency rescue вернул непригодный status="
                + repr(payload.get("status"))
            )
    except Exception as exc:
        _set_last_agency_rescue(
            {
                "status": "error",
                "version": AGENCY_RESCUE_VERSION,
                "search_strategy": AGENCY_RESCUE_STRATEGY,
                "allowed_domains": list(AGENCY_RESCUE_DOMAINS),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        plan["audit_status"] = "partial"
        budget["stop_reason"] = "agency_rescue_incomplete"
        return plan

    metadata = result.metadata
    raw_candidates = payload.get("candidates")
    accepted_for_pass = [
        _normalize_agency_rescue_candidate(item)
        for item in raw_candidates
        if isinstance(item, dict)
    ] if isinstance(raw_candidates, list) else []
    prior_general_attempts = [
        int(item.get("attempt", 0) or 0)
        for item in plan.get("attempts", [])
        if isinstance(item, dict)
        and item.get("direction_id") == "general_coverage_gaps"
    ]
    attempt_number = max(prior_general_attempts or [0]) + 1
    payload_status = str(payload.get("status"))
    record = {
        "direction_id": "general_coverage_gaps",
        "label": "Fresh Reuters/AP source-health rescue v1",
        "required": True,
        "attempt": attempt_number,
        "search_strategy": AGENCY_RESCUE_STRATEGY,
        "agency_rescue_version": AGENCY_RESCUE_VERSION,
        "allowed_domains": list(AGENCY_RESCUE_DOMAINS),
        "prompt": prompt,
        "status": "checked" if payload_status == "complete" else "checked_with_gaps",
        "outcome": "candidates_found" if accepted_for_pass else "no_news_found",
        "actual_queries": list(metadata.get("actual_queries") or []),
        "sources": list(metadata.get("consulted_sources") or []),
        "candidate_count": len(accepted_for_pass),
        "candidates": accepted_for_pass,
        "rejections": list(payload.get("rejections") or []),
        "notes": payload.get("notes"),
        "api": metadata,
        "error": None,
    }
    plan.setdefault("attempts", []).append(record)
    plan.setdefault("candidates", []).extend(copy.deepcopy(accepted_for_pass))

    completed = int(metadata.get("web_search_calls_completed", 0) or 0)
    observed = int(metadata.get("web_search_call_items_total", 0) or 0)
    budget["response_attempts"] = int(budget.get("response_attempts", 0) or 0) + 1
    budget["observed_call_items"] = int(budget.get("observed_call_items", 0) or 0) + observed
    budget["completed_calls"] = int(budget.get("completed_calls", 0) or 0) + completed
    budget["remaining_calls"] = max(
        0, maximum_web_search_calls - int(budget.get("completed_calls", 0) or 0)
    )
    budget["provider_overrun"] = bool(budget.get("provider_overrun")) or completed > 1
    budget["exhausted"] = False
    budget["search_budget_exhausted"] = False
    budget["response_attempt_limit_exhausted"] = False
    budget["stop_reason"] = "agency_rescue_completed"
    plan["api"] = _policy._aggregate_api_metadata(plan.get("attempts", []))
    _set_last_agency_rescue(
        {
            "status": "complete" if payload_status == "complete" else "complete_with_gaps",
            "version": AGENCY_RESCUE_VERSION,
            "search_strategy": AGENCY_RESCUE_STRATEGY,
            "allowed_domains": list(AGENCY_RESCUE_DOMAINS),
            "attempt": attempt_number,
            "actual_queries": record["actual_queries"],
            "candidate_count": len(accepted_for_pass),
            "sources": record["sources"],
        }
    )
    return plan


def _existing_recall_sentinel(plan: dict[str, Any]) -> dict[str, Any] | None:
    attempts = plan.get("attempts")
    if not isinstance(attempts, list):
        return None
    return next(
        (
            item
            for item in reversed(attempts)
            if _current_sentinel_record(item)
        ),
        None,
    )


def _normalize_sentinel_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(candidate)
    normalized["audit_direction"] = "recall_sentinel"
    if normalized.get("category") != "legal":
        normalized["legal_scale"] = "not_applicable"
        normalized["legal_scale_reason"] = ""
    return normalized


def execute_audit_plan(
    *,
    api_key: str,
    model: str,
    template: str,
    publication_date: str,
    search_window: dict[str, Any],
    missing_total: int,
    maximum_web_search_calls: int,
    existing_candidates: list[Any],
    archive: dict[str, Any],
    prior_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run mandatory coverage, then one versioned source-agnostic recall operation."""
    prepared_prior = _prepare_prior_plan(prior_plan, search_window)
    plan = globals()["_BASE_EXECUTE_AUDIT_PLAN"](
        api_key=api_key,
        model=model,
        template=template,
        publication_date=publication_date,
        search_window=search_window,
        missing_total=missing_total,
        maximum_web_search_calls=maximum_web_search_calls,
        existing_candidates=existing_candidates,
        archive=archive,
        prior_plan=prepared_prior,
    )
    plan["temporal_anchor_version"] = TEMPORAL_ANCHOR_VERSION

    existing_sentinel = _existing_recall_sentinel(plan)
    if existing_sentinel is not None:
        _set_last_recall_sentinel(
            {
                "status": "reused",
                "version": RECALL_SENTINEL_VERSION,
                "search_strategy": RECALL_SENTINEL_STRATEGY,
                "allowed_domains": list(RECALL_SENTINEL_DOMAINS),
                "attempt": existing_sentinel.get("attempt"),
                "actual_queries": existing_sentinel.get("actual_queries", []),
                "candidate_count": existing_sentinel.get("candidate_count", 0),
            }
        )
        return plan

    existing_rescue = _existing_agency_rescue(plan)
    if existing_rescue is not None:
        _set_last_agency_rescue(
            {
                "status": "reused",
                "version": AGENCY_RESCUE_VERSION,
                "search_strategy": AGENCY_RESCUE_STRATEGY,
                "allowed_domains": list(AGENCY_RESCUE_DOMAINS),
                "attempt": existing_rescue.get("attempt"),
                "actual_queries": existing_rescue.get("actual_queries", []),
                "candidate_count": existing_rescue.get("candidate_count", 0),
            }
        )
        return plan

    budget = plan.get("search_budget")
    if not isinstance(budget, dict):
        return plan
    mandatory_complete = (
        plan.get("audit_status") in {"complete", "complete_with_gaps"}
        and set(plan.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
    )
    final_eligible = _base._eligible_candidate_count(
        existing_candidates
    ) + _base._eligible_candidate_count(plan.get("candidates"))
    remaining_calls = int(budget.get("remaining_calls", 0) or 0)
    combined_candidates = list(existing_candidates) + list(plan.get("candidates") or [])
    agency_rescue_needed = bool(
        final_eligible > 0
        and not _policy._candidates_have_fresh_agency_source(
            combined_candidates, search_window
        )
    )
    if (
        maximum_web_search_calls >= RECALL_SENTINEL_MINIMUM_BUDGET
        and mandatory_complete
        and agency_rescue_needed
        and remaining_calls >= 1
    ):
        return _run_agency_rescue(
            plan=plan,
            budget=budget,
            api_key=api_key,
            model=model,
            search_window=search_window,
            existing_candidates=combined_candidates,
            archive=archive,
            maximum_web_search_calls=maximum_web_search_calls,
        )

    if not (
        maximum_web_search_calls >= RECALL_SENTINEL_MINIMUM_BUDGET
        and mandatory_complete
        and final_eligible == 0
        and remaining_calls >= 1
    ):
        return plan

    prompt = build_recall_sentinel_prompt(
        publication_date=publication_date,
        search_window=search_window,
        existing_candidates=existing_candidates,
        archive=archive,
    )
    try:
        # Keep test doubles and production transport wired through the same
        # historical hook.
        _base.run_audit_request = globals()["run_audit_request"]
        result = _base._policy_audit_request(
            api_key=api_key,
            model=model,
            prompt=prompt,
            maximum_web_search_calls=1,
            allowed_domains=RECALL_SENTINEL_DOMAINS,
        )
        payload = result.payload or {}
        if payload.get("status") not in {"complete", "complete_with_gaps"}:
            raise RuntimeError(
                "Recall sentinel вернул непригодный status="
                + repr(payload.get("status"))
            )
    except Exception as exc:
        _set_last_recall_sentinel(
            {
                "status": "error",
                "version": RECALL_SENTINEL_VERSION,
                "search_strategy": RECALL_SENTINEL_STRATEGY,
                "allowed_domains": list(RECALL_SENTINEL_DOMAINS),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        plan["audit_status"] = "partial"
        budget["stop_reason"] = "recall_sentinel_incomplete"
        return plan

    metadata = result.metadata
    raw_candidates = payload.get("candidates")
    accepted_for_pass = [
        _normalize_sentinel_candidate(item)
        for item in raw_candidates
        if isinstance(item, dict)
    ] if isinstance(raw_candidates, list) else []

    prior_general_attempts = [
        int(item.get("attempt", 0) or 0)
        for item in plan.get("attempts", [])
        if isinstance(item, dict)
        and item.get("direction_id") == "general_coverage_gaps"
    ]
    attempt_number = max(prior_general_attempts or [0]) + 1
    payload_status = str(payload.get("status"))
    record = {
        "direction_id": "general_coverage_gaps",
        "label": "Source-neutral broad recall sentinel v8",
        "required": True,
        "attempt": attempt_number,
        "search_strategy": RECALL_SENTINEL_STRATEGY,
        "recall_sentinel_version": RECALL_SENTINEL_VERSION,
        "allowed_domains": list(RECALL_SENTINEL_DOMAINS),
        "prompt": prompt,
        "status": (
            "checked" if payload_status == "complete" else "checked_with_gaps"
        ),
        "outcome": "candidates_found" if accepted_for_pass else "no_news_found",
        "actual_queries": list(metadata.get("actual_queries") or []),
        "sources": list(metadata.get("consulted_sources") or []),
        "candidate_count": len(accepted_for_pass),
        "candidates": accepted_for_pass,
        "rejections": list(payload.get("rejections") or []),
        "notes": payload.get("notes"),
        "api": metadata,
        "error": None,
    }
    plan.setdefault("attempts", []).append(record)
    plan.setdefault("candidates", []).extend(copy.deepcopy(accepted_for_pass))

    completed = int(metadata.get("web_search_calls_completed", 0) or 0)
    observed = int(metadata.get("web_search_call_items_total", 0) or 0)
    budget["response_attempts"] = int(budget.get("response_attempts", 0) or 0) + 1
    budget["observed_call_items"] = int(budget.get("observed_call_items", 0) or 0) + observed
    budget["completed_calls"] = int(budget.get("completed_calls", 0) or 0) + completed
    budget["remaining_calls"] = max(
        0,
        maximum_web_search_calls - int(budget.get("completed_calls", 0) or 0),
    )
    budget["provider_overrun"] = bool(budget.get("provider_overrun")) or completed > 1
    budget["exhausted"] = False
    budget["search_budget_exhausted"] = False
    budget["response_attempt_limit_exhausted"] = False
    budget["stop_reason"] = "recall_sentinel_completed"
    plan["api"] = _policy._aggregate_api_metadata(plan.get("attempts", []))

    _set_last_recall_sentinel(
        {
            "status": (
                "complete" if payload_status == "complete" else "complete_with_gaps"
            ),
            "version": RECALL_SENTINEL_VERSION,
            "search_strategy": RECALL_SENTINEL_STRATEGY,
            "allowed_domains": list(RECALL_SENTINEL_DOMAINS),
            "attempt": attempt_number,
            "actual_queries": record["actual_queries"],
            "candidate_count": len(accepted_for_pass),
            "sources": record["sources"],
        }
    )
    return plan


def _primary_search_diagnostics(publication_date: str) -> dict[str, Any] | None:
    _base.REPOSITORY_ROOT = globals()["REPOSITORY_ROOT"]
    return _base._primary_search_diagnostics(publication_date)


def _sync_policy_overrides() -> None:
    # Preserve the historical monkeypatch/runtime surface. Tests, recovery and
    # callers still override these names on ensure_story_coverage.py; forward
    # them into the preserved base before it wires the policy module.
    for name in (
        "RUNTIME_RESEARCH_ROOT",
        "PERSISTED_RESEARCH_ROOT",
        "PROMPT_PATH",
        "GENERATOR_PATH",
        "rerun_editorial",
        "run_audit_request",
    ):
        if name in globals():
            setattr(_base, name, globals()[name])
    _base.RECALL_SENTINEL_DOMAINS = RECALL_SENTINEL_DOMAINS
    _base.completed_prior_audit = completed_prior_audit
    _base.execute_audit_plan = execute_audit_plan
    _base.build_recall_sentinel_prompt = build_recall_sentinel_prompt
    _base._existing_recall_sentinel = _existing_recall_sentinel
    _base._sync_policy_overrides()



def _promote_completed_zero_pool_editorial_stop(report_path: Path | None) -> bool:
    """Convert only a proven complete zero-pool audit into a healthy no-publish stop."""
    if report_path is None or not report_path.is_file():
        return False
    try:
        payload = read_json(report_path)
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    pool_after = payload.get("candidate_pool_after")
    api = payload.get("api") or {}
    error = str(payload.get("error") or "")
    terminal = bool(
        payload.get("status") == "error"
        and "После основного и дополнительного поиска не осталось ни одного достойного сюжета" in error
        and payload.get("audit_state") == "completed_usable"
        and not payload.get("audit_error")
        and not payload.get("validation_error")
        and payload.get("web_search_performed") is True
        and isinstance(api, dict)
        and api.get("status") == "completed"
        and payload.get("audit_status") in {"complete", "complete_with_gaps"}
        and set(payload.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
        and payload.get("temporal_anchor_version") == TEMPORAL_ANCHOR_VERSION
        and _completed_sentinel_evidence(payload)
        and isinstance(pool_after, dict)
        and pool_after.get("total") == 0
    )
    if not terminal:
        return False
    payload["status"] = "editorial_stop"
    payload["editorial_stop"] = True
    payload["publication_mode"] = "none"
    payload["mode"] = "completed_zero_pool_editorial_stop"
    payload["editorial_stop_reason"] = (
        "Полный research, шесть обязательных coverage-проходов и актуальный "
        "recall sentinel не нашли ни одного достойного сюжета."
    )
    payload["error"] = None
    write_json(report_path, payload)
    return True

def _finalize_source_health_report(report_path: Path | None) -> None:
    if report_path is None or not report_path.is_file():
        return
    payload = read_json(report_path)
    if not isinstance(payload, dict):
        return
    payload["source_health_contract_version"] = SOURCE_HEALTH_CONTRACT_VERSION
    if _LAST_AGENCY_RESCUE is not None:
        payload["agency_rescue"] = copy.deepcopy(_LAST_AGENCY_RESCUE)
        status = str(_LAST_AGENCY_RESCUE.get("status") or "")
        if status in {"complete", "complete_with_gaps", "reused"}:
            payload["audit_notes"] = (
                "Шесть обязательных Coverage-проходов завершены; свободный "
                "седьмой search operation использован как Reuters/AP fresh-agency "
                "rescue для ненулевого пула без свежего agency-кандидата."
            )
        elif status == "error":
            payload["audit_notes"] = (
                "Шесть обязательных Coverage-проходов завершены, но требуемый "
                "fresh-agency rescue технически не завершён; публикация заблокирована."
            )
    write_json(report_path, payload)


def main() -> int:
    _set_last_recall_sentinel(None)
    _set_last_agency_rescue(None)
    _sync_policy_overrides()
    result = int(_base.main())
    # _base.main() resets and then populates the shared sentinel diagnostics.
    _set_last_recall_sentinel(_base._LAST_RECALL_SENTINEL)
    _finalize_source_health_report(_base._report_path())
    if result != 0 and _promote_completed_zero_pool_editorial_stop(_base._report_path()):
        return 0
    return result


if __name__ == "__main__":
    raise SystemExit(main())
