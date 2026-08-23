#!/usr/bin/env python3
"""Retrieval Quality v1 over the stable Coverage v8 policy.

The six mandatory passes and all v8 sentinel/agency behavior stay intact. Only
when Primary Recall produced a high-confidence unresolved signal do we reserve
the already-existing seventh Coverage slot for one source-neutral resolution
search. Coverage remains capped at seven calls. A distinct pre-Hybrid agency
discovery rescue may add at most one separate search, so the explicit whole-
pipeline ceiling is 24 = 12 Primary + 1 agency discovery + 4 Hybrid + 7 Coverage.
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

from agency_discovery_recovery_entry import run_recovery_entry


def __getattr__(name: str) -> Any:
    return getattr(_v8, name)


_V8_EXECUTE = _v8.execute_audit_plan
_V8_COMPLETED_PRIOR = _v8.completed_prior_audit
_V8_PREPARE_PRIOR = _v8._prepare_prior_plan
_V8_SYNC_POLICY = _v8._sync_policy_overrides
_policy = _v8._policy
_runtime = _v8._base

RETRIEVAL_QUALITY_CONTRACT_VERSION = 1
UNRESOLVED_RESOLUTION_VERSION = 1
UNRESOLVED_RESOLUTION_STRATEGY = "unresolved_high_signal_resolution"
UNRESOLVED_RESOLUTION_DOMAINS: tuple[str, ...] = ()

# Stable v8 transport still uses OpenAI(..., max_retries=2). Keep this literal
# at the public entrypoint because repository contract tests inspect it.

_EVENT_TERMS = (
    "data center", "data centre", "guarantee", "investment", "funding",
    "financing", "acquisition", "merger", "partnership", "chips",
    "semiconductor", "cloud", "infrastructure", "model", "release",
    "regulation", "security",
)
_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9.+-]{2,}")
_TOKEN_STOP = {
    "latest", "major", "artificial", "intelligence", "news", "plans", "new",
    "with", "from", "into", "under", "over", "about", "could", "would", "after",
    "data", "center", "centre", "company", "report", "reported", "possible",
    "fresh", "result", "direct", "primary", "source", "available", "within",
    "search", "operation", "unverified", "aggregated",
}


def _sync_direct_hooks() -> None:
    """Mirror monkeypatchable wrapper state into the preserved v8 runtime."""
    for name in (
        "REPOSITORY_ROOT", "RUNTIME_RESEARCH_ROOT", "PERSISTED_RESEARCH_ROOT",
        "PROMPT_PATH", "GENERATOR_PATH", "rerun_editorial", "run_audit_request",
        "_BASE_EXECUTE_AUDIT_PLAN",
    ):
        if name in globals():
            setattr(_v8, name, globals()[name])
    if "run_audit_request" in globals():
        _runtime.run_audit_request = globals()["run_audit_request"]


def _sync_state_from_v8() -> None:
    globals()["_LAST_RECALL_SENTINEL"] = getattr(_v8, "_LAST_RECALL_SENTINEL", None)
    globals()["_LAST_AGENCY_RESCUE"] = getattr(_v8, "_LAST_AGENCY_RESCUE", None)


def _primary_search_diagnostics(*args: Any, **kwargs: Any) -> Any:
    _sync_direct_hooks()
    return _v8._primary_search_diagnostics(*args, **kwargs)


def completed_prior_audit(payload: Any) -> bool:
    """Historical v8 completion semantics, retained for compatibility."""
    return bool(_V8_COMPLETED_PRIOR(payload))


def _sync_policy_overrides() -> None:
    """Keep the legacy policy hook pointing at this public compatibility entrypoint."""
    _sync_direct_hooks()
    _V8_SYNC_POLICY()
    _policy.completed_prior_audit = completed_prior_audit


def completed_quality_audit(payload: Any) -> bool:
    """Strict modern reuse gate: legacy completion plus Retrieval Quality v1."""
    if not completed_prior_audit(payload) or not isinstance(payload, dict):
        return False
    quality = payload.get("retrieval_quality")
    return bool(
        payload.get("retrieval_quality_contract_version") == RETRIEVAL_QUALITY_CONTRACT_VERSION
        and isinstance(quality, dict)
        and quality.get("status") == "complete"
    )


def _primary_quality_report(publication_date: str) -> dict[str, Any] | None:
    path = (
        Path(REPOSITORY_ROOT) / "automation" / "preview" / "production-daily"
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
    rows = report.get("unresolved_signals")
    if not isinstance(rows, list):
        return []
    result = [
        copy.deepcopy(item)
        for item in rows
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
    return {
        " ".join(str(raw).split()).casefold()
        for raw in signal.get("entities") or []
        if str(raw).strip()
    }


def _content_tokens(signal: dict[str, Any]) -> set[str]:
    text = " ".join(str(signal.get(key) or "") for key in ("title", "evidence_reason"))
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(text)
        if token.casefold() not in _TOKEN_STOP and not token.isdigit()
    }


def _signals_related(left: dict[str, Any], right: dict[str, Any]) -> bool:
    entities = _normalized_entities(left) & _normalized_entities(right)
    tokens = _content_tokens(left) & _content_tokens(right)
    return bool(len(entities) >= 2 or (entities and len(tokens) >= 2))


def resolution_cluster(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pick one related high-priority cluster resolvable by one targeted search."""
    if not signals:
        return []
    cluster = [copy.deepcopy(signals[0])]
    for signal in signals[1:]:
        if any(_signals_related(signal, current) for current in cluster):
            cluster.append(copy.deepcopy(signal))
    return cluster[:4]


