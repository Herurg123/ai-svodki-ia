from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Coverage policy: expose a pure fresh-agency predicate and make source
# health itself a reason to run mandatory Coverage, even when story count is full.
replace_once(
    "automation/scripts/ensure_story_coverage_policy.py",
    "import sys\nfrom pathlib import Path\n",
    "import sys\nfrom datetime import date, datetime\nfrom pathlib import Path\n",
)
replace_once(
    "automation/scripts/ensure_story_coverage_policy.py",
    "DEFAULT_MAXIMUM_AUDIT_CALLS = 7\n\nAUDIT_REJECTION_SCHEMA",
    '''DEFAULT_MAXIMUM_AUDIT_CALLS = 7\n\nAGENCY_SOURCE_HEALTH_DOMAINS: tuple[str, ...] = (\n    "reuters.com",\n    "apnews.com",\n    "bloomberg.com",\n    "ft.com",\n)\n\n\ndef _host_matches_domain(url: str, domains: tuple[str, ...]) -> bool:\n    try:\n        host = (urlsplit(url).hostname or "").casefold().strip(".")\n    except ValueError:\n        return False\n    return any(host == domain or host.endswith("." + domain) for domain in domains)\n\n\ndef _search_window_days(search_window: dict[str, Any]) -> tuple[date, date] | None:\n    try:\n        start = datetime.fromisoformat(\n            str(search_window.get("start_at") or "").replace("Z", "+00:00")\n        )\n        end = datetime.fromisoformat(\n            str(search_window.get("end_at") or "").replace("Z", "+00:00")\n        )\n    except ValueError:\n        return None\n    if start.tzinfo is None or end.tzinfo is None or end < start:\n        return None\n    return start.date(), end.date()\n\n\ndef _candidate_has_fresh_agency_source(\n    candidate: Any, search_window: dict[str, Any]\n) -> bool:\n    if not isinstance(candidate, dict):\n        return False\n    if candidate.get("recommendation") == "exclude":\n        return False\n    window = _search_window_days(search_window)\n    if window is None:\n        return False\n    try:\n        published = date.fromisoformat(str(candidate.get("published_date") or ""))\n    except ValueError:\n        return False\n    if not (window[0] <= published <= window[1]):\n        return False\n    source = candidate.get("primary_source")\n    return bool(\n        isinstance(source, dict)\n        and isinstance(source.get("url"), str)\n        and _host_matches_domain(source["url"], AGENCY_SOURCE_HEALTH_DOMAINS)\n    )\n\n\ndef _candidates_have_fresh_agency_source(\n    candidates: Any, search_window: dict[str, Any]\n) -> bool:\n    return bool(\n        isinstance(candidates, list)\n        and any(\n            _candidate_has_fresh_agency_source(item, search_window)\n            for item in candidates\n        )\n    )\n\n\nAUDIT_REJECTION_SCHEMA''',
)
replace_once(
    "automation/scripts/ensure_story_coverage_policy.py",
    '''        if (\n            artifact_mode == "complete"\n            and before["publication_allowed"]\n            and before["usual_target_met"]\n        ):\n            apply_short_edition_marker(args.artifact_dir, short_edition=False)\n            report["status"] = "ok"\n            report["mode"] = "existing_full_digest"\n            report["publication_mode"] = "full"\n            report["after"] = before\n            report["candidate_pool_after"] = candidate_pool\n            write_json(args.report, report)\n            print(json.dumps(report, ensure_ascii=False, indent=2))\n            return 0\n\n        report["audit_needed"] = (\n            not before["usual_target_met"]\n            or candidate_pool["total"] < args.usual_total\n        )\n''',
    '''        search_window = research.get("search_window")\n        if not isinstance(search_window, dict):\n            raise RuntimeError("candidates.json не содержит search_window")\n        source_health_rescue_needed = bool(\n            candidate_pool["total"] > 0\n            and not _candidates_have_fresh_agency_source(\n                research["candidates"], search_window\n            )\n        )\n        report["source_health_rescue_needed"] = source_health_rescue_needed\n\n        if (\n            artifact_mode == "complete"\n            and before["publication_allowed"]\n            and before["usual_target_met"]\n            and not source_health_rescue_needed\n        ):\n            apply_short_edition_marker(args.artifact_dir, short_edition=False)\n            report["status"] = "ok"\n            report["mode"] = "existing_full_digest"\n            report["publication_mode"] = "full"\n            report["after"] = before\n            report["candidate_pool_after"] = candidate_pool\n            write_json(args.report, report)\n            print(json.dumps(report, ensure_ascii=False, indent=2))\n            return 0\n\n        report["audit_needed"] = (\n            not before["usual_target_met"]\n            or candidate_pool["total"] < args.usual_total\n            or source_health_rescue_needed\n        )\n''',
)

