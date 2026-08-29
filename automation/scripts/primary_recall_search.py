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
RETRIEVAL_QUALITY_CONTRACT_VERSION = 1
UNRESOLVED_SIGNAL_VERSION = 1

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


def collect_unresolved_signals(direction_reports: Any) -> list[dict[str, Any]]:
    """Preserve unverified evidence; only strict high-signal rows require rescue."""
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
            if not isinstance(rejection, dict) or rejection.get("reason_code") != "unverified":
                continue
            title, reason = _clean(rejection.get("title")), _clean(rejection.get("reason"))
            if not title or not reason:
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
    regions = regional_health(report.get("directions"))
    for target in (research, report):
        target["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        target["unresolved_signals"] = copy.deepcopy(signals)
        target["regional_health"] = copy.deepcopy(regions)
    return research, report


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
    """Run zero-paid Source Pulse v1.2 before the first editorial call.

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
        from source_pulse_supplement_v12 import compact_supplement_report, run_source_pulse_supplement

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
            "version": 12,
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
    _base.run_primary_recall_matrix = run_primary_recall_matrix
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
