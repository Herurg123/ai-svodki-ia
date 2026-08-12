from __future__ import annotations

import copy
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_POLICY_PATH = Path(__file__).with_name("ensure_story_coverage_policy.py")
_POLICY_SPEC = importlib.util.spec_from_file_location(
    "ensure_story_coverage_policy",
    _POLICY_PATH,
)
assert _POLICY_SPEC and _POLICY_SPEC.loader
_policy = importlib.util.module_from_spec(_POLICY_SPEC)
sys.modules[_POLICY_SPEC.name] = _policy
_POLICY_SPEC.loader.exec_module(_policy)
_BASE_EXECUTE_AUDIT_PLAN = _policy.execute_audit_plan

# Re-export the policy surface so existing tests and callers keep importing the
# historical entry point. Runtime transport/recovery behavior is overridden
# below while the policy module remains the canonical implementation.
for _name in dir(_policy):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_policy, _name)


RECALL_SENTINEL_STRATEGY = "high_signal_recall_sentinel"
RECALL_SENTINEL_DOMAINS: tuple[str, ...] = (
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "ft.com",
)
RECALL_SENTINEL_MINIMUM_BUDGET = 7
COVERAGE_NAVIGATION_TOOL_ALLOWANCE = 3


@dataclass
class AuditRequestResult:
    payload: dict[str, Any] | None
    metadata: dict[str, Any]
    output_text: str
    raw_response: Any
    validation_error: str | None

    def __iter__(self):
        yield self.payload
        yield self.metadata


_LAST_AUDIT_RESULT: AuditRequestResult | None = None
_LAST_AUDIT_RESULTS: list[AuditRequestResult] = []
_LAST_RECALL_SENTINEL: dict[str, Any] | None = None


def build_audit_api_metadata(
    response: Any,
    *,
    maximum_web_search_calls: int,
) -> dict[str, Any]:
    return _policy.build_audit_api_metadata(
        response,
        maximum_web_search_calls=maximum_web_search_calls,
    )


def run_audit_request(
    *,
    api_key: str,
    model: str,
    prompt: str,
    maximum_web_search_calls: int,
    allowed_domains: list[str] | tuple[str, ...] | None = None,
) -> AuditRequestResult:
    global _LAST_AUDIT_RESULT

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
    web_search_tool: dict[str, Any] = {
        "type": "web_search",
        "search_context_size": "medium",
        "return_token_budget": "default",
    }
    if allowed_domains:
        web_search_tool["filters"] = {
            "allowed_domains": list(allowed_domains),
        }
    # The production fallback executes one search operation per targeted pass;
    # give those calls a small navigation allowance for open/find verification.
    # Historical multi-search callers keep their existing hard tool-call cap.
    total_tool_calls = (
        maximum_web_search_calls + COVERAGE_NAVIGATION_TOOL_ALLOWANCE
        if maximum_web_search_calls == 1
        else maximum_web_search_calls
    )
    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[web_search_tool],
        tool_choice="required",
        max_tool_calls=total_tool_calls,
        include=["web_search_call.action.sources"],
        reasoning={"effort": "medium"},
        max_output_tokens=3500,
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_ai_targeted_coverage_audit",
                "strict": True,
                "schema": AUDIT_SCHEMA,
            }
        },
        store=False,
    )
    metadata = build_audit_api_metadata(
        response,
        maximum_web_search_calls=maximum_web_search_calls,
    )
    metadata["configured_search_operations"] = maximum_web_search_calls
    metadata["configured_total_tool_calls"] = total_tool_calls
    metadata["navigation_tool_allowance"] = (
        COVERAGE_NAVIGATION_TOOL_ALLOWANCE
        if maximum_web_search_calls == 1
        else 0
    )
    output_text = (getattr(response, "output_text", None) or "").strip()
    payload: Any = None
    validation_error: str | None = None

    if metadata.get("web_search_calls_completed", 0) < 1:
        validation_error = (
            "Coverage audit не завершил ни одной поисковой операции "
            "web_search action.type=search"
        )
    elif metadata.get("web_search_calls_completed", 0) > maximum_web_search_calls:
        validation_error = (
            "Coverage audit превысил search-operation budget: "
            f"{metadata.get('web_search_calls_completed')}>{maximum_web_search_calls}"
        )
    elif getattr(response, "status", None) != "completed":
        validation_error = (
            "Coverage audit не завершён: "
            f"status={getattr(response, 'status', None)!r}"
        )
    elif not output_text:
        validation_error = "Coverage audit вернул пустой output_text"
    else:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            validation_error = f"Coverage audit вернул некорректный JSON: {exc}"
        if validation_error is None and not isinstance(payload, dict):
            validation_error = "Coverage audit должен вернуть JSON-объект"
        if validation_error is None:
            if payload.get("direction_id") not in AUDIT_DIRECTION_IDS:
                validation_error = "Coverage audit вернул неизвестный direction_id"
            elif payload.get("status") not in {
                "complete",
                "complete_with_gaps",
                "error",
            }:
                validation_error = "Coverage audit вернул неизвестный status"
            elif not metadata.get("actual_queries"):
                validation_error = (
                    "Coverage audit не сохранил фактический поисковый запрос"
                )

    result = AuditRequestResult(
        payload=payload if isinstance(payload, dict) else None,
        metadata=metadata,
        output_text=output_text,
        raw_response=response_to_plain(response),
        validation_error=validation_error,
    )
    _LAST_AUDIT_RESULT = result
    _LAST_AUDIT_RESULTS.append(result)
    if validation_error is None and metadata.get("budget_overrun"):
        print(
            "::warning title=Coverage audit web-search budget::"
            "Responses API завершил больше поисковых операций, чем настроено: "
            f"{metadata.get('web_search_calls_completed')}>"
            f"{maximum_web_search_calls}. Ответ сохранён для диагностики; "
            "неполный обязательный audit заблокирует публикацию.",
            file=sys.stderr,
        )
    return result