# 2) Runtime wrapper: the seventh Coverage slot becomes dual-use. Zero pool
# keeps the broad sentinel; non-zero pool without fresh agency evidence gets one
# bounded Reuters/AP rescue. Old non-zero reports must be re-evaluated once.
p = Path("automation/scripts/ensure_story_coverage.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    '_LAST_RECALL_SENTINEL: dict[str, Any] | None = None\n\nRECALL_SENTINEL_STRATEGY',
    '_LAST_RECALL_SENTINEL: dict[str, Any] | None = None\n_LAST_AGENCY_RESCUE: dict[str, Any] | None = None\n\nRECALL_SENTINEL_STRATEGY',
    1,
)
text = text.replace(
    'RECALL_SENTINEL_MINIMUM_BUDGET = 7\n',
    '''RECALL_SENTINEL_MINIMUM_BUDGET = 7\nAGENCY_RESCUE_STRATEGY = "fresh_agency_rescue"\nAGENCY_RESCUE_VERSION = 1\nAGENCY_RESCUE_DOMAINS: tuple[str, ...] = ("reuters.com", "apnews.com")\nSOURCE_HEALTH_CONTRACT_VERSION = 1\n''',
    1,
)
text = text.replace(
    '''def _set_last_recall_sentinel(value: dict[str, Any] | None) -> None:\n    global _LAST_RECALL_SENTINEL\n    _LAST_RECALL_SENTINEL = value\n    _base._LAST_RECALL_SENTINEL = value\n\n\ndef _pool_total''',
    '''def _set_last_recall_sentinel(value: dict[str, Any] | None) -> None:\n    global _LAST_RECALL_SENTINEL\n    _LAST_RECALL_SENTINEL = value\n    _base._LAST_RECALL_SENTINEL = value\n\n\ndef _set_last_agency_rescue(value: dict[str, Any] | None) -> None:\n    global _LAST_AGENCY_RESCUE\n    _LAST_AGENCY_RESCUE = value\n\n\ndef _pool_total''',
    1,
)
text = text.replace(
    '''    if _pool_total(payload) == 0 and not _completed_sentinel_evidence(payload):\n        return False\n    return True\n''',
    '''    pool_total = _pool_total(payload)\n    if pool_total == 0 and not _completed_sentinel_evidence(payload):\n        return False\n    if (\n        isinstance(pool_total, int)\n        and pool_total > 0\n        and payload.get("source_health_contract_version")\n        != SOURCE_HEALTH_CONTRACT_VERSION\n    ):\n        return False\n    return True\n''',
    1,
)
text = text.replace(
    '''def _rebuild_directions(\n    prior_directions: Any,\n    attempts: list[dict[str, Any]],\n) -> list[dict[str, Any]]:\n''',
    '''def _is_supplemental_attempt(item: Any) -> bool:\n    return bool(\n        isinstance(item, dict)\n        and item.get("search_strategy")\n        in {RECALL_SENTINEL_STRATEGY, AGENCY_RESCUE_STRATEGY}\n    )\n\n\ndef _rebuild_directions(\n    prior_directions: Any,\n    attempts: list[dict[str, Any]],\n) -> list[dict[str, Any]]:\n''',
    1,
)
text = text.replace(
    '''        if direction_id not in AUDIT_DIRECTION_IDS:\n            continue\n''',
    '''        if direction_id not in AUDIT_DIRECTION_IDS or _is_supplemental_attempt(item):\n            continue\n''',
    1,
)
text = text.replace(
    '''                and item.get("direction_id") in AUDIT_DIRECTION_IDS\n                and not _is_stale_sentinel_attempt(item)\n''',
    '''                and item.get("direction_id") in AUDIT_DIRECTION_IDS\n                and not _is_stale_sentinel_attempt(item)\n                and not _is_supplemental_attempt(item)\n''',
    1,
)
marker = '''def _existing_recall_sentinel(plan: dict[str, Any]) -> dict[str, Any] | None:\n'''
if marker not in text:
    raise SystemExit("sentinel marker missing")
