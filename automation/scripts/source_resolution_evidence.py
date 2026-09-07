"""Zero-network bridge from saved Source Freshness failures to resolution leads.

Publication still requires a new verified candidate, canonical merge/dedupe,
independent event/source freshness and editorial. An HTTP error is never proof.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Any


def _title(row: dict[str, Any]) -> str:
    return " ".join(str(row.get("title") or "").split()).casefold()


def _urls(row: dict[str, Any]) -> set[str]:
    return {
        str(source.get("url") or "").strip()
        for source in [row.get("primary_source"), *(row.get("supporting_sources") or [])]
        if isinstance(source, dict) and source.get("url")
    }


def collect_source_failure_signals(
    report: Any, primary: Any, *, search_window: dict[str, Any],
) -> list[dict[str, Any]]:
    """Use exact title + cited URL identity, never recycled candidate IDs alone."""
    if not isinstance(report, dict) or not isinstance(primary, dict):
        return []
    from primary_recall_search import _entities, _anchors

    originals = primary.get("accepted_events") or []
    final = primary.get("final_candidates") or []
    latest: dict[tuple[str, tuple[str, ...]], tuple[dict, dict]] = {}
    for run in report.get("runs") or []:
        if not isinstance(run, dict) or any(
            (run.get("search_window") or {}).get(key) != search_window.get(key)
            for key in ("start_at", "end_at")
        ):
            continue
        for record in run.get("candidates") or []:
            if not isinstance(record, dict) or record.get("status") == "skipped":
                continue
            proof_urls = {
                str(item.get("url") or "") for item in record.get("sources") or []
                if isinstance(item, dict) and item.get("url")
            }
            raw = record.get("candidate_evidence")
            if not isinstance(raw, dict):
                # Legacy compatibility: only the exact Primary final-cap row.
                matches = [
                    item for item in originals if isinstance(item, dict)
                    and _title(item) == _title(record)
                    and _urls(item) == proof_urls
                    and any(
                        isinstance(item_final, dict)
                        and _title(item_final) == _title(item)
                        and item_final.get("primary_url") == (item.get("primary_source") or {}).get("url")
                        for item_final in final
                    )
                ]
                if len(matches) != 1:
                    continue
                raw = matches[0]
            if _title(raw) != _title(record) or not proof_urls or _urls(raw) != proof_urls:
                continue
            latest[(_title(raw), tuple(sorted(proof_urls)))] = (raw, record)

    signals = []
    for identity, (raw, record) in sorted(latest.items()):
        if record.get("status") != "excluded_unverified_freshness":
            continue
        if record.get("event_freshness_status") == "stale":
            continue
        recommendation = record.get("original_recommendation")
        try:
            score = int(raw.get("significance_score", 0))
        except (TypeError, ValueError):
            continue
        if not (
            raw.get("verification_status") == "verified"
            and raw.get("freshness_status") in {"new_event", "material_update"}
            and raw.get("recommendation") == recommendation
            and ((recommendation == "include" and score >= 3)
                 or (recommendation == "consider" and score >= 4))
        ):
            continue
        source = raw.get("primary_source") or {}
        reason = ("Source Freshness could not verify cited publication dates. "
                  + str(raw.get("event_type") or "") + ". " + str(raw.get("event_summary") or ""))
        digest = hashlib.sha256(repr(identity).encode()).hexdigest()[:20]
        entities = _entities(str(raw.get("title") or ""))
        organization = str(raw.get("organization") or "").casefold()
        identity_tokens = [value.casefold() for value in entities
                           if value.casefold() not in organization]
        signals.append({
            "signal_id": "sig-source-" + digest,
            "version": 2, "status": "unresolved", "origin_direction": "source_freshness",
            "reason_code": "unverified", "title": raw.get("title"),
            "url": source.get("url"), "evidence_reason": reason,
            "rejection_evidence": {
                "candidate": copy.deepcopy(raw),
                "freshness_record": copy.deepcopy({key: value for key, value in record.items()
                                                    if key != "candidate_evidence"}),
            },
            "source_window_status": "unknown", "likely_significance_score": score,
            "entities": entities, "event_identity_tokens": identity_tokens,
            "anchors": _anchors(str(raw.get("title") or "")),
            "source_hint": source.get("publisher"), "resolution_required": True,
            "query_terms_are_hints_not_filters": True,
        })
    return signals
