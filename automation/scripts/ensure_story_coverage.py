#!/usr/bin/env python3
"""Retrieval Quality v1 policy layered over the stable Coverage v8 runtime.

Six mandatory Coverage passes remain unchanged.  The existing seventh search
slot now prefers resolving a high-confidence discovery that Primary Recall saw
but could not verify.  If there is no such signal, the v8 fresh-agency rescue or
zero-pool sentinel keeps its historical behavior.  Search budget stays at seven.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_BASE_PATH = Path(__file__).with_name("ensure_story_coverage_v8.py")
_BASE_SPEC = importlib.util.spec_from_file_location("ensure_story_coverage_v8", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
_v8 = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _v8
_BASE_SPEC.loader.exec_module(_v8)

for _name in dir(_v8):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_v8, _name)


def __getattr__(name: str) -> Any:
    """Preserve the historical module surface for tests and recovery hooks."""
    return getattr(_v8, name)

_V8_EXECUTE = _v8.execute_audit_plan
_V8_PREPARE = _v8._prepare_prior_plan
_V8_COMPLETED_PRIOR = _v8.completed_prior_audit
_MANDATORY_EXECUTE = _v8._BASE_EXECUTE_AUDIT_PLAN
_policy = _v8._policy
_runtime = _v8._base

RETRIEVAL_QUALITY_CONTRACT_VERSION = 1
UNRESOLVED_RESOLUTION_VERSION = 1
UNRESOLVED_RESOLUTION_STRATEGY = "unresolved_high_signal_resolution"
UNRESOLVED_RESOLUTION_DOMAINS: tuple[str, ...] = ()

_LAST_RESOLUTION: dict[str, Any] | None = None

_EVENT_TERMS: tuple[str, ...] = (
    "data center",
    "data centre",
    "guarantee",
    "investment",
    "funding",
    "financing",
    "acquisition",
    "merger",
    "partnership",
    "chips",
    "semiconductor",
    "cloud",
    "infrastructure",
    "model",
    "release",
    "regulation",
    "security",
)
_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9.+-]{2,}")
_TOKEN_STOP = {
    "latest", "major", "artificial", "intelligence", "news", "plans", "new",
    "with", "from", "into", "under", "over", "about", "could", "would", "after",
    "data", "center", "centre", "company", "report", "reported", "possible",
    "fresh", "result", "direct", "primary", "source", "available", "within",
    "search", "operation", "unverified", "aggregated", "latest",
}


def _set_last_resolution(value: dict[str, Any] | None) -> None:
    global _LAST_RESOLUTION
    _LAST_RESOLUTION = value


def _primary_quality_report(publication_date: str) -> dict[str, Any] | None:
    path = (
        Path(REPOSITORY_ROOT)
        / "automation"
        / "preview"
        / "production-daily"
        / f"primary-recall-{publication_date}.json"
    )
    if not path.is_file():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _required_signals(publication_date: str) -> list[dict[str, Any]]:
    report = _primary_quality_report(publication_date)
    if not isinstance(report, dict):
        return []
    if report.get("retrieval_quality_contract_version") != RETRIEVAL_QUALITY_CONTRACT_VERSION:
        return []
    signals = report.get("unresolved_signals")
    if not isinstance(signals, list):
        return []
    result = [
        copy.deepcopy(item)
        for item in signals
        if isinstance(item, dict)
        and item.get("status") == "unresolved"
        and item.get("resolution_required") is True
    ]
    result.sort(
        key=lambda item: (
            -int(item.get("likely_significance_score", 0) or 0),
            str(item.get("signal_id") or ""),
        )
    )
    return result


def _normalized_entities(signal: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for raw in signal.get("entities") or []:
        value = " ".join(str(raw).split()).casefold()
        if value:
            result.add(value)
    return result


def _content_tokens(signal: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(signal.get(key) or "")
        for key in ("title", "evidence_reason")
    )
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(text)
        if token.casefold() not in _TOKEN_STOP and not token.isdigit()
    }


def _signals_related(left: dict[str, Any], right: dict[str, Any]) -> bool:
    entity_overlap = _normalized_entities(left) & _normalized_entities(right)
    token_overlap = _content_tokens(left) & _content_tokens(right)
    return bool(len(entity_overlap) >= 2 or (entity_overlap and len(token_overlap) >= 2))


def resolution_cluster(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the highest-priority related cluster that one query can reasonably resolve."""
    if not signals:
        return []
    cluster = [copy.deepcopy(signals[0])]
    for signal in signals[1:]:
        if any(_signals_related(signal, existing) for existing in cluster):
            cluster.append(copy.deepcopy(signal))
    return cluster[:4]


