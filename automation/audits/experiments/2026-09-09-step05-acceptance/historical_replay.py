#!/usr/bin/env python3
"""Reproduce six saved Source Value observations without network or paid APIs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "automation/scripts"))
from source_pulse_value import build_report
from source_value_publication import load_publication
from source_value_period import aggregate

BASE = "8c50ca04068d23cef20917598bfa78f4f1da6536"
DAYS = ("2026-08-27", "2026-08-29", "2026-09-02", "2026-09-06", "2026-09-07")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "automation/preview/source-value-replay")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports, cases = [], []
    for day in DAYS:
        raw, bundle, proof = load_publication(ROOT, BASE, day)
        report = build_report(json.loads(raw), bundle)
        report["repository_publication_evidence"] = proof
        report["input_sha256"] = hashlib.sha256(raw).hexdigest()
        for row in report["sources"]:
            row["repository_published"] = row["assembled_stories"]
        reports.append(report)
        cases.append({"date": day, "input_sha256": proof["input_sha256"], "post_sha256": proof["post_sha256"],
                      "source_count": report["source_count"], "evidence_gaps": report["evidence_gaps"],
                      "positive_promotions": [{k: row[k] for k in ("source_id", "confirmed_promoted_count", "post_freshness_survivors", "editorial_selected", "repository_published")}
                                              for row in report["sources"] if row["confirmed_promoted_count"]]})
    raw = (ROOT / "automation/fixtures/recall/source-value-full-pulse-2026-09-08.json").read_bytes()
    report = build_report(json.loads(raw))
    report["input_sha256"] = hashlib.sha256(raw).hexdigest()
    reports.append(report)
    cases.append({"date": "2026-09-08", "input_sha256": report["input_sha256"], "source_count": report["source_count"],
                  "scope": "Saved Pulse only; editorial and publication unknown", "evidence_gaps": report["evidence_gaps"]})

    # Exercise both exact copies and ordinary changed recovery metadata.
    recovered = copy.deepcopy(reports[2])
    recovered["snapshot_reused"] = True
    ordinary = aggregate(reports)
    repeated = aggregate([*reports, copy.deepcopy(reports[2]), recovered])
    assert ordinary["sources"] == repeated["sources"]
    assert repeated["release_count"] == 6
    by_day = {r["publication_date"]: r for r in reports}
    nvidia = next(s for s in by_day["2026-09-02"]["sources"] if s["source_id"] == "nvidia_recent_news")
    yandex = next(s for s in by_day["2026-09-06"]["sources"] if s["source_id"] == "yandex_ir")
    assert (nvidia["confirmed_promoted_count"], nvidia["editorial_selected"], nvidia["repository_published"]) == (1, 1, 1)
    assert (yandex["confirmed_promoted_count"], yandex["editorial_selected"], yandex["repository_published"]) == (1, 0, 0)
    assert all(s["confirmed_promoted_count"] is None for s in by_day["2026-08-27"]["sources"])

    summary = {"baseline_main": BASE, "status": "pass", "cases": cases,
               "supplied_with_copies": repeated["supplied_reports"], "release_count": repeated["release_count"],
               "exact_duplicate_reports_ignored": repeated["exact_duplicate_reports_ignored"],
               "copy_and_recovery_totals_unchanged": ordinary["sources"] == repeated["sources"],
               "network_calls": 0, "paid_api_calls": 0}
    for name, value in [("historical-results.json", summary), ("period-results.json", repeated)]:
        (args.output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "pass", "releases": 6, "copy_and_recovery_totals_unchanged": True}))


if __name__ == "__main__":
    main()
