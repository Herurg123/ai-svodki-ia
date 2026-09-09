"""Aggregate saved source-contribution reports without counting recovery twice.

No score, source disabling, missing-as-zero imputation, network or API calls.
Conflicting observations of one publication date remain explicit unknowns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


METRICS = ("parsed_items", "window_items", "accepted_leads", "confirmed_promoted_count",
           "post_freshness_survivors", "editorial_selected", "assembled_stories", "repository_published")
EARLY_METRICS = set(METRICS[:4])


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def number(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def is_publication(report: dict[str, Any]) -> bool:
    proof = report.get("repository_publication_evidence")
    return isinstance(proof, dict) and proof.get("scope") == "repository_publication_on_origin_main"


def aggregate(reports: list[dict[str, Any]]) -> dict[str, Any]:
    unique = {digest(r): r for r in reports}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_sources = set()
    for report in unique.values():
        day = report.get("publication_date")
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("every report must identify its publication date")
        sources = report.get("sources")
        if not isinstance(sources, list) or any(not isinstance(s, dict) or not isinstance(s.get("source_id"), str) or not s["source_id"] for s in sources):
            raise ValueError("report source rows are missing or invalid")
        ids = [s["source_id"] for s in sources]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate source ID in one report")
        all_sources.update(ids)
        grouped[day].append(report)
    days = []
    for day, candidates in sorted(grouped.items()):
        observation_ids = {r.get("source_observation_id") for r in candidates}
        observation_conflict = None in observation_ids or len(observation_ids) != 1
        published = [r for r in candidates if is_publication(r)]
        # A committed final bundle outranks a local draft; never choose a draft
        # by timestamp, count, input order, or the amount of available evidence.
        traced = published or [r for r in candidates if r.get("trace_observation_id") is not None]
        trace_ids = {r.get("trace_observation_id") for r in traced}
        trace_conflict = None in trace_ids or len(trace_ids) > 1
        gaps = []
        if observation_conflict:
            gaps.append("source_observation_conflict_or_missing_identity")
        if trace_conflict:
            gaps.append("final_trace_conflict_or_missing_identity")
        source_rows = []
        for sid in sorted(all_sources):
            early = [s for r in candidates for s in r["sources"] if s["source_id"] == sid]
            late = [s for r in traced for s in r["sources"] if s["source_id"] == sid]
            row: dict[str, Any] = {"source_id": sid, "source_present": bool(early),
                                   "source_statuses": sorted({str(s.get("source_status", "unknown")) for s in early})}
            for metric in METRICS:
                choices = early if metric in EARLY_METRICS else late
                values = {n for s in choices if (n := number(s.get(metric))) is not None}
                uncertain = observation_conflict or (metric not in EARLY_METRICS and trace_conflict)
                if len(values) > 1:
                    gaps.append(f"metric_conflict:{sid}:{metric}")
                    uncertain = True
                row[metric] = next(iter(values)) if not uncertain and len(values) == 1 else None
            source_rows.append(row)
        days.append({"publication_date": day, "distinct_reports": len(candidates),
                     "source_observation_ids": sorted(str(v) for v in observation_ids),
                     "trace_selection": "committed_repository_bundle" if published else "saved_release_bundle",
                     "evidence_gaps": sorted(set(gaps)), "sources": source_rows})
    totals = []
    for sid in sorted(all_sources):
        values = [next(s for s in d["sources"] if s["source_id"] == sid) for d in days]
        metrics = {}
        for metric in METRICS:
            observed = [s[metric] for s in values if s[metric] is not None]
            metrics[metric] = {"observed_total": sum(observed), "observed_releases": len(observed),
                               "unknown_releases": len(days) - len(observed),
                               "complete_total": sum(observed) if len(observed) == len(days) else None}
        totals.append({"source_id": sid, "source_present_releases": sum(s["source_present"] for s in values), "metrics": metrics})
    return {"version": 1, "status": "diagnostic_only", "supplied_reports": len(reports),
            "exact_duplicate_reports_ignored": len(reports) - len(unique), "release_count": len(days),
            "days": days, "sources": totals, "network_calls": 0, "paid_api_calls": 0,
            "policy": "One observation per release date. Conflicts remain unknown. Observed sums exclude unknowns; complete_total is null when any release is unknown. Repository publication is not FTP delivery. No causal source ranking or automatic source changes."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in {p.resolve() for p in args.report}:
        parser.error("output must not replace an input report")
    values = [json.loads(path.read_bytes()) for path in args.report]
    if any(not isinstance(v, dict) for v in values):
        parser.error("each input must be a report object")
    result = aggregate(values)
    result["input_sha256"] = [hashlib.sha256(path.read_bytes()).hexdigest() for path in args.report]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