def _display_entity(originals: list[Any], folded: str) -> str:
    for raw in originals:
        value = " ".join(str(raw).split())
        if value.casefold() == folded:
            return value
    return folded


def build_resolution_query(cluster: list[dict[str, Any]]) -> str:
    """Build a short source-neutral query from minimal evidence, never an AND whitelist."""
    if not cluster:
        raise ValueError("resolution query requires a non-empty cluster")

    all_entity_values: list[Any] = []
    entity_counts: Counter[str] = Counter()
    for signal in cluster:
        values = list(signal.get("entities") or [])
        all_entity_values.extend(values)
        entity_counts.update({" ".join(str(raw).split()).casefold() for raw in values if str(raw).strip()})

    if len(cluster) > 1:
        ranked_entities = [
            value for value, count in entity_counts.most_common()
            if count >= 2
        ][:2]
    else:
        ranked_entities = [value for value, _count in entity_counts.most_common(2)]

    parts = [_display_entity(all_entity_values, value) for value in ranked_entities]
    combined = " ".join(
        str(signal.get(key) or "")
        for signal in cluster
        for key in ("title", "evidence_reason")
    ).casefold()
    for event_term in _EVENT_TERMS:
        if event_term in combined and event_term not in {part.casefold() for part in parts}:
            parts.append(event_term)
        if len(parts) >= 5:
            break

    if len(parts) < 3:
        counts: Counter[str] = Counter()
        surface: dict[str, str] = {}
        for signal in cluster:
            for token in _TOKEN_RE.findall(str(signal.get("title") or "")):
                folded = token.casefold()
                if folded in _TOKEN_STOP or token.isdigit():
                    continue
                counts[folded] += 1
                surface.setdefault(folded, token)
        for folded, _count in counts.most_common():
            token = surface[folded]
            if folded not in {part.casefold() for part in parts}:
                parts.append(token)
            if len(parts) >= 4:
                break

    parts = [" ".join(part.split()) for part in parts if part.strip()]
    query = " ".join(parts[:5] + ["latest"]).strip()
    if not query or query == "latest":
        raise ValueError("could not build a distinctive resolution query")
    return query


def _cluster_compact(cluster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "signal_id": item.get("signal_id"),
            "title": item.get("title"),
            "origin_direction": item.get("origin_direction"),
            "evidence_reason": item.get("evidence_reason"),
            "entities": item.get("entities"),
            "anchors": item.get("anchors"),
            "source_hint": item.get("source_hint"),
            "likely_significance_score": item.get("likely_significance_score"),
            "query_terms_are_hints_not_filters": True,
        }
        for item in cluster
    ]