agency_block = r'''
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


'''
text = text.replace(marker, agency_block + marker, 1)
text = text.replace(
    '''    existing_sentinel = _existing_recall_sentinel(plan)\n    if existing_sentinel is not None:\n''',
    '''    existing_sentinel = _existing_recall_sentinel(plan)\n    if existing_sentinel is not None:\n''',
    1,
)
needle = '''        )\n        return plan\n\n    budget = plan.get("search_budget")\n'''
pos = text.find(needle, text.find("existing_sentinel = _existing_recall_sentinel(plan)"))
if pos < 0:
    raise SystemExit("existing sentinel return marker missing")
insert = '''        )\n        return plan\n\n    existing_rescue = _existing_agency_rescue(plan)\n    if existing_rescue is not None:\n        _set_last_agency_rescue(\n            {\n                "status": "reused",\n                "version": AGENCY_RESCUE_VERSION,\n                "search_strategy": AGENCY_RESCUE_STRATEGY,\n                "allowed_domains": list(AGENCY_RESCUE_DOMAINS),\n                "attempt": existing_rescue.get("attempt"),\n                "actual_queries": existing_rescue.get("actual_queries", []),\n                "candidate_count": existing_rescue.get("candidate_count", 0),\n            }\n        )\n        return plan\n\n    budget = plan.get("search_budget")\n'''
text = text[:pos] + text[pos:].replace(needle, insert, 1)
needle = '''    final_eligible = _base._eligible_candidate_count(\n        existing_candidates\n    ) + _base._eligible_candidate_count(plan.get("candidates"))\n    remaining_calls = int(budget.get("remaining_calls", 0) or 0)\n    if not (\n'''
replacement = '''    final_eligible = _base._eligible_candidate_count(\n        existing_candidates\n    ) + _base._eligible_candidate_count(plan.get("candidates"))\n    remaining_calls = int(budget.get("remaining_calls", 0) or 0)\n    combined_candidates = list(existing_candidates) + list(plan.get("candidates") or [])\n    agency_rescue_needed = bool(\n        final_eligible > 0\n        and not _policy._candidates_have_fresh_agency_source(\n            combined_candidates, search_window\n        )\n    )\n    if (\n        maximum_web_search_calls >= RECALL_SENTINEL_MINIMUM_BUDGET\n        and mandatory_complete\n        and agency_rescue_needed\n        and remaining_calls >= 1\n    ):\n        return _run_agency_rescue(\n            plan=plan,\n            budget=budget,\n            api_key=api_key,\n            model=model,\n            search_window=search_window,\n            existing_candidates=combined_candidates,\n            archive=archive,\n            maximum_web_search_calls=maximum_web_search_calls,\n        )\n\n    if not (\n'''
if needle not in text:
    raise SystemExit("execute budget marker missing")
text = text.replace(needle, replacement, 1)
# Add post-base report finalization without touching the preserved runtime base.
main_marker = '''def main() -> int:\n    _set_last_recall_sentinel(None)\n    _sync_policy_overrides()\n    result = int(_base.main())\n    # _base.main() resets and then populates the shared sentinel diagnostics.\n    _set_last_recall_sentinel(_base._LAST_RECALL_SENTINEL)\n    if result != 0 and _promote_completed_zero_pool_editorial_stop(_base._report_path()):\n        return 0\n    return result\n'''
main_replacement = r'''def _finalize_source_health_report(report_path: Path | None) -> None:
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
'''
if main_marker not in text:
    raise SystemExit("wrapper main marker missing")
text = text.replace(main_marker, main_replacement, 1)
p.write_text(text, encoding="utf-8")