def coerce_audit_result(value: Any) -> AuditRequestResult:
    if isinstance(value, AuditRequestResult):
        value.metadata.setdefault(
            "web_search_calls_completed",
            int(value.metadata.get("web_search_calls", 0) or 0),
        )
        value.metadata.setdefault(
            "web_search_call_items_total",
            int(
                value.metadata.get(
                    "observed_web_search_calls",
                    value.metadata.get("web_search_calls", 0),
                )
                or 0
            ),
        )
        return value
    if isinstance(value, tuple) and len(value) == 2:
        payload, metadata = value
        if isinstance(payload, dict) and isinstance(metadata, dict):
            legacy_queries = payload.get("queries_used")
            if not metadata.get("actual_queries") and isinstance(
                legacy_queries, list
            ):
                metadata["actual_queries"] = [
                    str(item.get("query", "")).strip()
                    for item in legacy_queries
                    if isinstance(item, dict) and str(item.get("query", "")).strip()
                ]
            metadata.setdefault(
                "web_search_calls_completed",
                int(metadata.get("web_search_calls", 0) or 0),
            )
            metadata.setdefault(
                "web_search_call_items_total",
                int(metadata.get("web_search_calls", 0) or 0),
            )
            return AuditRequestResult(
                payload=payload,
                metadata=metadata,
                output_text=json.dumps(payload, ensure_ascii=False),
                raw_response=None,
                validation_error=None,
            )
    raise RuntimeError("Coverage audit вернул результат неожиданного типа")