def build_resolution_prompt(
    *, search_window: dict[str, Any], cluster: list[dict[str, Any]], archive: dict[str, Any]
) -> str:
    query = build_resolution_query(cluster)
    start_at = str(search_window.get("start_at") or "")
    end_at = str(search_window.get("end_at") or "")
    return f"""Ты — targeted resolution-проход редакции «ИИ-Сводки».

Строгое редакционное окно: {start_at} → {end_at}
Авторитетное текущее время: {end_at}
Идентификатор направления: general_coverage_gaps
Версия resolution: {UNRESOLVED_RESOLUTION_VERSION}

Primary Recall уже заметил один или несколько потенциально крупных событий, но не
успел подтвердить их внутри своего единственного search operation. Это НЕ список
разрешённых компаний и НЕ publisher whitelist. `entities`, `anchors` и
`source_hint` ниже являются только evidence/hints. Кандидат не обязан содержать
каждую сущность или каждый anchor.

Выполни РОВНО ОДИН source-neutral Web Search без API domain filter. Не добавляй
Reuters, site:, календарные даты или длинную OR-цепочку. Фактический query должен
быть ТОЧНО:
`{query}`

Задача: подтвердить одно или несколько событий из одного связанного кластера.
Допустим любой авторитетный источник: официальный первоисточник, агентство,
крупное деловое, технологическое или отраслевое СМИ. Не отдавай предпочтение
Reuters только из-за source_hint. После поиска открой релевантные страницы и
проверь фактическую дату/timestamp, событие и существенные факты. Для
include/consider обязательны verification_status=verified и freshness_status
new_event/material_update. Старую перепечатку, слух или событие другого типа
отклоняй. Не выдумывай timestamp.

Unresolved evidence:
{json.dumps(_cluster_compact(cluster), ensure_ascii=False, indent=2)}

Недавний архив:
{json.dumps(_runtime._compact_recent_archive(archive), ensure_ascii=False, indent=2)}

Верни до 3 подтверждённых кандидатов, относящихся к этому evidence cluster. Если
подтвердить событие нельзя, верни пустой candidates и status=complete_with_gaps.
`direction_id` строго `general_coverage_gaps`. Верни только JSON по схеме."""


def _candidate_text(candidate: dict[str, Any]) -> str:
    keywords = candidate.get("keywords") if isinstance(candidate.get("keywords"), list) else []
    return " ".join(
        [
            str(candidate.get("title") or ""),
            str(candidate.get("organization") or ""),
            str(candidate.get("event_summary") or ""),
            *[str(item) for item in keywords],
        ]
    ).casefold()


def _candidate_matches_cluster(candidate: dict[str, Any], cluster: list[dict[str, Any]]) -> bool:
    candidate_text = _candidate_text(candidate)
    candidate_tokens = {
        token.casefold()
        for token in _TOKEN_RE.findall(candidate_text)
        if token.casefold() not in _TOKEN_STOP
    }
    for signal in cluster:
        if len(candidate_tokens & _content_tokens(signal)) >= 2:
            return True
        entities = _normalized_entities(signal)
        if any(entity in candidate_text for entity in entities):
            if any(term in candidate_text for term in _EVENT_TERMS):
                return True
    return False


def _eligible_resolution_candidate(candidate: Any, cluster: list[dict[str, Any]]) -> bool:
    return bool(
        isinstance(candidate, dict)
        and candidate.get("recommendation") in {"include", "consider"}
        and candidate.get("verification_status") == "verified"
        and candidate.get("freshness_status") in {"new_event", "material_update"}
        and _candidate_matches_cluster(candidate, cluster)
    )


def _normalize_resolution_candidate(candidate: dict[str, Any], signal_ids: list[str]) -> dict[str, Any]:
    value = copy.deepcopy(candidate)
    value["audit_direction"] = "unresolved_resolution"
    value["resolution_signal_ids"] = signal_ids
    if value.get("category") != "legal":
        value["legal_scale"] = "not_applicable"
        value["legal_scale_reason"] = ""
    return value


def _recalculate_budget(plan: dict[str, Any], maximum_calls: int) -> None:
    attempts = [item for item in plan.get("attempts", []) if isinstance(item, dict)]
    completed = 0
    observed = 0
    provider_overrun = False
    for attempt in attempts:
        api = attempt.get("api")
        if not isinstance(api, dict):
            continue
        calls = int(api.get("web_search_calls_completed", 0) or 0)
        completed += calls
        observed += int(api.get("web_search_call_items_total", 0) or 0)
        provider_overrun = provider_overrun or calls > 1
    plan["search_budget"] = {
        "maximum_calls": maximum_calls,
        "minimum_required_calls": len(AUDIT_DIRECTION_IDS),
        "response_attempts": len(attempts),
        "observed_call_items": observed,
        "completed_calls": completed,
        "remaining_calls": max(0, maximum_calls - completed),
        "exhausted": completed >= maximum_calls,
        "search_budget_exhausted": completed >= maximum_calls,
        "response_attempt_limit_exhausted": False,
        "provider_overrun": provider_overrun,
        "stop_reason": "retrieval_quality_contract_migration",
    }
    plan["api"] = _policy._aggregate_api_metadata(attempts)