# 3) Normalizer: keep the fresh-agency requirement, but allow mandatory Coverage
# to satisfy it through the final validated candidate pool.
replace_once(
    "automation/scripts/normalize_digest_artifact.py",
    '''def _direction_has_fresh_agency_evidence(\n    direction: dict[str, Any], *, start_day: date, end_day: date\n) -> bool:\n''',
    '''def _artifact_has_fresh_agency_evidence(\n    artifact_dir: Path, *, start_day: date, end_day: date\n) -> bool:\n    candidates_path = artifact_dir / "candidates.json"\n    if not candidates_path.is_file():\n        return False\n    payload = read_json(candidates_path)\n    candidates = payload.get("candidates") if isinstance(payload, dict) else payload\n    if not isinstance(candidates, list):\n        return False\n    return any(\n        _candidate_has_fresh_agency_evidence(\n            candidate, start_day=start_day, end_day=end_day\n        )\n        for candidate in candidates\n    )\n\n\ndef _direction_has_fresh_agency_evidence(\n    direction: dict[str, Any], *, start_day: date, end_day: date\n) -> bool:\n''',
)
replace_once(
    "automation/scripts/normalize_digest_artifact.py",
    '''        if not any(\n            _direction_has_fresh_agency_evidence(\n                item, start_day=start_day, end_day=end_day\n            )\n            for item in directions\n            if isinstance(item, dict)\n        ):\n            raise NormalizationError(\n                "Primary Recall source-health degraded: ни одно из 12 Primary-направлений "\n                "не подтвердило свежий Reuters/AP/Bloomberg/FT материал в effective "\n                "window; служебные, author и старые newsletter URL не считаются "\n                "доказательством свежего agency retrieval."\n            )\n''',
    '''        primary_has_fresh_agency = any(\n            _direction_has_fresh_agency_evidence(\n                item, start_day=start_day, end_day=end_day\n            )\n            for item in directions\n            if isinstance(item, dict)\n        )\n        final_pool_has_fresh_agency = _artifact_has_fresh_agency_evidence(\n            artifact_dir, start_day=start_day, end_day=end_day\n        )\n        if not (primary_has_fresh_agency or final_pool_has_fresh_agency):\n            raise NormalizationError(\n                "Primary Recall source-health degraded: ни Primary diagnostics, ни "\n                "финальный validated candidate pool после mandatory Coverage не "\n                "подтвердили свежий Reuters/AP/Bloomberg/FT материал в effective "\n                "window; служебные, author и старые newsletter URL не считаются "\n                "доказательством свежего agency retrieval."\n            )\n''',
)

# 4) Existing sentinel test: a non-zero Reuters candidate is already source-healthy
# and therefore should consume neither kind of seventh-slot rescue.
replace_once(
    "automation/tests/test_recall_sentinel.py",
    '''    def test_sentinel_is_not_used_when_pool_is_nonzero(self) -> None:\n        existing = [{"recommendation": "include"}]\n''',
    '''    def test_sentinel_is_not_used_when_pool_is_nonzero(self) -> None:\n        existing = [candidate()]\n''',
)

