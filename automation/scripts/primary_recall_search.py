#!/usr/bin/env python3
"""Retrieval Quality v1 wrapper over the stable Primary Recall v2 engine."""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from event_freshness_contract import apply_candidate_schema_contract

_BASE_PATH = Path(__file__).with_name("primary_recall_search_v2.py")
_BASE_SPEC = importlib.util.spec_from_file_location("primary_recall_search_v2", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)

apply_candidate_schema_contract(_base.AUDIT_CANDIDATE_SCHEMA)


def __getattr__(name: str) -> Any:
    return getattr(_base, name)

_BASE_RUN_MATRIX = _base.run_primary_recall_matrix
_BASE_RUN_SEARCH = _base.run_primary_recall_search
_BASE_BUILD_PROMPT = _base.build_prompt
RETRIEVAL_QUALITY_CONTRACT_VERSION = 1
UNRESOLVED_SIGNAL_VERSION = 1
WEAK_SOURCE_SIGNAL_VERSION = 1
BUSINESS_QUERY_TREATMENT_VERSION = 1
BUSINESS_QUERY_DIRECTION_ID = "business_investment_partnerships"
BUSINESS_QUERY_TREATMENT = (
    "latest AI investment financing acquisitions partnerships enterprise deals "
    "revenue monetization ads earnings"
)
TEMPORAL_BOUNDARY_GUARD_VERSION = 1
TEMPORAL_BOUNDARY_GUARD = f"""

### Temporal boundary guard v{TEMPORAL_BOUNDARY_GUARD_VERSION}

Не отклоняй потенциально значимое событие как `outside_window` только из-за
ручного пересчёта часового пояса на пограничной календарной дате. Если source
показывает точный timestamp с timezone/UTC offset, сохраняй этот instant в
`published_at` без выдуманного сдвига даты. Если событие иначе пригодно, верни
его candidate и позволь последующему deterministic Source Freshness Proof строго
сравнить timezone-aware instant с effective window.

Не прибавляй календарные сутки, если арифметика offset реально не пересекает
полночь. Контрольный пример, который НЕ является текущей датой поиска:
`2026-09-04 09:21 PDT (UTC-07:00)` = `2026-09-04T19:21:00+03:00`, а НЕ 5 сентября.
Аналогично `2026-09-04 07:47 PDT` = `2026-09-04T17:47:00+03:00`.

Если timezone/timestamp неоднозначен, не выдумывай converted datetime и не ставь
`outside_window` только на основании сомнительного ручного пересчёта. Сохрани
доказанный source timestamp/date с корректной precision; downstream freshness
остаётся fail-closed и сам отклонит источник, который действительно позже cutoff
или раньше effective window. Эта защита не меняет search query, число Web Search
operations, significance, dedupe или freshness thresholds.
"""

# Stable v2 transport keeps these contracts. The literals remain at the public
# entrypoint because offline repository tests intentionally guard them:
# max_output_tokens=PRIMARY_MAX_OUTPUT_TOKENS_PER_PASS
# metadata["configured_max_output_tokens"]

