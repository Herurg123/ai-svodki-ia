#!/usr/bin/env python3
"""Production-shadow Source Pulse diagnostics before Hybrid.

Stage 2 is deliberately non-influential: it fetches the fixed Source Pulse
registry, snapshots source health and fresh leads, and compares those leads with
the already-built Primary + agency-rescue candidate pool.  It never mutates
candidates, never calls OpenAI/Web Search, and is fail-open for the existing
retrieval pipeline.
"""
from __future__ import annotations

import copy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import source_pulse
from story_coverage import candidate_primary_url, read_json, write_json

SOURCE_PULSE_SHADOW_VERSION = 1
SOURCE_PULSE_SHADOW_STRATEGY = "source_pulse_shadow"
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "source-pulse-v1.json"

Collector = Callable[..., dict[str, Any]]


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Source Pulse shadow: {label} отсутствует")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError(f"Source Pulse shadow: {label} должен содержать timezone")
    return parsed


def _published_date(candidate: dict[str, Any]) -> date | None:
    value = candidate.get("published_date")
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _candidate_event_fingerprint(candidate: dict[str, Any]) -> str | None:
    title = candidate.get("title")
    published = _published_date(candidate)
    if not isinstance(title, str) or not title.strip() or published is None:
        return None
    return source_pulse.event_fingerprint(title, published)


def _eligible_candidates(research: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(item)
        for item in research.get("candidates", [])
        if isinstance(item, dict)
        and item.get("recommendation") in {"include", "consider"}
    ]


def build_fusion_diagnostics(
    snapshot: dict[str, Any], research: dict[str, Any]
) -> dict[str, Any]:
    """Compare the two discovery planes without changing either one."""
    candidates = _eligible_candidates(research)
    candidate_urls: dict[str, list[str]] = {}
    candidate_events: dict[str, list[str]] = {}
    candidate_ids: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        candidate_id = str(candidate.get("id") or candidate.get("candidate_id") or f"candidate-{index}")
        candidate_ids.append(candidate_id)
        url = candidate_primary_url(candidate)
        if url:
            candidate_urls.setdefault(source_pulse._normalized_url(url), []).append(candidate_id)
        event = _candidate_event_fingerprint(candidate)
        if event:
            candidate_events.setdefault(event, []).append(candidate_id)

    matched_candidate_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    for raw in snapshot.get("leads", []):
        if not isinstance(raw, dict):
            continue
        lead = copy.deepcopy(raw)
        url = lead.get("url")
        normalized_url = (
            source_pulse._normalized_url(url)
            if isinstance(url, str) and url.strip()
            else None
        )
        exact_matches = list(candidate_urls.get(normalized_url or "", []))
        event_matches = list(candidate_events.get(str(lead.get("event_fingerprint") or ""), []))
        matches = exact_matches or event_matches
        matched_candidate_ids.update(matches)

        if lead.get("cutoff_ambiguous") is True:
            disposition = "cutoff_ambiguous"
            actionable = False
        elif lead.get("archive_url_duplicate") is True:
            disposition = "archive_duplicate"
            actionable = False
        elif exact_matches:
            disposition = "both_exact_url"
            actionable = False
        elif event_matches:
            disposition = "both_event_fingerprint"
            actionable = False
        else:
            disposition = "pulse_only"
            actionable = True

        rows.append(
            {
                "source_id": lead.get("source_id"),
                "tier": lead.get("tier"),
                "region": lead.get("region"),
                "role": lead.get("role"),
                "title": lead.get("title"),
                "url": normalized_url,
                "published_date": lead.get("published_date"),
                "published_at": lead.get("published_at"),
                "time_precision": lead.get("time_precision"),
                "event_fingerprint": lead.get("event_fingerprint"),
                "exact_fingerprint": lead.get("exact_fingerprint"),
                "disposition": disposition,
                "matched_candidate_ids": matches,
                "actionable_shadow_lead": actionable,
            }
        )

    search_only = [item for item in candidate_ids if item not in matched_candidate_ids]
    both = [
        row
        for row in rows
        if row["disposition"] in {"both_exact_url", "both_event_fingerprint"}
    ]
    pulse_only = [row for row in rows if row["disposition"] == "pulse_only"]
    ambiguous = [row for row in rows if row["disposition"] == "cutoff_ambiguous"]
    archived = [row for row in rows if row["disposition"] == "archive_duplicate"]

    return {
        "version": 1,
        "candidate_influence": False,
        "matching_policy": "exact_url_then_conservative_title_date_event_fingerprint",
        "pulse_leads": rows,
        "search_candidate_ids": candidate_ids,
        "search_only_candidate_ids": search_only,
        "summary": {
            "pulse_total": len(rows),
            "pulse_only_count": len(pulse_only),
            "both_count": len(both),
            "search_only_count": len(search_only),
            "cutoff_ambiguous_count": len(ambiguous),
            "archive_duplicate_count": len(archived),
            "pulse_only_tier_a_count": sum(row.get("tier") == "A" for row in pulse_only),
            "pulse_only_tier_b_count": sum(row.get("tier") == "B" for row in pulse_only),
            "pulse_only_russia_count": sum(row.get("region") == "russia" for row in pulse_only),
            "pulse_only_china_asia_count": sum(row.get("region") == "china_asia" for row in pulse_only),
        },
    }


