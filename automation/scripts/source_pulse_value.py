"""Offline Source Pulse contribution inventory; does not rank or disable sources.

Reads one saved report and optional final release artifacts. Candidate acceptance,
editorial selection, assembly and publication remain distinct evidence stages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from source_value_identity import digest, nonempty, valid_url


def count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def build_report(pulse: dict[str, Any], bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(pulse, dict):
        raise ValueError("Pulse report must be an object")
    snapshot = pulse.get("snapshot", {})
    promotion = pulse.get("promotion")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    sources = snapshot.get("sources", [])
    if not isinstance(sources, list) or any(not isinstance(s, dict) for s in sources):
        raise ValueError("snapshot sources must be an array of objects")
    raw_dispositions = promotion.get("lead_dispositions") if isinstance(promotion, dict) else None
    dispositions_valid = isinstance(raw_dispositions, list) and all(isinstance(d, dict) for d in raw_dispositions)
    dispositions = raw_dispositions if dispositions_valid else []
    accepted = promotion.get("accepted_candidate_urls") if isinstance(promotion, dict) else None
    accepted_available = isinstance(accepted, list) and all(valid_url(url) for url in accepted)
    accepted_urls = set(accepted) if accepted_available else set()
    source_ids = [row.get("source_id") for row in sources]
    if any(not nonempty(s) for s in source_ids):
        raise ValueError("source_id is missing")
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("duplicate source_id in snapshot")

    gaps = []
    unknown_sources = sorted({str(row.get("source_id")) for row in dispositions if row.get("source_id") not in source_ids})
    if unknown_sources:
        gaps.append("promotion_source_absent_from_snapshot:" + ",".join(unknown_sources))
    if not isinstance(snapshot.get("sources"), list):
        gaps.append("snapshot_sources_missing")
    if not dispositions_valid:
        gaps.append("promotion_dispositions_missing_or_malformed")
    if not accepted_available:
        gaps.append("accepted_candidate_urls_missing_or_malformed")
    if accepted_available and len(accepted_urls) != len(accepted):
        gaps.append("accepted_candidate_urls_duplicated")
    if any(not valid_url(d.get("url")) or not isinstance(d.get("promotion_status"), str)
           or d["promotion_status"] not in {"promoted", "rejected", "not_eligible"} for d in dispositions):
        gaps.append("promotion_disposition_identity_or_status_invalid")
    disposition_urls = [d.get("url") for d in dispositions if valid_url(d.get("url"))]
    if len(set(disposition_urls)) != len(disposition_urls):
        gaps.append("promotion_disposition_url_duplicated")
    promoted_urls = {d["url"] for d in dispositions if d.get("promotion_status") == "promoted" and valid_url(d.get("url"))}
    if dispositions_valid and accepted_available and promoted_urls != accepted_urls:
        gaps.append("promotion_and_accepted_urls_conflict")
    if isinstance(promotion, dict) and "promoted_count" in promotion and count(promotion["promoted_count"]) != len(accepted_urls):
        gaps.append("promotion_count_conflict")
    # A damaged global merge/disposition ledger cannot prove attribution to any
    # one source. Keep the gap instead of silently dropping rows or duplicates.
    promotion_available = not gaps

    rows = []
    for source in sources:
        sid = source["source_id"]
        decisions = [row for row in dispositions if row.get("source_id") == sid]
        # Preserve query parameters: Yandex article IDs live in the query string.
        # Title/company/host matches must never establish candidate acceptance.
        decision_counts = Counter(str(row.get("promotion_status") or "unknown") for row in decisions)
        verified_urls = set()
        promotion_complete = promotion_available
        if count(source.get("accepted_leads")) is not None and source["accepted_leads"] != len(decisions):
            promotion_complete = False
            gaps.append(f"source_lead_disposition_count_conflict:{sid}")
        for row in decisions:
            if row.get("promotion_status") != "promoted":
                continue
            # v1.2/v1.3 set promoted by membership of record.url in the
            # merge result. final_url is fetch evidence, not candidate identity.
            url = row.get("url")
            if accepted_available and isinstance(url, str) and url and url in accepted_urls:
                verified_urls.add(url)
            else:
                promotion_complete = False
                gaps.append(f"promoted_url_not_confirmed:{sid}:{url}")
        reported_counts = {k: count(source.get(k)) for k in ("parsed_items", "window_items", "accepted_leads")}
        observed_counts = reported_counts.copy()
        if source.get("status") != "ok":
            observed_counts = dict.fromkeys(reported_counts)
            gaps.append(f"source_observation_unavailable:{sid}")
        for key, value in reported_counts.items():
            if value is None:
                gaps.append(f"source_count_missing_or_invalid:{sid}:{key}")
        row = {
            "source_id": sid,
            "tier": source.get("tier"),
            "region": source.get("region"),
            "source_status": source.get("status", "unknown"),
            **observed_counts,
            "reported_counts": reported_counts,
            "promotion_decision_counts": dict(sorted(decision_counts.items())) if promotion_available else None,
            "promotion_reasons": dict(sorted(Counter(str(row.get("reason") or "unspecified") for row in decisions if row.get("promotion_status") != "promoted").items())) if promotion_available else None,
            "confirmed_promoted_urls": sorted(verified_urls) if promotion_complete else None,
            "confirmed_promoted_count": len(verified_urls) if promotion_complete else None,
            "promotion_evidence_complete": promotion_complete,
            "post_freshness_survivors": None,
            "editorial_selected": None,
            "assembled_stories": None,
            "repository_published": None,
            "published": None,
        }
        rows.append(row)
    result = {
        "version": 3,
        "status": "diagnostic_only",
        "publication_date": pulse.get("publication_date"),
        "snapshot_hash": snapshot.get("snapshot_hash"),
        "snapshot_reused": pulse.get("reused_snapshot"),
        "source_report_status": pulse.get("status"),
        "source_observation_id": digest({"publication_date": pulse.get("publication_date"), "snapshot": snapshot, "promotion": promotion}),
        "trace_observation_id": None,
        "source_count": len(rows),
        "sources": sorted(rows, key=lambda row: row["source_id"]),
        "evidence_gaps": sorted(set(gaps)),
        "unobserved_stages": ["post_freshness", "editorial_selection", "publication"],
        "policy": "Unknown is null. Raw collector counters remain separately reported. Exact snapshot/promotion identity excludes later fusion/reuse metadata. Counts are not usefulness scores; unavailable sources are not evidence of no news.",
        "network_calls": 0,
        "paid_api_calls": 0,
    }
    if bundle is not None:
        from source_pulse_trace import add_trace
        add_trace(result, pulse, bundle)
        result["trace_observation_id"] = digest({"source_observation_id": result["source_observation_id"], "bundle": bundle})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pulse", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--release-dir", type=Path, help="Saved candidate/editorial/story artifacts from the same release")
    inputs.add_argument("--published-repo", type=Path, help="Local Git repository; reads committed artifacts, never fetches")
    parser.add_argument("--published-commit", help="Full commit SHA reachable from the local origin/main reference")
    args = parser.parse_args()
    if args.pulse.resolve() == args.output.resolve():
        parser.error("output must not overwrite the source report")
    raw = args.pulse.read_bytes()
    pulse = json.loads(raw)
    if not isinstance(pulse, dict):
        parser.error("source report must be a JSON object")
    bundle = None
    publication = None
    input_hashes = {}
    if bool(args.published_repo) != bool(args.published_commit):
        parser.error("published-repo and published-commit must be provided together")
    if args.published_repo:
        from source_value_publication import load_publication
        try:
            committed_pulse, bundle, publication = load_publication(args.published_repo, args.published_commit, pulse.get("publication_date", ""))
            if committed_pulse != raw:
                raise ValueError("Pulse input differs from the committed release; cross-run attribution rejected")
        except (ValueError, TypeError, OSError) as exc:
            parser.error(str(exc))
    if args.release_dir:
        bundle = {}
        for key, name in [("candidates", "candidates.json"), ("editorial", "editorial-output.json"), ("stories", "stories.json")]:
            path = args.release_dir / name
            if args.output.resolve() == path.resolve():
                parser.error("output must not overwrite an input artifact")
            if path.is_file():
                data = path.read_bytes()
                bundle[key] = json.loads(data)
                input_hashes[name] = hashlib.sha256(data).hexdigest()
    report = build_report(pulse, bundle)
    if publication is not None:
        report["repository_publication_evidence"] = publication
        for row in report["sources"]:
            row["repository_published"] = row.get("assembled_stories")
        # Retain published=null: this offline reader cannot attest FTP delivery.
        report["unobserved_stages"] = ["ftp_publication" if stage == "publication" else stage for stage in report["unobserved_stages"]]
    report["input_sha256"] = hashlib.sha256(raw).hexdigest()
    report["release_input_sha256"] = input_hashes
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