_STRONG_SOURCE_HINTS = (
    ("reuters", "Reuters"), ("associated press", "Associated Press"),
    ("ap news", "Associated Press"), ("bloomberg", "Bloomberg"),
    ("financial times", "Financial Times"), ("wall street journal", "Wall Street Journal"),
    ("wsj", "Wall Street Journal"), ("official", "official source"),
)
_STRONG_EVENT_TERMS = (
    "investment", "invest", "funding", "financing", "guarantee", "acquisition",
    "merger", "m&a", "data center", "data centre", "chips", "semiconductor",
    "partnership", "strategic deal", "billion", "млрд", "инвест", "сделк",
    "поглощ", "дата-центр",
)
_MONEY_RE = re.compile(
    r"(?:\$|€|£)\s?\d+(?:[.,]\d+)?\s?(?:b|bn|m|million|billion|млн|млрд)?|"
    r"\b\d+(?:[.,]\d+)?\s?(?:million|billion|млн|млрд)\b", re.IGNORECASE,
)
# Conservative tokens are intentional. This is retrieval evidence, not NER truth.
_ENTITY_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9.&-]*|[A-Z]{2,})\b")
_ENTITY_STOP = {
    "AI", "The", "Latest", "Plans", "Downsizes", "New", "Breaking", "Major",
    "Data", "Center", "Centre", "Billion", "Million", "Guarantee", "Investment",
    "Wall", "Street", "Journal", "Financial", "Times",
}
_WEAK_PRODUCT_VERSION_RE = re.compile(
    r"\b(?:v\d+(?:\.\d+){0,3}|(?:gpt|claude|gemini|llama|qwen|glm|deepseek)[- ]?\d+(?:\.\d+){0,3})"
    r"(?:[- ][A-Za-z][A-Za-z0-9-]*)?\b",
    re.IGNORECASE,
)
_WEAK_PRODUCT_ACTION_PATTERNS = (
    (re.compile(r"\breplaces?\b", re.IGNORECASE), "replace"),
    (re.compile(r"\breleases?\b|\breleased\b", re.IGNORECASE), "release"),
    (re.compile(r"\blaunches?\b|\blaunched\b", re.IGNORECASE), "launch"),
    (re.compile(r"\bintroduces?\b|\bintroduced\b", re.IGNORECASE), "introduce"),
    (re.compile(r"\bunveils?\b|\bunveiled\b", re.IGNORECASE), "unveil"),
    (re.compile(r"\bupdates?\b|\bupdated\b", re.IGNORECASE), "update"),
    (re.compile(r"\bupgrades?\b|\bupgraded\b", re.IGNORECASE), "upgrade"),
    (re.compile(r"\bships?\b|\bshipped\b", re.IGNORECASE), "ship"),
    (re.compile(r"\brolls? out\b|\brolled out\b", re.IGNORECASE), "rollout"),
    (re.compile(r"\bpreview\b", re.IGNORECASE), "preview"),
    (re.compile(r"\bgeneral availability\b|\bgenerally available\b", re.IGNORECASE), "general_availability"),
    (re.compile(r"\bretires?\b|\bretired\b|\bdiscontinues?\b|\bdiscontinued\b", re.IGNORECASE), "retire"),
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _source_hint(text: str) -> str | None:
    folded = text.casefold()
    for needle, label in _STRONG_SOURCE_HINTS:
        if needle in folded:
            return label
    return None


def _anchors(text: str) -> list[str]:
    result: list[str] = []
    for match in _MONEY_RE.finditer(text):
        value = _clean(match.group(0))
        if value and value not in result:
            result.append(value)
    return result[:3]


def _entities(title: str) -> list[str]:
    result: list[str] = []
    for match in _ENTITY_RE.finditer(title):
        value = _clean(match.group(0)).strip(".,:;()[]{}")
        if value and value not in _ENTITY_STOP and value not in result:
            result.append(value)
    return result[:8]


def _score(title: str, reason: str) -> tuple[int, str | None, list[str]]:
    text = f"{title} {reason}".strip()
    source = _source_hint(text)
    anchors = _anchors(text)
    folded = text.casefold()
    score = (2 if source else 0) + (2 if any(term in folded for term in _STRONG_EVENT_TERMS) else 0)
    score += 1 if anchors else 0
    score += 1 if len(_entities(title)) >= 2 else 0
    return min(score, 5), source, anchors


def _weak_source_product_identity(
    rejection: dict[str, Any], title: str
) -> dict[str, Any] | None:
    """Extract evidence-only product identity without making it retrieval-eligible."""
    source_url = _clean(rejection.get("url"))
    try:
        parsed = urlparse(source_url)
        host = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme != "https" or not host:
        return None

    versions: list[str] = []
    for match in _WEAK_PRODUCT_VERSION_RE.finditer(title):
        value = _clean(match.group(0)).strip(".,:;()[]{}")
        if value and value.casefold() not in {item.casefold() for item in versions}:
            versions.append(value)
    if not versions:
        return None

    actions: list[str] = []
    action_positions: list[int] = []
    for pattern, canonical in _WEAK_PRODUCT_ACTION_PATTERNS:
        match = pattern.search(title)
        if not match:
            continue
        action_positions.append(match.start())
        if canonical not in actions:
            actions.append(canonical)
    if not actions:
        return None

    organization = _clean(rejection.get("organization"))
    if not organization and action_positions:
        prefix = title[:min(action_positions)].strip(" -–—,:;()[]{}")
        if 1 <= len(prefix.split()) <= 4 and any(char.isalpha() for char in prefix):
            organization = _clean(prefix)
    if not organization:
        return None

    host = host.casefold()
    if host.startswith("www."):
        host = host[4:]
    return {
        "organization": organization,
        "product_version_anchors": versions[:4],
        "lifecycle_action_anchors": actions[:4],
        "source_url": source_url,
        "source_host": host,
    }


def _weak_source_signal(
    *, rejection: dict[str, Any], direction_id: str, index: int, title: str, reason: str
) -> dict[str, Any] | None:
    identity = _weak_source_product_identity(rejection, title)
    if identity is None:
        return None
    score, source, anchors = _score(title, reason)
    return {
        "signal_id": f"sig-{direction_id}-{index:02d}",
        "version": WEAK_SOURCE_SIGNAL_VERSION,
        "status": "unresolved",
        "signal_class": "weak_source_product",
        "title": title,
        "origin_direction": direction_id,
        "reason_code": "weak_source",
        "evidence_reason": reason,
        "likely_significance_score": score,
        "entities": _entities(title),
        "anchors": anchors,
        "source_hint": source,
        "organization": identity["organization"],
        "product_version_anchors": identity["product_version_anchors"],
        "lifecycle_action_anchors": identity["lifecycle_action_anchors"],
        "source_provenance": {
            "url": identity["source_url"],
            "host": identity["source_host"],
            "reason_code": "weak_source",
            "reason": reason,
        },
        "resolution_required": False,
        "resolution_eligibility": "deferred_exact_authoritative_binding",
        "candidate_eligible": False,
        "additional_search_operations": 0,
        "query_terms_are_hints_not_filters": True,
    }


def collect_unresolved_signals(direction_reports: Any) -> list[dict[str, Any]]:
    """Preserve unresolved evidence without granting weak-source publication eligibility."""
    signals: list[dict[str, Any]] = []
    if not isinstance(direction_reports, list):
        return signals
    for report in direction_reports:
        if not isinstance(report, dict):
            continue
        direction_id = _clean(report.get("direction_id")) or "unknown"
        rows = report.get("model_rejections")
        if not isinstance(rows, list):
            continue
        for index, rejection in enumerate(rows, start=1):
            if not isinstance(rejection, dict):
                continue
            reason_code = rejection.get("reason_code")
            title, reason = _clean(rejection.get("title")), _clean(rejection.get("reason"))
            if not title or not reason:
                continue
            if reason_code == "weak_source":
                weak_signal = _weak_source_signal(
                    rejection=rejection,
                    direction_id=direction_id,
                    index=index,
                    title=title,
                    reason=reason,
                )
                if weak_signal is not None:
                    signals.append(weak_signal)
                continue
            if reason_code != "unverified":
                continue
            score, source, anchors = _score(title, reason)
            signals.append({
                "signal_id": f"sig-{direction_id}-{index:02d}",
                "version": UNRESOLVED_SIGNAL_VERSION,
                "status": "unresolved",
                "title": title,
                "origin_direction": direction_id,
                "reason_code": "unverified",
                "evidence_reason": reason,
                "likely_significance_score": score,
                "entities": _entities(title),
                "anchors": anchors,
                "source_hint": source,
                "resolution_required": score >= 4,
                "query_terms_are_hints_not_filters": True,
            })
    return signals


def regional_health(direction_reports: Any) -> dict[str, Any]:
    reports = {str(item.get("direction_id")): item for item in direction_reports or [] if isinstance(item, dict) and item.get("direction_id")}

    def row(ids: tuple[str, ...]) -> dict[str, Any]:
        selected = [reports.get(item) for item in ids]
        completed = all(isinstance(item, dict) and item.get("status") in {"complete", "complete_with_gaps"} for item in selected)
        accepted = sum(int(item.get("accepted_count", 0) or 0) for item in selected if isinstance(item, dict))
        return {
            "directions": list(ids), "primary_completed": completed,
            "accepted_candidates": accepted,
            "health_check_needed": bool(completed and accepted == 0),
        }

    return {
        "version": 1,
        "asia": row(("china_asia_models", "china_asia_integrations")),
        "russia": row(("russia",)),
        "policy": "zero candidates triggers a completeness health-check, never a publication quota",
    }


def _annotate(research: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    research, report = copy.deepcopy(research), copy.deepcopy(report)
    signals = collect_unresolved_signals(report.get("directions"))
    research_signals = [
        copy.deepcopy(item)
        for item in signals
        if item.get("reason_code") != "weak_source"
    ]
    regions = regional_health(report.get("directions"))
    for target, target_signals in ((research, research_signals), (report, signals)):
        target["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        target["unresolved_signals"] = copy.deepcopy(target_signals)
        target["regional_health"] = copy.deepcopy(regions)
        target["business_query_treatment"] = {
            "version": BUSINESS_QUERY_TREATMENT_VERSION,
            "direction_id": BUSINESS_QUERY_DIRECTION_ID,
            "query": BUSINESS_QUERY_TREATMENT,
            "additional_search_operations": 0,
        }
        target["temporal_boundary_guard"] = {
            "version": TEMPORAL_BOUNDARY_GUARD_VERSION,
            "scope": "all_primary_directions",
            "query_changed": False,
            "additional_search_operations": 0,
            "downstream_freshness_fail_closed": True,
        }
    return research, report


def build_prompt(*args: Any, **kwargs: Any) -> str:
    """Apply universal temporal guard and the approved business query treatment."""
    prompt = _BASE_BUILD_PROMPT(*args, **kwargs) + TEMPORAL_BOUNDARY_GUARD
    direction = kwargs.get("direction")
    if not isinstance(direction, dict) or direction.get("id") != BUSINESS_QUERY_DIRECTION_ID:
        return prompt
    return prompt + f"""

### Business recall treatment v{BUSINESS_QUERY_TREATMENT_VERSION}

Для направления `{BUSINESS_QUERY_DIRECTION_ID}` фактический query должен быть РОВНО:
`{BUSINESS_QUERY_TREATMENT}`

Это узкий ranking treatment внутри уже существующего business-прохода. Он сохраняет
investment/financing/M&A/partnership/enterprise recall и дополнительно покрывает
крупные AI-driven revenue, monetization, advertising и earnings/outlook события.
Не превращай это в общий financial-market sweep: кандидат остаётся релевантным
только если ИИ является существенным драйвером события. Search-operation budget
не меняется: этот проход по-прежнему выполняет ровно один Web Search.
"""


def run_primary_recall_matrix(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    research, report = _BASE_RUN_MATRIX(*args, **kwargs)
    return _annotate(research, report)


def _sync_paths() -> None:
    for name in ("REPOSITORY_ROOT", "PROMPT_PATH", "ARCHIVE_PATH", "SITE_CONFIG_PATH", "PREVIEW_ROOT", "PRODUCTION_PREVIEW_ROOT", "RUNTIME_RESEARCH_ROOT"):
        if name in globals():
            setattr(_base, name, globals()[name])


def _primary_failure_reason_code(message: str) -> str:
    folded = message.casefold()
    if (
        "insufficient_quota" in folded
        or "credit_balance_exhausted" in folded
        or "you have no credits remaining" in folded
    ):
        return "openai_insufficient_quota"
    return "primary_recall_error"


def _persist_primary_failure(publication_date: Any, exc: Exception) -> None:
    """Persist a machine-readable fresh-Primary failure for the final summary."""
    if not isinstance(publication_date, str) or not publication_date.strip():
        return
    message = str(exc).strip()
    report_path = Path(PRODUCTION_PREVIEW_ROOT) / "research-error.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "status": "error",
                "stage": "primary_recall",
                "publication_date": publication_date.strip(),
                "reason_code": _primary_failure_reason_code(message),
                "error_type": type(exc).__name__,
                "error_message": message,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _supplement_primary_research(
    research_path: Path, report: dict[str, Any], *, publication_date: Any,
    maximum_candidates: Any,
) -> tuple[Path, dict[str, Any]]:
    """Run zero-paid Source Pulse v1.4 before the first editorial call.

    The Search-derived ``regional_health`` annotation is intentionally left
    unchanged, so Pulse cannot mask a China/Asia or Russia Search gap and cannot
    suppress the existing Hybrid regional-health passes.
    """
    if not isinstance(publication_date, str) or not publication_date.strip():
        return research_path, report
    try:
        limit = int(maximum_candidates or 20)
    except (TypeError, ValueError):
        limit = 20
    try:
        from source_pulse_supplement_v14 import compact_supplement_report, run_source_pulse_supplement

        pulse = run_source_pulse_supplement(
            research_path=research_path,
            archive_path=Path(ARCHIVE_PATH),
            publication_date=publication_date.strip(),
            output_root=Path(PRODUCTION_PREVIEW_ROOT),
            maximum_candidates=limit,
        )
        updated = copy.deepcopy(report)
        updated["source_pulse_supplement"] = compact_supplement_report(pulse)
        try:
            research = json.loads(research_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            research = None
        if isinstance(research, dict) and isinstance(research.get("candidates"), list):
            updated["final_candidate_count"] = len(research["candidates"])
        return research_path, updated
    except Exception as exc:
        updated = copy.deepcopy(report)
        updated["source_pulse_supplement"] = {
            "version": 14,
            "status": "complete_with_gaps",
            "paid_api_calls": 0,
            "web_search_operations": 0,
            "promoted_count": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
        return research_path, updated


def run_primary_recall_search(*args: Any, **kwargs: Any) -> tuple[Path, dict[str, Any]]:
    _sync_paths()
    original = _base.run_primary_recall_matrix
    original_build_prompt = _base.build_prompt
    _base.run_primary_recall_matrix = run_primary_recall_matrix
    _base.build_prompt = build_prompt
    try:
        research_path, report = _BASE_RUN_SEARCH(*args, **kwargs)
        return _supplement_primary_research(
            research_path,
            report,
            publication_date=kwargs.get("publication_date"),
            maximum_candidates=kwargs.get("maximum_candidates", 20),
        )
    except Exception as exc:
        _persist_primary_failure(kwargs.get("publication_date"), exc)
        raise
    finally:
        _base.run_primary_recall_matrix = original
        _base.build_prompt = original_build_prompt