def persist_audit_diagnostics(
    result: AuditRequestResult,
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "coverage-audit-output.txt"
    response_path = output_dir / "coverage-audit-response.json"
    output_path.write_text(
        result.output_text + ("\n" if result.output_text else ""),
        encoding="utf-8",
    )
    response_path.write_text(
        json.dumps(
            result.raw_response,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "api_output_path": str(output_path),
        "api_response_path": str(response_path),
    }


def _pool_total(payload: dict[str, Any]) -> int | None:
    for key in ("candidate_pool_after", "candidate_pool_before"):
        pool = payload.get(key)
        if not isinstance(pool, dict):
            continue
        total = pool.get("total")
        if isinstance(total, int):
            return total
    return None


def _completed_sentinel_evidence(payload: dict[str, Any]) -> bool:
    sentinel = payload.get("recall_sentinel")
    if isinstance(sentinel, dict) and sentinel.get("status") in {
        "complete",
        "complete_with_gaps",
        "reused",
    }:
        return True
    attempts = payload.get("attempts")
    if not isinstance(attempts, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("search_strategy") == RECALL_SENTINEL_STRATEGY
        and item.get("status") in {"checked", "checked_with_gaps"}
        for item in attempts
    )


def completed_prior_audit(payload: Any) -> bool:
    """Reuse a completed audit unless a zero pool predates the recall sentinel."""
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


def _policy_audit_request(**kwargs: Any) -> AuditRequestResult:
    global _LAST_AUDIT_RESULT

    result = coerce_audit_result(globals()["run_audit_request"](**kwargs))
    _LAST_AUDIT_RESULT = result
    if result not in _LAST_AUDIT_RESULTS:
        _LAST_AUDIT_RESULTS.append(result)
    if isinstance(result.payload, dict):
        if result.payload.get("status") == "ok":
            result.payload["status"] = "complete"
        if result.payload.get("direction_id") not in AUDIT_DIRECTION_IDS:
            prompt = str(kwargs.get("prompt") or "")
            inferred = next((item for item in AUDIT_DIRECTION_IDS if item in prompt), None)
            if inferred:
                result.payload["direction_id"] = inferred
        result.payload.setdefault("rejections", [])
    if result.validation_error:
        raise CoverageAuditResponseError(result.validation_error, result.metadata)
    return result


def _eligible_candidate_count(candidates: Any) -> int:
    if not isinstance(candidates, list):
        return 0
    return sum(
        1
        for item in candidates
        if isinstance(item, dict)
        and item.get("recommendation") in {"include", "consider"}
    )


def _compact_recent_archive(archive: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in compact_archive(archive, limit=14):
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "date": item.get("date"),
                "stories": item.get("stories", []),
                "source_urls": item.get("source_urls", []),
            }
        )
    return result


def build_recall_sentinel_prompt(
    *,
    publication_date: str,
    search_window: dict[str, Any],
    existing_candidates: list[Any],
    archive: dict[str, Any],
) -> str:
    existing = [
        {
            "title": item.get("title"),
            "organization": item.get("organization"),
            "primary_source": item.get("primary_source"),
        }
        for item in existing_candidates
        if isinstance(item, dict)
    ]
    return f"""Ты — финальный high-signal recall sentinel редакции «ИИ-сводки».

Дата выпуска: {publication_date}
Строгое редакционное окно: {search_window.get('start_at', '')} → {search_window.get('end_at', '')}
Идентификатор направления: general_coverage_gaps

Основной research и все шесть обязательных coverage-проходов уже завершились,
но пригодный пул всё ещё равен нулю. Выполни РОВНО ОДИН широкий Web Search
по крупнейшим новостным агентствам, чтобы проверить, не пропущено ли явно
значимое ИИ-событие внутри окна. Не разбивай задачу на массив независимых
поисковых запросов и не пытайся заново исследовать весь интернет. После поиска
открой релевантные страницы, если это нужно для проверки даты и фактов; навигация
не считается дополнительной поисковой операцией.

Ищи только события высокой самостоятельной новостной ценности: новый или
существенно обновлённый frontier-модель/продукт, крупный security/cyber risk,
важный coding/agent релиз, чипы и инфраструктуру, значимое регулирование,
робототехнику, крупную инвестицию/сделку или существенное корпоративное
решение ведущей ИИ-компании. В первую очередь проверяй Reuters, AP, Bloomberg
и Financial Times. Путь URL или рубрика источника не определяют категорию
события.

Событие и основной источник обязаны попадать в окно. Старую перепечатку без
нового развития отклоняй. Для include/consider требуются verified и
freshness_status new_event/material_update. Если точного времени публикации
нет, используй published_at=null и time_precision=date. Не придумывай время.
Не добивай количество слабым материалом.

Уже найденные кандидаты:
{json.dumps(existing, ensure_ascii=False, indent=2)}

Недавний архив для дедупликации:
{json.dumps(_compact_recent_archive(archive), ensure_ascii=False, indent=2)}

Если достойное событие найдено, верни его кандидатом по заданной JSON-схеме.
Если нет, верни пустой candidates и status=complete_with_gaps. direction_id
должен быть строго general_coverage_gaps. Верни только JSON по схеме."""


def _existing_recall_sentinel(plan: dict[str, Any]) -> dict[str, Any] | None:
    attempts = plan.get("attempts")
    if not isinstance(attempts, list):
        return None
    for attempt in reversed(attempts):
        if (
            isinstance(attempt, dict)
            and attempt.get("search_strategy") == RECALL_SENTINEL_STRATEGY
            and attempt.get("status") in {"checked", "checked_with_gaps"}
        ):
            return attempt
    return None


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
    global _LAST_RECALL_SENTINEL

    plan = _BASE_EXECUTE_AUDIT_PLAN(
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
    )

    existing_sentinel = _existing_recall_sentinel(plan)
    if existing_sentinel is not None:
        _LAST_RECALL_SENTINEL = {
            "status": "reused",
            "search_strategy": RECALL_SENTINEL_STRATEGY,
            "attempt": existing_sentinel.get("attempt"),
            "actual_queries": existing_sentinel.get("actual_queries", []),
            "candidate_count": existing_sentinel.get("candidate_count", 0),
        }
        return plan

    budget = plan.get("search_budget")
    if not isinstance(budget, dict):
        return plan
    mandatory_complete = (
        plan.get("audit_status") in {"complete", "complete_with_gaps"}
        and set(plan.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
    )
    final_eligible = _eligible_candidate_count(existing_candidates) + _eligible_candidate_count(plan.get("candidates"))
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
        result = _policy_audit_request(
            api_key=api_key,
            model=model,
            prompt=prompt,
            maximum_web_search_calls=1,
            allowed_domains=RECALL_SENTINEL_DOMAINS,
        )
        payload = result.payload or {}
        if payload.get("status") not in {"complete", "complete_with_gaps"}:
            raise RuntimeError("Recall sentinel вернул непригодный status=" + repr(payload.get("status")))
    except Exception as exc:
        _LAST_RECALL_SENTINEL = {
            "status": "error",
            "search_strategy": RECALL_SENTINEL_STRATEGY,
            "allowed_domains": list(RECALL_SENTINEL_DOMAINS),
            "error": f"{type(exc).__name__}: {exc}",
        }
        plan["audit_status"] = "partial"
        budget["stop_reason"] = "recall_sentinel_incomplete"
        return plan

    metadata = result.metadata
    raw_candidates = payload.get("candidates")
    accepted_for_pass: list[dict[str, Any]] = []
    if isinstance(raw_candidates, list):
        for raw_candidate in raw_candidates:
            if not isinstance(raw_candidate, dict):
                continue
            candidate = copy.deepcopy(raw_candidate)
            candidate["audit_direction"] = "recall_sentinel"
            accepted_for_pass.append(candidate)

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
        "label": "High-signal recall sentinel",
        "required": True,
        "attempt": attempt_number,
        "search_strategy": RECALL_SENTINEL_STRATEGY,
        "allowed_domains": list(RECALL_SENTINEL_DOMAINS),
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
    budget["remaining_calls"] = max(0, maximum_web_search_calls - int(budget.get("completed_calls", 0) or 0))
    budget["provider_overrun"] = bool(budget.get("provider_overrun")) or completed > 1
    budget["exhausted"] = False
    budget["search_budget_exhausted"] = False
    budget["response_attempt_limit_exhausted"] = False
    budget["stop_reason"] = "recall_sentinel_completed"
    plan["api"] = _policy._aggregate_api_metadata(plan.get("attempts", []))
    _LAST_RECALL_SENTINEL = {
        "status": "complete" if payload_status == "complete" else "complete_with_gaps",
        "search_strategy": RECALL_SENTINEL_STRATEGY,
        "allowed_domains": list(RECALL_SENTINEL_DOMAINS),
        "attempt": attempt_number,
        "actual_queries": record["actual_queries"],
        "candidate_count": len(accepted_for_pass),
        "sources": record["sources"],
    }
    return plan


def _report_path() -> Path | None:
    try:
        index = sys.argv.index("--report")
        return Path(sys.argv[index + 1])
    except (ValueError, IndexError):
        return None


def _read_prior_report(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _primary_search_diagnostics(publication_date: str) -> dict[str, Any] | None:
    trajectory_path = REPOSITORY_ROOT / "automation" / "preview" / publication_date / "research-search-trajectory.json"
    if not trajectory_path.is_file():
        return None
    try:
        trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(trajectory, dict):
        return None

    per_operation: list[int] = []
    calls = trajectory.get("calls")
    if isinstance(calls, list):
        for call in calls:
            if not isinstance(call, dict) or call.get("action_type") != "search":
                continue
            action = call.get("action")
            if not isinstance(action, dict):
                action = {}
            queries: list[str] = []
            if action.get("query") is not None:
                query = str(action.get("query")).strip()
                if query:
                    queries.append(query)
            raw_queries = action.get("queries")
            if isinstance(raw_queries, list):
                for raw in raw_queries:
                    query = str(raw).strip()
                    if query and query not in queries:
                        queries.append(query)
            per_operation.append(len(queries))

    actual_queries = trajectory.get("actual_queries")
    logical_query_count = len(actual_queries) if isinstance(actual_queries, list) else 0
    completed_calls = int(trajectory.get("completed_calls", 0) or 0)
    return {
        "search_operation_count": completed_calls,
        "logical_query_count": logical_query_count,
        "queries_per_search_operation": per_operation,
        "query_batching_detected": any(count > 1 for count in per_operation),
    }


def _audit_search_diagnostics(report: dict[str, Any]) -> dict[str, Any]:
    operations = 0
    logical_queries = 0
    batched_attempts: list[dict[str, Any]] = []
    for attempt in report.get("attempts", []):
        if not isinstance(attempt, dict):
            continue
        api = attempt.get("api")
        completed = int(api.get("web_search_calls_completed", 0) or 0) if isinstance(api, dict) else 0
        queries = attempt.get("actual_queries")
        query_count = len(queries) if isinstance(queries, list) else 0
        operations += completed
        logical_queries += query_count
        if completed > 0 and query_count > completed:
            batched_attempts.append(
                {
                    "direction_id": attempt.get("direction_id"),
                    "attempt": attempt.get("attempt"),
                    "search_strategy": attempt.get("search_strategy"),
                    "search_operations": completed,
                    "logical_queries": query_count,
                }
            )
    return {
        "search_operation_count": operations,
        "logical_query_count": logical_queries,
        "query_batching_detected": bool(batched_attempts),
        "batched_attempts": batched_attempts,
    }


def _sync_policy_overrides() -> None:
    for name in (
        "RUNTIME_RESEARCH_ROOT",
        "PERSISTED_RESEARCH_ROOT",
        "PROMPT_PATH",
        "GENERATOR_PATH",
        "rerun_editorial",
    ):
        setattr(_policy, name, globals()[name])
    _policy.run_audit_request = _policy_audit_request
    _policy.execute_audit_plan = execute_audit_plan
    _policy.completed_prior_audit = completed_prior_audit


def _finalize_report(
    report_path: Path | None,
    prior_report: dict[str, Any] | None,
) -> None:
    if report_path is None or not report_path.is_file():
        return
    report = read_json(report_path)
    if not isinstance(report, dict):
        return

    report.setdefault("audit_state", "not_started")
    report.setdefault("validation_error", None)
    report.setdefault("error_stage", None)
    report.setdefault("api_output_path", None)
    report.setdefault("api_response_path", None)

    if _LAST_AUDIT_RESULTS:
        results = list(_LAST_AUDIT_RESULTS)
        prior_api_attempts = (prior_report or {}).get("api_attempts")
        report["api_attempts"] = (
            copy.deepcopy(prior_api_attempts)
            if isinstance(prior_api_attempts, list)
            else []
        ) + [item.metadata for item in results]
        completed_searches = sum(
            int(item.metadata.get("web_search_calls_completed", item.metadata.get("web_search_calls", 0)) or 0)
            for item in results
        )
        report["web_search_performed"] = completed_searches > 0
        prior_diagnostic_paths = (prior_report or {}).get("api_diagnostic_paths")
        diagnostic_paths: list[dict[str, str]] = (
            copy.deepcopy(prior_diagnostic_paths) if isinstance(prior_diagnostic_paths, list) else []
        )
        index_offset = len(diagnostic_paths)
        for index, item in enumerate(results, start=1 + index_offset):
            direction = str(item.payload.get("direction_id")) if isinstance(item.payload, dict) else "unknown"
            pass_dir = report_path.parent / "coverage-audit-passes"
            pass_dir.mkdir(parents=True, exist_ok=True)
            output_path = pass_dir / f"{index:02d}-{direction}-output.txt"
            response_path = pass_dir / f"{index:02d}-{direction}-response.json"
            output_path.write_text(item.output_text + ("\n" if item.output_text else ""), encoding="utf-8")
            response_path.write_text(
                json.dumps(item.raw_response, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            diagnostic_paths.append(
                {"direction_id": direction, "api_output_path": str(output_path), "api_response_path": str(response_path)}
            )
        report["api_diagnostic_paths"] = diagnostic_paths

        last_result = results[-1]
        report.update(persist_audit_diagnostics(last_result, report_path.parent))
        if len(results) == 1 and not report.get("api"):
            report["api"] = last_result.metadata

        audit_status = report.get("audit_status")
        usable_statuses = {"complete", "complete_with_gaps"}
        validation_errors = [item.validation_error for item in results if item.validation_error]
        if (
            audit_status in usable_statuses
            and not validation_errors
            and set(report.get("checked_directions") or ()) == set(AUDIT_DIRECTION_IDS)
        ):
            report["audit_state"] = "completed_usable"
        else:
            report["audit_state"] = "completed_unusable"
            if validation_errors:
                report["validation_error"] = "; ".join(validation_errors)
            elif audit_status == "error":
                report["validation_error"] = "Ни одно обязательное направление audit не было подтверждено фактическим поиском"
            report["error_stage"] = "response_validation"
    elif report.get("prior_audit_reused"):
        prior_state = (prior_report or {}).get("audit_state")
        if prior_state in {"completed_usable", "completed_unusable"}:
            report["audit_state"] = prior_state
        else:
            prior_api = (prior_report or {}).get("api") or {}
            prior_usable = (
                (prior_report or {}).get("status") == "ok"
                and isinstance(prior_api, dict)
                and prior_api.get("status") == "completed"
                and not (prior_report or {}).get("audit_error")
                and not (prior_report or {}).get("error")
            )
            report["audit_state"] = "completed_usable" if prior_usable else "completed_unusable"
        for key in ("api_output_path", "api_response_path", "validation_error"):
            if (prior_report or {}).get(key) is not None:
                report[key] = (prior_report or {}).get(key)
        if report["audit_state"] == "completed_unusable":
            report["error_stage"] = "response_validation"

    publication_date = str(report.get("publication_date") or "")
    primary_diagnostics = _primary_search_diagnostics(publication_date)
    if primary_diagnostics is not None:
        report["primary_search_retrieval"] = primary_diagnostics
    report["audit_search_retrieval"] = _audit_search_diagnostics(report)

    if _LAST_RECALL_SENTINEL is not None:
        report["recall_sentinel"] = copy.deepcopy(_LAST_RECALL_SENTINEL)
    elif isinstance((prior_report or {}).get("recall_sentinel"), dict):
        report["recall_sentinel"] = copy.deepcopy(prior_report["recall_sentinel"])

    sentinel = report.get("recall_sentinel")
    if isinstance(sentinel, dict):
        status = str(sentinel.get("status") or "")
        if status in {"complete", "complete_with_gaps", "reused"}:
            report["audit_notes"] = (
                "Шесть обязательных тематических проходов завершены; свободный "
                "седьмой вызов использован как high-signal recall sentinel, "
                "поскольку итоговый пригодный пул оставался нулевым."
            )
        elif status == "error":
            report["audit_notes"] = (
                "Шесть обязательных проходов завершены, но обязательный для "
                "нулевого пула high-signal recall sentinel технически не "
                "завершён; редакционная остановка не считается надёжной."
            )

    write_json(report_path, report)


def main() -> int:
    global _LAST_AUDIT_RESULT, _LAST_RECALL_SENTINEL

    _LAST_AUDIT_RESULT = None
    _LAST_RECALL_SENTINEL = None
    _LAST_AUDIT_RESULTS.clear()
    report_path = _report_path()
    prior_report = _read_prior_report(report_path)
    _sync_policy_overrides()
    result = _policy.main()
    _finalize_report(report_path, prior_report)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