def _is_quality_supplemental(item: Any) -> bool:
    return bool(
        isinstance(item, dict)
        and item.get("search_strategy")
        in {
            _v8.RECALL_SENTINEL_STRATEGY,
            _v8.AGENCY_RESCUE_STRATEGY,
            UNRESOLVED_RESOLUTION_STRATEGY,
        }
    )


def _prepare_prior_plan(
    prior_plan: dict[str, Any] | None,
    search_window: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    prepared = _V8_PREPARE(prior_plan, search_window)
    if not isinstance(prepared, dict):
        return prepared
    quality = prepared.get("retrieval_quality")
    current = bool(
        prepared.get("retrieval_quality_contract_version") == RETRIEVAL_QUALITY_CONTRACT_VERSION
        and isinstance(quality, dict)
        and quality.get("status") == "complete"
    )
    if current:
        return prepared

    attempts = [
        copy.deepcopy(item)
        for item in prepared.get("attempts", [])
        if isinstance(item, dict) and not _is_quality_supplemental(item)
    ]
    prepared["attempts"] = attempts
    prepared["directions"] = _v8._rebuild_directions(prepared.get("directions"), attempts)
    for key in ("recall_sentinel", "agency_rescue", "unresolved_resolution", "retrieval_quality"):
        prepared.pop(key, None)
    prepared.pop("retrieval_quality_contract_version", None)
    maximum_calls = int((prepared.get("search_budget") or {}).get("maximum_calls", 7) or 7)
    _recalculate_budget(prepared, maximum_calls)
    prepared["audit_status"] = (
        "complete_with_gaps"
        if set(prepared.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
        else prepared.get("audit_status", "partial")
    )
    return prepared


def completed_prior_audit(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    quality = payload.get("retrieval_quality")
    if not (
        payload.get("retrieval_quality_contract_version") == RETRIEVAL_QUALITY_CONTRACT_VERSION
        and isinstance(quality, dict)
        and quality.get("status") == "complete"
    ):
        return False
    return _V8_COMPLETED_PRIOR(payload)


def _resolution_quality(
    *, status: str, required: int, cluster: list[dict[str, Any]], resolved: int,
    remaining_required: int, query: str | None = None, reason: str | None = None,
) -> dict[str, Any]:
    return {
        "version": RETRIEVAL_QUALITY_CONTRACT_VERSION,
        "status": status,
        "required_signal_count": required,
        "cluster_signal_ids": [str(item.get("signal_id") or "") for item in cluster],
        "resolved_candidate_count": resolved,
        "remaining_required_signal_count": remaining_required,
        "query": query,
        "domain_filter": False,
        "publisher_whitelist": False,
        "company_whitelist": False,
        "reason": reason,
    }


def _run_resolution(
    *, plan: dict[str, Any], budget: dict[str, Any], api_key: str, model: str,
    search_window: dict[str, Any], archive: dict[str, Any], signals: list[dict[str, Any]],
    maximum_web_search_calls: int,
) -> dict[str, Any]:
    cluster = resolution_cluster(signals)
    query = build_resolution_query(cluster)
    prompt = build_resolution_prompt(search_window=search_window, cluster=cluster, archive=archive)
    signal_ids = [str(item.get("signal_id") or "") for item in cluster]
    try:
        _runtime.run_audit_request = globals()["run_audit_request"]
        result = _runtime._policy_audit_request(
            api_key=api_key,
            model=model,
            prompt=prompt,
            maximum_web_search_calls=1,
            allowed_domains=UNRESOLVED_RESOLUTION_DOMAINS,
        )
        payload = result.payload or {}
        if payload.get("status") not in {"complete", "complete_with_gaps"}:
            raise RuntimeError(
                "Unresolved resolution вернул непригодный status=" + repr(payload.get("status"))
            )
    except Exception as exc:
        quality = _resolution_quality(
            status="incomplete", required=len(signals), cluster=cluster, resolved=0,
            remaining_required=len(signals), query=query,
            reason=f"technical resolution failure: {type(exc).__name__}: {exc}",
        )
        plan["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        plan["retrieval_quality"] = quality
        plan["audit_status"] = "partial"
        budget["stop_reason"] = "unresolved_resolution_incomplete"
        _set_last_resolution(copy.deepcopy(quality))
        return plan

    metadata = result.metadata
    raw_candidates = payload.get("candidates")
    accepted = [
        _normalize_resolution_candidate(item, signal_ids)
        for item in raw_candidates or []
        if _eligible_resolution_candidate(item, cluster)
    ] if isinstance(raw_candidates, list) else []
    accepted = accepted[:3]

    prior_general_attempts = [
        int(item.get("attempt", 0) or 0)
        for item in plan.get("attempts", [])
        if isinstance(item, dict) and item.get("direction_id") == "general_coverage_gaps"
    ]
    attempt_number = max(prior_general_attempts or [0]) + 1
    payload_status = str(payload.get("status"))
    record = {
        "direction_id": "general_coverage_gaps",
        "label": "Unresolved high-signal resolution v1",
        "required": True,
        "attempt": attempt_number,
        "search_strategy": UNRESOLVED_RESOLUTION_STRATEGY,
        "unresolved_resolution_version": UNRESOLVED_RESOLUTION_VERSION,
        "allowed_domains": [],
        "signal_ids": signal_ids,
        "required_query": query,
        "prompt": prompt,
        "status": "checked" if payload_status == "complete" else "checked_with_gaps",
        "outcome": "candidates_found" if accepted else "unresolved",
        "actual_queries": list(metadata.get("actual_queries") or []),
        "sources": list(metadata.get("consulted_sources") or []),
        "candidate_count": len(accepted),
        "candidates": accepted,
        "rejections": list(payload.get("rejections") or []),
        "notes": payload.get("notes"),
        "api": metadata,
        "error": None,
    }
    plan.setdefault("attempts", []).append(record)
    plan.setdefault("candidates", []).extend(copy.deepcopy(accepted))

    completed = int(metadata.get("web_search_calls_completed", 0) or 0)
    observed = int(metadata.get("web_search_call_items_total", 0) or 0)
    budget["response_attempts"] = int(budget.get("response_attempts", 0) or 0) + 1
    budget["observed_call_items"] = int(budget.get("observed_call_items", 0) or 0) + observed
    budget["completed_calls"] = int(budget.get("completed_calls", 0) or 0) + completed
    budget["remaining_calls"] = max(0, maximum_web_search_calls - int(budget.get("completed_calls", 0) or 0))
    budget["provider_overrun"] = bool(budget.get("provider_overrun")) or completed > 1
    budget["exhausted"] = int(budget.get("completed_calls", 0) or 0) >= maximum_web_search_calls
    budget["search_budget_exhausted"] = budget["exhausted"]
    budget["response_attempt_limit_exhausted"] = False
    budget["stop_reason"] = "unresolved_resolution_completed"
    plan["api"] = _policy._aggregate_api_metadata(plan.get("attempts", []))

    unresolved_outside_cluster = max(0, len(signals) - len(cluster))
    if accepted and unresolved_outside_cluster == 0:
        quality_status = "complete"
        remaining_required = 0
        reason = "targeted resolution produced verified candidate evidence"
    else:
        quality_status = "degraded"
        remaining_required = unresolved_outside_cluster + (0 if accepted else len(cluster))
        reason = "high-confidence unresolved evidence remains after the single available resolution slot"
        plan["audit_status"] = "partial"

    quality = _resolution_quality(
        status=quality_status,
        required=len(signals),
        cluster=cluster,
        resolved=len(accepted),
        remaining_required=remaining_required,
        query=query,
        reason=reason,
    )
    plan["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
    plan["retrieval_quality"] = quality
    plan["unresolved_resolution"] = copy.deepcopy(quality)
    _set_last_resolution(copy.deepcopy(quality))
    return plan


def execute_audit_plan(
    *, api_key: str, model: str, template: str, publication_date: str,
    search_window: dict[str, Any], missing_total: int, maximum_web_search_calls: int,
    existing_candidates: list[Any], archive: dict[str, Any],
    prior_plan: dict[str, Any] | None = None, source_health_rescue_needed: bool = False,
) -> dict[str, Any]:
    """Mandatory Coverage -> unresolved resolution -> historical v8 supplementals."""
    prepared_prior = _prepare_prior_plan(prior_plan, search_window)
    plan = _MANDATORY_EXECUTE(
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
    plan["temporal_anchor_version"] = _v8.TEMPORAL_ANCHOR_VERSION

    budget = plan.get("search_budget")
    mandatory_complete = bool(
        isinstance(budget, dict)
        and plan.get("audit_status") in {"complete", "complete_with_gaps"}
        and set(plan.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
    )
    signals = _required_signals(publication_date)
    remaining_calls = int(budget.get("remaining_calls", 0) or 0) if isinstance(budget, dict) else 0

    if signals and mandatory_complete and remaining_calls >= 1:
        plan = _run_resolution(
            plan=plan,
            budget=budget,
            api_key=api_key,
            model=model,
            search_window=search_window,
            archive=archive,
            signals=signals,
            maximum_web_search_calls=maximum_web_search_calls,
        )
        if plan.get("retrieval_quality", {}).get("status") != "complete":
            return plan
        if int((plan.get("search_budget") or {}).get("remaining_calls", 0) or 0) <= 0:
            return plan
    elif signals:
        quality = _resolution_quality(
            status="degraded",
            required=len(signals),
            cluster=[],
            resolved=0,
            remaining_required=len(signals),
            reason=(
                "mandatory Coverage retry consumed the adaptive budget before high-signal resolution"
                if mandatory_complete
                else "mandatory Coverage is incomplete"
            ),
        )
        plan["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        plan["retrieval_quality"] = quality
        plan["audit_status"] = "partial"
        _set_last_resolution(copy.deepcopy(quality))
        return plan
    else:
        quality = _resolution_quality(
            status="complete",
            required=0,
            cluster=[],
            resolved=0,
            remaining_required=0,
            reason="Primary Recall produced no high-confidence unresolved signal requiring resolution",
        )
        plan["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        plan["retrieval_quality"] = quality

    return _V8_EXECUTE(
        api_key=api_key,
        model=model,
        template=template,
        publication_date=publication_date,
        search_window=search_window,
        missing_total=missing_total,
        maximum_web_search_calls=maximum_web_search_calls,
        existing_candidates=existing_candidates,
        archive=archive,
        prior_plan=plan,
        source_health_rescue_needed=source_health_rescue_needed,
    )


def _sync_v8_overrides() -> None:
    for name in (
        "REPOSITORY_ROOT", "RUNTIME_RESEARCH_ROOT", "PERSISTED_RESEARCH_ROOT",
        "PROMPT_PATH", "GENERATOR_PATH", "rerun_editorial", "run_audit_request",
    ):
        if name in globals():
            setattr(_v8, name, globals()[name])
    _v8.execute_audit_plan = execute_audit_plan
    _v8.completed_prior_audit = completed_prior_audit
    _v8._prepare_prior_plan = _prepare_prior_plan


def _finalize_quality_report(report_path: Path | None) -> None:
    if report_path is None or not report_path.is_file():
        return
    payload = read_json(report_path)
    if not isinstance(payload, dict):
        return
    payload["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
    if not isinstance(payload.get("retrieval_quality"), dict):
        if _LAST_RESOLUTION is not None:
            payload["retrieval_quality"] = copy.deepcopy(_LAST_RESOLUTION)
        else:
            payload["retrieval_quality"] = _resolution_quality(
                status="complete", required=0, cluster=[], resolved=0,
                remaining_required=0,
                reason="no high-confidence unresolved signal required resolution",
            )
    write_json(report_path, payload)


def main() -> int:
    _set_last_resolution(None)
    _sync_v8_overrides()
    result = int(_v8.main())
    _finalize_quality_report(_v8._base._report_path())
    return result


if __name__ == "__main__":
    raise SystemExit(main())
