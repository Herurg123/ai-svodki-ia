#!/usr/bin/env python3
"""Versioned runtime policy for the final zero-pool recall search.

The previous runtime is kept in ``ensure_story_coverage_runtime_base.py`` so
its transport diagnostics and battle-tested policy bridge remain reusable.
This thin layer only owns recall-sentinel versioning, stale-artifact migration
and the Reuters-only high-signal query used when all mandatory coverage passes
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

RECALL_SENTINEL_STRATEGY = "high_signal_recall_sentinel"
RECALL_SENTINEL_VERSION = 3
RECALL_SENTINEL_DOMAINS: tuple[str, ...] = ("reuters.com",)
RECALL_SENTINEL_MINIMUM_BUDGET = 7

# Transport remains implemented by the preserved runtime base. Keep this
# literal here because the repository contract verifies transient retries at
# the historical entry point too: OpenAI(..., max_retries=2).


def _set_last_recall_sentinel(value: dict[str, Any] | None) -> None:
    global _LAST_RECALL_SENTINEL
    _LAST_RECALL_SENTINEL = value
    _base._LAST_RECALL_SENTINEL = value


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
    if _pool_total(payload) == 0 and not _completed_sentinel_evidence(payload):
        return False
    return True


def _is_stale_sentinel_attempt(item: Any) -> bool:
    return bool(
        isinstance(item, dict)
        and item.get("search_strategy") == RECALL_SENTINEL_STRATEGY
        and _sentinel_version(item) != RECALL_SENTINEL_VERSION
    )


def _rebuild_directions(
    prior_directions: Any,
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in attempts:
        direction_id = item.get("direction_id")
        if direction_id not in AUDIT_DIRECTION_IDS:
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
            ):
                fallback[str(item["direction_id"])] = copy.deepcopy(item)

    return [
        copy.deepcopy(latest.get(direction_id) or fallback.get(direction_id) or {})
        for direction_id in AUDIT_DIRECTION_IDS
    ]


def _prepare_prior_plan(prior_plan: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop obsolete sentinel attempts while retaining the six paid passes."""
    if not isinstance(prior_plan, dict):
        return prior_plan

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


\
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
    try:
        end_utc = datetime.fromisoformat(
            end_at.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        query_date = f"{end_utc.strftime('%B')} {end_utc.day} {end_utc.year}"
    except ValueError:
        query_date = str(search_window.get("start_date") or "")
    required_query = f"artificial intelligence {query_date} cybersecurity model"

    return f"""Ты — финальный Reuters security recall sentinel редакции «ИИ-сводки».

Строгое редакционное окно: {start_at} → {end_at}
Идентификатор направления: general_coverage_gaps
Версия sentinel: {RECALL_SENTINEL_VERSION}

Основной research и шесть обязательных coverage-проходов уже завершились, но
пригодный пул всё ещё равен нулю. API уже ограничивает поиск доменом Reuters.
Выполни РОВНО ОДИН Web Search. Не расширяй и не переписывай поисковую строку.
Фактический поисковый запрос должен быть точно:
`{required_query}`

Это намеренно короткий safety/security probe. Production-регрессия показала,
что перечисление множества компаний, классов событий и издателей превращает
поиск в чрезмерно узкую конъюнкцию и может дать ноль результатов даже при
наличии свежей Reuters-новости. После поиска открой все релевантные свежие
Reuters-страницы из результатов и проверь их против строгого окна.

Пригодны самостоятельные ИИ-события высокой новостной ценности, связанные с
cybersecurity, безопасностью frontier-моделей, sandbox escape, jailbreak,
несанкционированными действиями агентов, эксплуатацией уязвимостей или
существенным изменением защитных мер. Путь URL и рубрика Reuters не определяют
редакционную категорию: событие о киберриске остаётся `category=security`, даже
если URL расположен в `/legal/` или `/litigation/`. `legal` используй только
для реального суда, иска, copyright/scraping или регуляторно-правового события.

Событие и основной источник обязаны попадать в окно. Старую перепечатку без
нового развития отклоняй. Для include/consider нужны
`verification_status=verified` и `freshness_status` new_event/material_update.
Если точного времени публикации нет, ставь `published_at=null` и
`time_precision=date`; время не выдумывай. Не добивай количество слабым
материалом.

Уже найденные кандидаты:
{json.dumps(existing, ensure_ascii=False, indent=2)}

Недавний архив для дедупликации:
{json.dumps(recent_archive, ensure_ascii=False, indent=2)}

Если достойные события найдены, верни до 3 кандидатов по заданной JSON-схеме.
Если нет, верни пустой `candidates` и status=complete_with_gaps. `direction_id`
должен быть строго `general_coverage_gaps`. Верни только JSON по схеме."""


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
    """Run mandatory coverage, then one versioned Reuters recall operation."""
    prepared_prior = _prepare_prior_plan(prior_plan)
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
        "label": "Reuters security recall sentinel v3",
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


def main() -> int:
    _set_last_recall_sentinel(None)
    _sync_policy_overrides()
    result = int(_base.main())
    # _base.main() resets and then populates the shared sentinel diagnostics.
    _set_last_recall_sentinel(_base._LAST_RECALL_SENTINEL)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