# 5) New focused regression tests for the seventh-slot agency rescue and recovery
# versioning. This reproduces the Aug 14 production shape: non-zero TechCrunch-only
# pool after six completed Coverage passes.
Path("automation/tests/test_agency_rescue.py").write_text(r'''from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_module("agency_rescue_runtime", SCRIPTS / "ensure_story_coverage.py")

SEARCH_WINDOW = {
    "start_at": "2026-08-12T02:58:08+03:00",
    "end_at": "2026-08-14T08:03:43+03:00",
}


def metadata(query: str) -> dict[str, object]:
    return {
        "status": "completed",
        "web_search_calls": 1,
        "web_search_calls_completed": 1,
        "web_search_call_items_total": 1,
        "web_search_call_statuses": {"completed": 1},
        "web_search_search_statuses": {"completed": 1},
        "web_search_action_type_counts": {"search": 1},
        "web_search_navigation_items_total": 0,
        "actual_queries": [query],
        "consulted_sources": [
            {
                "title": "Reuters AI story",
                "url": "https://www.reuters.com/world/china/fresh-ai-story-2026-08-13/",
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }


def attempt(direction_id: str) -> dict[str, object]:
    return {
        "direction_id": direction_id,
        "label": direction_id,
        "required": True,
        "attempt": 1,
        "search_strategy": "targeted_topic_search",
        "allowed_domains": [],
        "status": "checked_with_gaps",
        "outcome": "no_news_found",
        "actual_queries": [f"{direction_id} query"],
        "sources": [],
        "candidate_count": 0,
        "candidates": [],
        "rejections": [],
        "notes": "checked",
        "api": metadata(f"{direction_id} query"),
        "error": None,
    }


def complete_plan() -> dict[str, object]:
    attempts = [attempt(item) for item in runtime.AUDIT_DIRECTION_IDS]
    return {
        "audit_status": "complete_with_gaps",
        "required_directions": list(runtime.AUDIT_DIRECTION_IDS),
        "checked_directions": list(runtime.AUDIT_DIRECTION_IDS),
        "partial_directions": [],
        "unchecked_directions": [],
        "directions": copy.deepcopy(attempts),
        "attempts": attempts,
        "search_budget": {
            "maximum_calls": 7,
            "minimum_required_calls": 6,
            "response_attempts": 6,
            "observed_call_items": 6,
            "completed_calls": 6,
            "remaining_calls": 1,
            "exhausted": False,
            "search_budget_exhausted": False,
            "response_attempt_limit_exhausted": False,
            "provider_overrun": False,
            "stop_reason": "all_required_directions_checked",
        },
        "api": {"status": "completed"},
        "candidates": [],
        "time_precision_warnings": [],
    }


def candidate(*, publisher: str, url: str, title: str = "AI event") -> dict[str, object]:
    return {
        "title": title,
        "organization": "Example AI",
        "published_date": "2026-08-13",
        "published_at": "2026-08-13T12:00:00+00:00",
        "time_precision": "datetime",
        "topic": "AI",
        "event_type": "model_launch",
        "keywords": ["AI", "launch"],
        "geography": "world",
        "category": "models",
        "source_type": "news_agency" if "reuters.com" in url else "technology_media",
        "primary_source": {"title": title, "publisher": publisher, "url": url},
        "supporting_sources": [],
        "event_summary": "Fresh event.",
        "verified_facts": ["Fact one.", "Fact two."],
        "significance": "Major event.",
        "significance_score": 5,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "Not in archive.",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "Verified.",
        "freshness_status": "new_event",
        "freshness_reason": "Inside window.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


class AgencyRescueTests(unittest.TestCase):
    def test_nonzero_tech_media_pool_uses_seventh_slot_for_reuters_ap_rescue(self):
        existing = [
            candidate(
                publisher="TechCrunch",
                url="https://techcrunch.com/2026/08/13/existing-ai-story/",
                title="Existing TechCrunch story",
            )
        ]
        rescued = candidate(
            publisher="Reuters",
            url="https://www.reuters.com/world/china/new-ai-model-2026-08-13/",
            title="New Reuters story",
        )

        def fake_request(**kwargs):
            return (
                {
                    "status": "complete",
                    "error_message": None,
                    "direction_id": "general_coverage_gaps",
                    "candidates": [rescued],
                    "rejections": [],
                    "notes": "Found independent missing event.",
                },
                metadata("latest major artificial intelligence news"),
            )

        with (
            mock.patch.object(
                runtime, "_BASE_EXECUTE_AUDIT_PLAN", return_value=complete_plan()
            ),
            mock.patch.object(runtime, "run_audit_request", side_effect=fake_request) as request,
        ):
            result = runtime.execute_audit_plan(
                api_key="secret",
                model="gpt-5.6-terra",
                template="unused",
                publication_date="2026-08-14",
                search_window=SEARCH_WINDOW,
                missing_total=0,
                maximum_web_search_calls=7,
                existing_candidates=existing,
                archive={"items": []},
            )

        self.assertEqual(request.call_count, 1)
        call = request.call_args.kwargs
        self.assertEqual(tuple(call["allowed_domains"]), runtime.AGENCY_RESCUE_DOMAINS)
        self.assertEqual(call["maximum_web_search_calls"], 1)
        self.assertIn("latest major artificial intelligence news", call["prompt"])
        self.assertIn("НЕТ в текущем пуле", call["prompt"])
        rescue = result["attempts"][-1]
        self.assertEqual(rescue["search_strategy"], runtime.AGENCY_RESCUE_STRATEGY)
        self.assertEqual(rescue["agency_rescue_version"], runtime.AGENCY_RESCUE_VERSION)
        self.assertEqual(rescue["candidate_count"], 1)
        self.assertEqual(result["candidates"][-1]["audit_direction"], "agency_rescue")
        self.assertEqual(result["search_budget"]["completed_calls"], 7)
        self.assertEqual(result["search_budget"]["remaining_calls"], 0)

    def test_fresh_agency_candidate_does_not_spend_seventh_slot(self):
        existing = [
            candidate(
                publisher="Reuters",
                url="https://www.reuters.com/technology/current-ai-story-2026-08-13/",
            )
        ]
        with (
            mock.patch.object(
                runtime, "_BASE_EXECUTE_AUDIT_PLAN", return_value=complete_plan()
            ),
            mock.patch.object(runtime, "run_audit_request") as request,
        ):
            result = runtime.execute_audit_plan(
                api_key="secret",
                model="gpt-5.6-terra",
                template="unused",
                publication_date="2026-08-14",
                search_window=SEARCH_WINDOW,
                missing_total=0,
                maximum_web_search_calls=7,
                existing_candidates=existing,
                archive={"items": []},
            )
        self.assertEqual(request.call_count, 0)
        self.assertEqual(result["search_budget"]["completed_calls"], 6)

    def test_legacy_nonzero_audit_is_replayed_once_under_source_health_contract(self):
        report = complete_plan()
        report.update(
            {
                "audit_state": "completed_usable",
                "web_search_performed": True,
                "candidate_pool_after": {"total": 7},
            }
        )
        self.assertFalse(runtime.completed_prior_audit(report))
        report["source_health_contract_version"] = runtime.SOURCE_HEALTH_CONTRACT_VERSION
        self.assertTrue(runtime.completed_prior_audit(report))


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

# 6) Normalizer regression: fresh Reuters candidate recovered by mandatory
# Coverage satisfies the same gate even when Primary's agency sweep was stale.
p = Path("automation/tests/test_digest_artifact_primary_normalization.py")
text = p.read_text(encoding="utf-8")
marker = '''    def test_current_dated_reuters_article_is_fresh_source_health_evidence(self):\n'''
insert = r'''    def test_final_coverage_pool_can_supply_fresh_agency_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=[
                    "https://www.bloomberg.com/authors/EXAMPLE/example-author",
                    "https://www.bloomberg.com/news/newsletters/2026-04-09/old-ai-newsletter",
                ],
                other_sources=["https://openai.com/index/example", "https://nvidia.com/example"],
                with_search_window=True,
            )
            write_json(
                artifact / "candidates.json",
                {
                    "candidates": [
                        {
                            "published_date": "2026-08-12",
                            "primary_source": {
                                "url": "https://www.reuters.com/technology/fresh-coverage-rescue-2026-08-12/"
                            },
                        }
                    ]
                },
            )
            normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )

'''
if marker not in text:
    raise SystemExit("normalizer test insertion marker missing")
text = text.replace(marker, insert + marker, 1)
p.write_text(text, encoding="utf-8")

# 7) Documentation. Fix the stale automation matrix while recording the new
# dual-use seventh slot and final-pool source-health boundary.
replace_once(
    "automation/README.md",
    "2. `major_agencies` — Reuters, AP, Bloomberg, FT;",
    "2. `major_agencies` — дополнительный high-signal sweep по Bloomberg и Financial Times;",
)
for path in ("README.md", "automation/README.md", "AGENTS.md"):
    p = Path(path)
    value = p.read_text(encoding="utf-8")
    note = r'''
### Fresh-agency source-health rescue

Ненулевой candidate pool не считается автоматически здоровым только потому, что
он содержит достаточно сюжетов. Если после Primary/Hybrid и шести обязательных
Coverage-направлений в текущем валидном пуле нет ни одного свежего
Reuters/AP/Bloomberg/FT-кандидата, свободный **седьмой** Coverage search operation
используется как bounded `fresh_agency_rescue`: один date-free запрос
`latest major artificial intelligence news` с API domain filter только на
Reuters + AP. Bloomberg/FT уже имеют отдельный `major_agencies` шанс в Primary.
Rescue ищет новое самостоятельное событие, отсутствующее в текущем пуле; простой
дубликат существующего сюжета не считается исправлением source-health.

Для нулевого пула тот же седьмой слот по-прежнему занят source-neutral recall
sentinel v8. Эти два режима взаимоисключающие, поэтому общий worst-case бюджет не
растёт: **12 Primary + до 4 Hybrid + до 7 Coverage = максимум 23 search
operations**. Технический сбой обязательного rescue остаётся fail-closed.
Normalizer принимает свежую agency evidence либо из Primary diagnostics, либо из
финального validated candidate pool после mandatory Coverage; он не требует,
чтобы найденный агентский материал возник именно в Primary-слое.
'''
    if "### Fresh-agency source-health rescue" not in value:
        value = value.rstrip() + "\n\n" + note.strip() + "\n"
    p.write_text(value, encoding="utf-8")

# Patcher is temporary and must never survive in the final PR tree.
Path(".github/_tmp_apply_agency_rescue.py").unlink()