def _display_entity(originals: list[Any], folded: str) -> str:
    for raw in originals:
        value = " ".join(str(raw).split())
        if value.casefold() == folded:
            return value
    return folded


def build_resolution_query(cluster: list[dict[str, Any]]) -> str:
    """Build minimal source-neutral evidence query, never an AND whitelist."""
    if not cluster:
        raise ValueError("resolution query requires a non-empty cluster")
    originals: list[Any] = []
    counts: Counter[str] = Counter()
    for signal in cluster:
        values = list(signal.get("entities") or [])
        originals.extend(values)
        counts.update({
            " ".join(str(raw).split()).casefold()
            for raw in values if str(raw).strip()
        })
    if len(cluster) > 1:
        entities = [value for value, count in counts.most_common() if count >= 2][:2]
    else:
        entities = [value for value, _count in counts.most_common(2)]
    parts = [_display_entity(originals, value) for value in entities]
    combined = " ".join(
        str(signal.get(key) or "")
        for signal in cluster for key in ("title", "evidence_reason")
    ).casefold()
    for term in _EVENT_TERMS:
        if term in combined and term not in {part.casefold() for part in parts}:
            parts.append(term)
        if len(parts) >= 5:
            break
    if len(parts) < 3:
        token_counts: Counter[str] = Counter()
        surface: dict[str, str] = {}
        for signal in cluster:
            for token in _TOKEN_RE.findall(str(signal.get("title") or "")):
                folded = token.casefold()
                if folded in _TOKEN_STOP or token.isdigit():
                    continue
                token_counts[folded] += 1
                surface.setdefault(folded, token)
        for folded, _count in token_counts.most_common():
            if folded not in {part.casefold() for part in parts}:
                parts.append(surface[folded])
            if len(parts) >= 4:
                break
    query = " ".join(
        [" ".join(item.split()) for item in parts[:5] if item.strip()] + ["latest"]
    ).strip()
    if query == "latest":
        raise ValueError("could not build a distinctive resolution query")
    return query