def _report_paths(
    artifact_dir: Path, output_root: Path, publication_date: str
) -> tuple[Path, Path]:
    return (
        artifact_dir / "source-pulse.json",
        output_root / f"source-pulse-{publication_date}.json",
    )


def _persist(
    report: dict[str, Any], *, artifact_dir: Path, output_root: Path,
    publication_date: str
) -> None:
    artifact_path, diagnostic_path = _report_paths(
        artifact_dir, output_root, publication_date
    )
    write_json(artifact_path, report)
    write_json(diagnostic_path, report)


def _prior_report(
    artifact_dir: Path, output_root: Path, publication_date: str
) -> dict[str, Any] | None:
    for path in _report_paths(artifact_dir, output_root, publication_date):
        if not path.is_file():
            continue
        try:
            value = read_json(path)
        except Exception:
            continue
        if (
            isinstance(value, dict)
            and value.get("version") == SOURCE_PULSE_SHADOW_VERSION
            and value.get("strategy") == SOURCE_PULSE_SHADOW_STRATEGY
            and value.get("publication_date") == publication_date
        ):
            return value
    return None


def compact_shadow_report(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    snapshot = report.get("snapshot")
    fusion = report.get("fusion")
    return {
        "version": report.get("version"),
        "strategy": report.get("strategy"),
        "publication_date": report.get("publication_date"),
        "status": report.get("status"),
        "state": report.get("state"),
        "reused_snapshot": report.get("reused_snapshot", False),
        "candidate_influence": False,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "snapshot_hash": snapshot.get("snapshot_hash") if isinstance(snapshot, dict) else None,
        "source_summary": copy.deepcopy(snapshot.get("summary")) if isinstance(snapshot, dict) else None,
        "fusion_summary": copy.deepcopy(fusion.get("summary")) if isinstance(fusion, dict) else None,
        "error": report.get("error"),
    }


def run_source_pulse_shadow(
    *,
    artifact_dir: Path,
    archive_path: Path,
    publication_date: str,
    output_root: Path,
    registry_path: Path = REGISTRY_PATH,
    collector_fn: Collector = source_pulse.run_source_pulse,
) -> dict[str, Any]:
    """Run at most once for an artifact and never influence publication."""
    prior = _prior_report(artifact_dir, output_root, publication_date)
    if prior is not None:
        reused = copy.deepcopy(prior)
        reused["reused_snapshot"] = True
        if reused.get("state") == "fetch_started":
            reused["status"] = "complete_with_gaps"
            reused["state"] = "interrupted_no_repoll"
            reused["error"] = (
                "Предыдущий Source Pulse snapshot был помечен fetch_started; "
                "для mutable sources повторный polling в том же artifact запрещён."
            )
        return reused

    report: dict[str, Any] = {
        "version": SOURCE_PULSE_SHADOW_VERSION,
        "strategy": SOURCE_PULSE_SHADOW_STRATEGY,
        "publication_date": publication_date,
        "status": "running",
        "state": "fetch_started",
        "candidate_influence": False,
        "repoll_on_recovery": False,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "reused_snapshot": False,
    }
    _persist(
        report,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )

    try:
        research = read_json(artifact_dir / "candidates.json")
        window = research.get("search_window") if isinstance(research, dict) else None
        if not isinstance(window, dict):
            raise RuntimeError("candidates.json не содержит search_window")
        start_at = _aware(window.get("start_at"), "search_window.start_at")
        end_at = _aware(window.get("end_at"), "search_window.end_at")
        archive = read_json(archive_path)
        registry = source_pulse.load_registry(registry_path)
        snapshot = collector_fn(
            registry=registry,
            start_at=start_at,
            end_at=end_at,
            archive=archive,
        )
        snapshot = copy.deepcopy(snapshot)
        snapshot["mode"] = "production_shadow"
        snapshot["production_integration"] = True
        snapshot["candidate_influence"] = False
        snapshot["repoll_on_recovery"] = False
        fusion = build_fusion_diagnostics(snapshot, research)
        report.update(
            {
                "status": "complete",
                "state": "completed",
                "snapshot": snapshot,
                "fusion": fusion,
                "error": None,
            }
        )
    except Exception as exc:
        report.update(
            {
                "status": "complete_with_gaps",
                "state": "error_nonfatal",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )

    _persist(
        report,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )
    return report
