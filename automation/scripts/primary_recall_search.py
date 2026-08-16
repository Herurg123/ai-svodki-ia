#!/usr/bin/env python3
"""Retrieval Quality v1 wrapper over the stable Primary Recall v2 engine.

The v2 search matrix remains untouched.  This layer preserves high-signal
unverified discoveries as first-class resolution evidence and records regional
health without adding a single paid search operation.
"""
from __future__ import annotations

import copy
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

_BASE_PATH = Path(__file__).with_name("primary_recall_search_v2.py")
_BASE_SPEC = importlib.util.spec_from_file_location("primary_recall_search_v2", _BASE_PATH)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)


def __getattr__(name: str) -> Any:
    """Preserve the historical module surface for tests and recovery hooks."""
    return getattr(_base, name)

_BASE_RUN_MATRIX = _base.run_primary_recall_matrix
_BASE_RUN_SEARCH = _base.run_primary_recall_search

RETRIEVAL_QUALITY_CONTRACT_VERSION = 1
UNRESOLVED_SIGNAL_VERSION = 1

_STRONG_SOURCE_HINTS: tuple[tuple[str, str], ...] = (
    ("reuters", "Reuters"),
    ("associated press", "Associated Press"),
    ("ap news", "Associated Press"),
    ("bloomberg", "Bloomberg"),
    ("financial times", "Financial Times"),
    ("wall street journal", "Wall Street Journal"),
    ("wsj", "Wall Street Journal"),
    ("official", "official source"),
)
_STRONG_EVENT_TERMS = (
    "investment", "invest", "funding", "financing", "guarantee", "acquisition",
    "merger", "m&a", "data center", "data centre", "chips", "semiconductor",
    "partnership", "strategic deal", "billion", "млрд", "инвест", "сделк",
    "поглощ", "дата-центр",
)
_MONEY_RE = re.compile(
    r"(?:\$|€|£)\s?\d+(?:[.,]\d+)?\s?(?:b|bn|m|million|billion|млн|млрд)?|"
    r"\b\d+(?:[.,]\d+)?\s?(?:million|billion|млн|млрд)\b",
    re.IGNORECASE,
)
# Conservative token extraction is intentional.  These are retrieval hints,
# not a NER truth source; greedy capitalized phrases can fuse title verbs with
# company names and break event clustering.
_ENTITY_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9.&-]*|[A-Z]{2,})\b")
_ENTITY_STOP = {
    "AI", "The", "Latest", "Plans", "Downsizes", "New", "Breaking", "Major",
    "Data", "Center", "Centre", "Billion", "Million", "Guarantee", "Investment",
    "Wall", "Street", "Journal", "Financial", "Times",
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _source_hint(text: str) -> str | None:
    folded = text.casefold()
    for needle, label in _STRONG_SOURCE_HINTS:
        if needle in folded:
            return label
    return None


def _money_anchors(text: str) -> list[str]:
    result: list[str] = []
    for match in _MONEY_RE.finditer(text):
        value = _clean_text(match.group(0))
        if value and value not in result:
            result.append(value)
    return result[:3]


def _entities(title: str) -> list[str]:
    result: list[str] = []
    for match in _ENTITY_RE.finditer(title):
        value = _clean_text(match.group(0)).strip(".,:;()[]{}")
        if not value or value in _ENTITY_STOP:
            continue
        if value not in result:
            result.append(value)
    return result[:8]


def _signal_score(title: str, reason: str) -> tuple[int, str | None, list[str]]:
    text = f"{title} {reason}".strip()
    folded = text.casefold()
    source = _source_hint(text)
    anchors = _money_anchors(text)
    score = 0
    if source:
        score += 2
    if any(term in folded for term in _STRONG_EVENT_TERMS):
        score += 2
    if anchors:
        score += 1
    if len(_entities(title)) >= 2:
        score += 1
    return min(score, 5), source, anchors


def collect_unresolved_signals(direction_reports: Any) -> list[dict[str, Any]]:
    """Promote `unverified` evidence; only strict high-signal rows require rescue.

    `entities`, `anchors` and `source_hint` are evidence, never mandatory query
    filters. Query construction is deliberately handled by the resolution stage.
    """
    signals: list[dict[str, Any]] = []
    if not isinstance(direction_reports, list):
        return signals
    for report in direction_reports:
        if not isinstance(report, dict):
            continue
        direction_id = _clean_text(report.get("direction_id")) or "unknown"
        rejections = report.get("model_rejections")
        if not isinstance(rejections, list):
            continue
        for index, rejection in enumerate(rejections, start=1):
            if not isinstance(rejection, dict) or rejection.get("reason_code") != "unverified":
                continue
            title = _clean_text(rejection.get("title"))
            reason = _clean_text(rejection.get("reason"))
            if not title or not reason:
                continue
            score, source, anchors = _signal_score(title, reason)
            signals.append(
                {
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
                }
            )
    return signals


def regional_health(direction_reports: Any) -> dict[str, Any]:
    reports = {
        str(item.get("direction_id")): item
        for item in direction_reports or []
        if isinstance(item, dict) and item.get("direction_id")
    }

    def row(ids: tuple[str, ...]) -> dict[str, Any]:
        selected = [reports.get(item) for item in ids]
        completed = all(
            isinstance(item, dict)
            and item.get("status") in {"complete", "complete_with_gaps"}
            for item in selected
        )
        accepted = sum(
            int(item.get("accepted_count", 0) or 0)
            for item in selected
            if isinstance(item, dict)
        )
        return {
            "directions": list(ids),
            "primary_completed": completed,
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
    enriched_research = copy.deepcopy(research)
    enriched_report = copy.deepcopy(report)
    signals = collect_unresolved_signals(enriched_report.get("directions"))
    regions = regional_health(enriched_report.get("directions"))
    for target in (enriched_research, enriched_report):
        target["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION
        target["unresolved_signals"] = copy.deepcopy(signals)
        target["regional_health"] = copy.deepcopy(regions)
    return enriched_research, enriched_report


def run_primary_recall_matrix(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    research, report = _BASE_RUN_MATRIX(*args, **kwargs)
    return _annotate(research, report)


def _sync_base_overrides() -> None:
    for name in (
        "REPOSITORY_ROOT", "PROMPT_PATH", "ARCHIVE_PATH", "SITE_CONFIG_PATH",
        "PREVIEW_ROOT", "PRODUCTION_PREVIEW_ROOT", "RUNTIME_RESEARCH_ROOT",
    ):
        if name in globals():
            setattr(_base, name, globals()[name])
    _base.run_primary_recall_matrix = run_primary_recall_matrix


def run_primary_recall_search(*args: Any, **kwargs: Any) -> tuple[Path, dict[str, Any]]:
    _sync_base_overrides()
    return _BASE_RUN_SEARCH(*args, **kwargs)
