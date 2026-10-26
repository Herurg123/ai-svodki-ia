#!/usr/bin/env python3
"""Offline Primary A/B evidence matrix. Does not adjudicate different URLs as events."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

DIRECTIONS = (
    "global_breaking", "major_agencies", "models_products_agents",
    "infrastructure_chips_cloud", "business_investment_partnerships",
    "china_asia_models", "china_asia_integrations", "russia",
    "developer_tools", "security_safety", "legal_regulation",
    "independent_missing_events",
)


def normalize_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    u = urlsplit(value.strip())
    if u.scheme not in ("https", "http") or not u.hostname:
        return ""
    query = urlencode(sorted((k, v) for k, v in parse_qsl(u.query)
                              if not k.lower().startswith("utm_")))
    return urlunsplit((u.scheme.lower(), u.hostname.lower(),
                       u.path.rstrip("/") or "/", query, ""))


def source_url(row: dict) -> str:
    src = row.get("primary_source")
    return normalize_url(src.get("url", "") if isinstance(src, dict) else "")


def flat_rows(label: str, report: dict) -> list[dict]:
    rows = []
    directions = report.get("directions")
    if not isinstance(directions, list):
        raise ValueError(label + ": no pass-level directions")
    if [d.get("direction_id") for d in directions] != list(DIRECTIONS[:len(directions)]):
        raise ValueError(label + ": changed direction order")
    for d in directions:
        for c in d.get("raw_candidates", []):
            if not isinstance(c, dict):
                continue
            url = source_url(c)
            key = hashlib.sha256((url or (label + "|" + c.get("title", "")))
                                 .encode()).hexdigest()[:16]
            rows.append({
                "model_side": label, "direction": d["direction_id"],
                "event_id_provisional": key,
                "title": c.get("title", ""), "organization": c.get("organization", ""),
                "category": c.get("category", ""), "geography": c.get("geography", ""),
                "event_date": c.get("event_date", ""),
                "published_at": c.get("published_at", ""),
                "primary_source_url": url,
                "significance_score": c.get("significance_score", ""),
                "verification_status": c.get("verification_status", ""),
                "freshness_status": c.get("freshness_status", ""),
                # Never infer final/eligible solely from raw candidate presence.
                "review_status": "needs_event_identity_and_freshness_check",
                "editorial_quality": "unreviewed",
            })
    return rows


def build(terra: dict, sol: dict) -> tuple[dict, list[dict]]:
    if (terra.get("publication_date") != "2026-10-22" or
            sol.get("publication_date") != "2026-10-22"):
        raise ValueError("Wrong date")
    tw, sw = terra.get("search_window", {}), sol.get("search_window", {})
    if tw.get("start_at") != sw.get("start_at") or tw.get("end_at") != sw.get("end_at"):
        raise ValueError("Research windows differ")
    tr, sr = terra.get("directions", []), sol.get("directions", [])
    rows = flat_rows("terra", terra) + flat_rows("sol", sol)
    ready = len(tr) == 12 and len(sr) == 12 and all(
        d.get("web_search_calls_completed") == 1 for d in tr + sr
    )
    url_sets = {}
    for side in ("terra", "sol"):
        url_sets[side] = {r["primary_source_url"] for r in rows
                          if r["model_side"] == side and r["primary_source_url"]}
    return ({
        "status": "ready_for_manual_event_review" if ready else "incomplete_search_matrix",
        "publication_date": "2026-10-22",
        "search_window": tw,
        "directions_terra": len(tr), "directions_sol": len(sr),
        "raw_candidates_terra": sum(r["model_side"] == "terra" for r in rows),
        "raw_candidates_sol": sum(r["model_side"] == "sol" for r in rows),
        "exact_source_url_overlap": len(url_sets["terra"] & url_sets["sol"]),
        "exact_source_url_only_terra": len(url_sets["terra"] - url_sets["sol"]),
        "exact_source_url_only_sol": len(url_sets["sol"] - url_sets["terra"]),
        "caution": (
            "Different source URLs may describe the same event. Exact-URL comparisons "
            "are NOT event-level discovery scores. Manual review must establish event "
            "identity, timing, significance, duplicate status, and factual correctness."
        ),
        "model_recommendation": "insufficient_evidence_until_manual_adjudication",
        "paid_api_calls": 0,
    }, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terra", type=Path, required=True)
    parser.add_argument("--sol", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    terra = json.loads(args.terra.read_text(encoding="utf-8"))
    sol = json.loads(args.sol.read_text(encoding="utf-8"))
    summary, rows = build(terra, sol)
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    (args.output_prefix.with_suffix(".json")).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path = args.output_prefix.with_suffix(".csv")
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["status"] != "ready_for_manual_event_review":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
