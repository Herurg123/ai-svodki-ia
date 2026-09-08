"""Offline Source Pulse contribution inventory; does not rank or disable sources.

Reads one saved report. Candidate acceptance is distinct from editorial selection
and publication, which this first checkpoint deliberately leaves unknown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def records(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def build_report(pulse: dict[str, Any]) -> dict[str, Any]:
    snapshot = pulse.get("snapshot") or {}
    promotion = pulse.get("promotion")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    sources = records(snapshot.get("sources"))
    dispositions = records(promotion.get("lead_dispositions")) if isinstance(promotion, dict) else []
    promotion_available = isinstance(promotion, dict) and isinstance(promotion.get("lead_dispositions"), list)
    accepted = promotion.get("accepted_candidate_urls") if isinstance(promotion, dict) else None
    accepted_available = isinstance(accepted, list) and all(isinstance(url, str) for url in accepted)
    accepted_urls = set(accepted) if accepted_available else set()
    source_ids = [row.get("source_id") for row in sources]
    if any(not isinstance(s, str) or not s for s in source_ids):
        raise ValueError("source_id is missing")
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("duplicate source_id in snapshot")

    gaps = []
    unknown_sources = sorted({str(row.get("source_id")) for row in dispositions if row.get("source_id") not in source_ids})
    if unknown_sources:
        gaps.append("promotion_source_absent_from_snapshot:" + ",".join(unknown_sources))
    if not isinstance(snapshot.get("sources"), list):
        gaps.append("snapshot_sources_missing")
    if not promotion_available:
        gaps.append("promotion_dispositions_missing")
    if not accepted_available:
        gaps.append("accepted_candidate_urls_missing")

    rows = []
    for source in sources:
        sid = source["source_id"]
        decisions = [row for row in dispositions if row.get("source_id") == sid]
        # Preserve query parameters: Yandex article IDs live in the query string.
        # Title/company/host matches must never establish candidate acceptance.
        decision_counts = Counter(row.get("promotion_status") or "unknown" for row in decisions)
        verified_urls = set()
        for row in decisions:
            if row.get("promotion_status") != "promoted":
                continue
            # v1.2/v1.3 set promoted by membership of record.url in the
            # merge result. final_url is fetch evidence, not candidate identity.
            url = row.get("url")
            if accepted_available and url in accepted_urls:
                verified_urls.add(url)
            else:
                gaps.append(f"promoted_url_not_confirmed:{sid}:{url}")
        rows.append({
            "source_id": sid,
            "tier": source.get("tier"),
            "region": source.get("region"),
            "source_status": source.get("status", "unknown"),
            "parsed_items": count(source.get("parsed_items")),
            "window_items": count(source.get("window_items")),
            "accepted_leads": count(source.get("accepted_leads")),
            "promotion_decision_counts": dict(sorted(decision_counts.items())) if promotion_available else None,
            "promotion_reasons": dict(sorted(Counter(str(row.get("reason") or "unspecified") for row in decisions if row.get("promotion_status") != "promoted").items())) if promotion_available else None,
            "confirmed_promoted_urls": sorted(verified_urls) if promotion_available and accepted_available else None,
            "confirmed_promoted_count": len(verified_urls) if promotion_available and accepted_available else None,
            "post_freshness_survivors": None,
            "editorial_selected": None,
            "published": None,
        })
    return {
        "version": 1,
        "status": "partial_checkpoint",
        "publication_date": pulse.get("publication_date"),
        "snapshot_hash": snapshot.get("snapshot_hash"),
        "snapshot_reused": pulse.get("reused_snapshot"),
        "source_report_status": pulse.get("status"),
        "source_count": len(rows),
        "sources": sorted(rows, key=lambda row: row["source_id"]),
        "evidence_gaps": sorted(set(gaps)),
        "unobserved_stages": ["post_freshness", "editorial_selection", "publication"],
        "policy": "Single saved snapshot only. Unknown is null. Counts are not source usefulness scores; unavailable sources are not evidence of no news. No cross-release or recovery aggregation.",
        "network_calls": 0,
        "paid_api_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pulse", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.pulse.resolve() == args.output.resolve():
        parser.error("output must not overwrite the source report")
    raw = args.pulse.read_bytes()
    pulse = json.loads(raw)
    if not isinstance(pulse, dict):
        parser.error("source report must be a JSON object")
    report = build_report(pulse)
    report["input_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