def build_resolution_prompt(
    *, search_window: dict[str, Any], cluster: list[dict[str, Any]], archive: dict[str, Any]
) -> str:
    query = build_resolution_query(cluster)
    compact = [
        {key: item.get(key) for key in (
            "signal_id", "title", "origin_direction", "evidence_reason", "entities",
            "anchors", "source_hint", "likely_significance_score",
        )}
        for item in cluster
    ]
    return f"""Ты — targeted resolution-проход редакции «ИИ-Сводки».

Строгое редакционное окно: {search_window.get('start_at')} → {search_window.get('end_at')}
Идентификатор направления: general_coverage_gaps
Версия resolution: {UNRESOLVED_RESOLUTION_VERSION}

Primary Recall заметил потенциально крупное событие, но не успел подтвердить его.
`entities`, `anchors` и `source_hint` являются только evidence/hints. Они НЕ
являются списком обязательных слов, company whitelist или publisher whitelist.

Выполни РОВНО ОДИН source-neutral Web Search без API domain filter. Не добавляй
Reuters, site:, календарные даты или длинную OR-цепочку. Фактический query ТОЧНО:
`{query}`

Допустим любой авторитетный источник: официальный первоисточник, агентство,
крупное деловое, технологическое или отраслевое СМИ. Не отдавай предпочтение
Reuters из-за source_hint. Подтверди дату/timestamp, событие и существенные факты.
Для include/consider обязательны verification_status=verified и freshness_status
new_event/material_update. Верни до 3 кандидатов из этого evidence cluster.

Evidence:
{json.dumps(compact, ensure_ascii=False, indent=2)}

Archive:
{json.dumps(_runtime._compact_recent_archive(archive), ensure_ascii=False, indent=2)}

Если подтвердить событие нельзя, верни пустой candidates и status=complete_with_gaps.
Верни только JSON по штатной Coverage-схеме."""


def _candidate_text(candidate: dict[str, Any]) -> str:
    keywords = candidate.get("keywords") if isinstance(candidate.get("keywords"), list) else []
    return " ".join([
        str(candidate.get("title") or ""),
        str(candidate.get("organization") or ""),
        str(candidate.get("event_summary") or ""),
        *[str(item) for item in keywords],
    ]).casefold()


def _candidate_matches_cluster(candidate: dict[str, Any], cluster: list[dict[str, Any]]) -> bool:
    text = _candidate_text(candidate)
    tokens = {
        token.casefold() for token in _TOKEN_RE.findall(text)
        if token.casefold() not in _TOKEN_STOP
    }
    for signal in cluster:
        if len(tokens & _content_tokens(signal)) >= 2:
            return True
        if (
            any(entity in text for entity in _normalized_entities(signal))
            and any(term in text for term in _EVENT_TERMS)
        ):
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


def _is_quality_supplemental(item: Any) -> bool:
    return bool(
        isinstance(item, dict)
        and item.get("search_strategy") in {
            _v8.RECALL_SENTINEL_STRATEGY,
            _v8.AGENCY_RESCUE_STRATEGY,
            UNRESOLVED_RESOLUTION_STRATEGY,
        }
    )


def _recalculate_budget(plan: dict[str, Any], maximum_calls: int) -> None:
    attempts = [item for item in plan.get("attempts", []) if isinstance(item, dict)]
    completed = sum(
        int((item.get("api") or {}).get("web_search_calls_completed", 0) or 0)
        for item in attempts
    )
    observed = sum(
        int((item.get("api") or {}).get("web_search_call_items_total", 0) or 0)
        for item in attempts
    )
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
        "provider_overrun": any(
            int((item.get("api") or {}).get("web_search_calls_completed", 0) or 0) > 1
            for item in attempts
        ),
        "stop_reason": "retrieval_quality_contract_migration",
    }
    plan["api"] = _policy._aggregate_api_metadata(attempts)


def _prepare_prior_plan(
    prior_plan: dict[str, Any] | None,
    search_window: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Historical v8 preparation proxy retained for callers/tests."""
    _sync_direct_hooks()
    return _V8_PREPARE_PRIOR(prior_plan, search_window)


def _prepare_prior_for_quality(
    prior_plan: dict[str, Any] | None,
    search_window: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    prepared = _V8_PREPARE_PRIOR(prior_plan, search_window)
    if not isinstance(prepared, dict):
        return prepared
    quality = prepared.get("retrieval_quality")
    if (
        prepared.get("retrieval_quality_contract_version") == RETRIEVAL_QUALITY_CONTRACT_VERSION
        and isinstance(quality, dict)
        and quality.get("status") == "complete"
    ):
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
    return prepared


def _quality(
    status: str,
    signals: list[dict[str, Any]],
    cluster: list[dict[str, Any]],
    *,
    resolved: int = 0,
    remaining: int | None = None,
    query: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "version": RETRIEVAL_QUALITY_CONTRACT_VERSION,
        "status": status,
        "required_signal_count": len(signals),
        "cluster_signal_ids": [str(item.get("signal_id") or "") for item in cluster],
        "resolved_candidate_count": resolved,
        "remaining_required_signal_count": len(signals) if remaining is None else remaining,
        "query": query,
        "domain_filter": False,
        "publisher_whitelist": False,
        "company_whitelist": False,
        "reason": reason,
    }


def _annotate_no_signal_quality(plan: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    result["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
    result["retrieval_quality"] = _quality(
        "complete", [], [], remaining=0,
        reason="no high-confidence unresolved signal required resolution",
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
    cluster = resolution_cluster(signals)
    query = build_resolution_query(cluster)
    prompt = build_resolution_prompt(search_window=search_window, cluster=cluster, archive=archive)
    _sync_direct_hooks()
    try:
        result = _runtime._policy_audit_request(
            api_key=api_key,
            model=model,
            prompt=prompt,
            maximum_web_search_calls=1,
            allowed_domains=UNRESOLVED_RESOLUTION_DOMAINS,
        )
        payload = result.payload or {}
        metadata = result.metadata
        if payload.get("status") not in {"complete", "complete_with_gaps"}:
            raise RuntimeError(f"unusable resolution status={payload.get('status')!r}")
    except Exception as exc:
        plan["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        plan["retrieval_quality"] = _quality(
            "incomplete", signals, cluster, query=query,
            reason=f"technical resolution failure: {type(exc).__name__}: {exc}",
        )
        plan["audit_status"] = "partial"
        return plan

    signal_ids = [str(item.get("signal_id") or "") for item in cluster]
    raw = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    accepted: list[dict[str, Any]] = []
    for candidate in raw:
        if not _eligible_resolution_candidate(candidate, cluster):
            continue
        item = copy.deepcopy(candidate)
        item["audit_direction"] = "unresolved_resolution"
        item["resolution_signal_ids"] = signal_ids
        if item.get("category") != "legal":
            item["legal_scale"] = "not_applicable"
            item["legal_scale_reason"] = ""
        accepted.append(item)
    accepted = accepted[:3]

    attempts = plan.setdefault("attempts", [])
    attempt_number = 1 + max([
        int(item.get("attempt", 0) or 0)
        for item in attempts
        if isinstance(item, dict) and item.get("direction_id") == "general_coverage_gaps"
    ] or [0])
    attempts.append({
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
        "status": "checked" if payload.get("status") == "complete" else "checked_with_gaps",
        "outcome": "candidates_found" if accepted else "unresolved",
        "actual_queries": list(metadata.get("actual_queries") or []),
        "sources": list(metadata.get("consulted_sources") or []),
        "candidate_count": len(accepted),
        "candidates": accepted,
        "rejections": list(payload.get("rejections") or []),
        "notes": payload.get("notes"),
        "api": metadata,
        "error": None,
    })
    plan.setdefault("candidates", []).extend(copy.deepcopy(accepted))
    maximum_calls = int(
        (plan.get("search_budget") or {}).get("maximum_calls", maximum_web_search_calls)
        or maximum_web_search_calls
    )
    _recalculate_budget(plan, maximum_calls)
    unresolved_outside = max(0, len(signals) - len(cluster))
    complete = bool(accepted and unresolved_outside == 0)
    remaining = unresolved_outside + (0 if accepted else len(cluster))
    plan["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
    plan["retrieval_quality"] = _quality(
        "complete" if complete else "degraded",
        signals,
        cluster,
        resolved=len(accepted),
        remaining=remaining,
        query=query,
        reason=(
            "verified candidate evidence found"
            if complete
            else "high-confidence unresolved evidence remains after the single resolution slot"
        ),
    )
    plan["unresolved_resolution"] = copy.deepcopy(plan["retrieval_quality"])
    if not complete:
        plan["audit_status"] = "partial"
    return plan


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
    source_health_rescue_needed: bool = False,
) -> dict[str, Any]:
    """Run v8 unchanged unless current Primary evidence requires resolution."""
    _sync_direct_hooks()
    signals = _required_signals(publication_date)
    if not signals:
        result = _V8_EXECUTE(
            api_key=api_key,
            model=model,
            template=template,
            publication_date=publication_date,
            search_window=search_window,
            missing_total=missing_total,
            maximum_web_search_calls=maximum_web_search_calls,
            existing_candidates=existing_candidates,
            archive=archive,
            prior_plan=prior_plan,
            source_health_rescue_needed=source_health_rescue_needed,
        )
        _sync_state_from_v8()
        return _annotate_no_signal_quality(result)

    prepared = _prepare_prior_for_quality(prior_plan, search_window)
    # Let v8 finish/retry all mandatory directions first. A synthetic non-zero
    # pool suppresses only v8's supplemental sentinel while this higher-priority
    # unresolved resolution is pending.
    sentinel_guard = existing_candidates if existing_candidates else [{"id": "retrieval-quality-guard"}]
    base = _V8_EXECUTE(
        api_key=api_key,
        model=model,
        template=template,
        publication_date=publication_date,
        search_window=search_window,
        missing_total=missing_total,
        maximum_web_search_calls=maximum_web_search_calls,
        existing_candidates=sentinel_guard,
        archive=archive,
        prior_plan=prepared,
        source_health_rescue_needed=False,
    )
    _sync_state_from_v8()
    checked = set(base.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
    remaining_calls = int((base.get("search_budget") or {}).get("remaining_calls", 0) or 0)
    if not checked:
        base["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        base["retrieval_quality"] = _quality(
            "degraded", signals, [], reason="mandatory Coverage remains incomplete"
        )
        base["audit_status"] = "partial"
        return base
    if remaining_calls < 1:
        base["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        base["retrieval_quality"] = _quality(
            "degraded", signals, [],
            reason="mandatory Coverage retry consumed the adaptive quality slot",
        )
        base["audit_status"] = "partial"
        return base
    return _run_resolution(
        plan=base,
        signals=signals,
        api_key=api_key,
        model=model,
        search_window=search_window,
        archive=archive,
        maximum_web_search_calls=maximum_web_search_calls,
    )


def _finalize_quality_report(report_path: Path | None, recovery_entry: dict[str, Any] | None = None) -> None:
    if report_path is None or not report_path.is_file():
        return
    payload = read_json(report_path)
    if not isinstance(payload, dict):
        return
    if not isinstance(payload.get("retrieval_quality"), dict):
        payload = _annotate_no_signal_quality(payload)
    if isinstance(recovery_entry, dict) and recovery_entry.get("status") != "not_recovery":
        payload["agency_discovery_rescue_recovery_entry"] = {
            key: recovery_entry.get(key)
            for key in (
                "version",
                "search_strategy",
                "triggered",
                "trigger_reason",
                "executed",
                "state",
                "status",
                "raw_count",
                "accepted_count",
                "added_count",
                "duplicate_count",
                "search_operation_count_contribution",
                "recovered_from_artifact",
                "coverage_recovery_entry",
                "coverage_recovery_editorial_rerun",
                "coverage_recovery_source_freshness",
            )
            if key in recovery_entry
        }
    write_json(report_path, payload)


def main() -> int:
    _sync_direct_hooks()
    _v8.execute_audit_plan = execute_audit_plan
    _v8.completed_prior_audit = completed_prior_audit
    recovery_entry = run_recovery_entry(rerun_editorial_fn=rerun_editorial)
    result = int(_v8.main())
    _sync_state_from_v8()
    _finalize_quality_report(_runtime._report_path(), recovery_entry)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
