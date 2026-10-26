#!/usr/bin/env python3
"""23 Oct 2026 Sol shadow Primary: independent, manual, fail-closed, no publication."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "automation/scripts"))
DATE = "2026-10-23"
CUTOFF = "2026-10-23T04:31:19+03:00"
START = "2026-10-21T04:32:02+03:00"
FROZEN_CODE = "071c1d6c2777de461d5e74b33d851e64a1d5f473"
MODEL = "gpt-6.1-sol"
MAX_REQUESTS = 12
MAX_ESTIMATE_USD = 1.0
NEXT_RESERVE_USD = 0.16
OUT = ROOT / "automation/preview/sol-shadow-2026-10-23"
RUN = OUT / "execution.json"
STATE = {
    "status": "not_started", "publication_date": DATE, "model": MODEL,
    "reasoning": "medium", "initial_commit": FROZEN_CODE,
    "search_window": {"start_at": START, "end_at": CUTOFF},
    "max_new_api_requests": MAX_REQUESTS,
    "max_client_tier_adjusted_estimate_usd": MAX_ESTIMATE_USD,
    "estimation_is_not_invoice_or_provider_spending_cap": True,
    "requests": [], "api_request_count": 0, "search_actions_completed": 0,
    "tier_adjusted_estimate_usd": 0.0, "standard_price_estimate_usd": 0.0,
    "completed_passes": [], "warnings": [
        "No Terra candidate data is passed into Sol prompts.",
        "Sol starts after Terra; index timing is not identical.",
        "Do not retry: ambiguous transport outcomes might be billed.",
        "Cost is a client-side estimate. The OpenAI invoice is authoritative.",
    ],
}

def save() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = RUN.with_suffix(".tmp")
    tmp.write_text(json.dumps(STATE, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(RUN)

def archive_bytes() -> bytes:
    return subprocess.check_output(
        ["git", "show", FROZEN_CODE + ":automation/archive/index.json"],
        cwd=ROOT,
    )

def prepared_window():
    import primary_recall_search as primary
    from primary_recall_search import build_search_window
    from story_coverage import read_json
    frozen = archive_bytes()
    archive = json.loads(frozen)
    config = read_json(ROOT / "automation/config/site.json")
    window, overlap = build_search_window(
        publication_date=DATE, archive=archive, config=config,
        cutoff_at=datetime.fromisoformat(CUTOFF))
    if (window.get("start_at") != START or window.get("end_at") != CUTOFF
            or window.get("latest_archive_at") != "2026-10-22T04:32:02+03:00"):
        raise RuntimeError("Frozen Terra/Sol window mismatch, API forbidden: " + str(window))
    if len(primary.PRIMARY_DIRECTIONS) != MAX_REQUESTS:
        raise RuntimeError("Primary directions changed")
    return frozen, archive, window, overlap

def cost(resp, searches: int) -> tuple[float, float, str]:
    usage = getattr(resp, "usage", None)
    if usage is None:
        raise RuntimeError("API response without usage; stop")
    inp = getattr(usage, "input_tokens", None)
    out = getattr(usage, "output_tokens", None)
    if not isinstance(inp, int) or not isinstance(out, int):
        raise RuntimeError("Malformed API usage")
    details = getattr(usage, "input_tokens_details", None)
    cached = int(getattr(details, "cached_tokens", 0) or 0)
    written = int(getattr(details, "cache_write_tokens", 0) or 0)
    if min(inp, out, cached, written, searches) < 0 or cached + written > inp:
        raise RuntimeError("Inconsistent token breakdown")
    uncached = inp - cached - written
    standard = (uncached * 2.0 + cached * .1 + written * 2.5 +
                out * 10.0) / 1_000_000 + searches * .01
    tier = str(getattr(resp, "service_tier", None) or "unknown")
    # Observed OpenAI billing Oct 19-22: incentivized-tier text is zero.
    # This is NOT a guaranteed future discount; flag tier uncertainty.
    adjusted = searches * .01 if tier == "incentivized-tier" else standard
    return round(standard, 9), round(adjusted, 9), tier

def offline() -> None:
    frozen, archive, window, overlap = prepared_window()
    STATE.update({"status": "offline_pass",
                  "frozen_archive_sha256": hashlib.sha256(frozen).hexdigest(),
                  "frozen_archive_items": len(archive.get("items", [])),
                  "validated_search_window": window,
                  "continuity_overlap": overlap,
                  "paid_api_requests": 0})
    save()
    print(json.dumps({"status": "offline_pass", "search_window": window,
                      "archive_sha256": STATE["frozen_archive_sha256"],
                      "archive_items": STATE["frozen_archive_items"],
                      "paid_api_requests": 0}, ensure_ascii=False))

def paid() -> None:
    if os.environ.get("SOL_SHADOW_OWNER_APPROVAL_USD") != "1.00":
        raise RuntimeError("No explicit one-time $1 API budget approval")
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise RuntimeError("Re-run forbidden")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY")
    if RUN.is_file():
        old = json.loads(RUN.read_text(encoding="utf-8"))
        if old.get("api_request_count", 0) or old.get("status") not in {"offline_pass"}:
            raise RuntimeError("Existing paid/ambiguous execution, no retry")
    frozen, archive, window, overlap = prepared_window()
    expected_sha = hashlib.sha256(frozen).hexdigest()
    if STATE.get("frozen_archive_sha256") not in {None, expected_sha}:
        raise RuntimeError("Frozen archive changed between offline and paid")
    # Isolate this local GitHub runner checkout; never write back to the repo.
    archive_path = ROOT / "automation/archive/index.json"
    archive_path.write_bytes(frozen)
    STATE.update({"status": "running",
                  "frozen_archive_sha256": expected_sha,
                  "archive_item_count": len(archive.get("items", [])),
                  "validated_search_window": window})
    save()

    from openai import OpenAI
    from openai.resources.responses import Responses
    from ensure_story_coverage_policy import build_audit_api_metadata
    import primary_recall_search as primary
    original_init, original_create = OpenAI.__init__, Responses.create

    def zero_retry(self, *args, **kwargs):
        kwargs["max_retries"] = 0
        return original_init(self, *args, **kwargs)

    active = {"direction": None, "prompt_sha": None}
    def tracked_create(self, *args, **kwargs):
        if (kwargs.get("model") != MODEL
                or (kwargs.get("reasoning") or {}).get("effort") != "medium"
                or kwargs.get("store") is not False
                or kwargs.get("max_tool_calls") != 4
                or kwargs.get("max_output_tokens", 0) > 6000
                or not active["direction"]):
            raise RuntimeError("Unexpected Sol API request configuration")
        if STATE["api_request_count"] >= MAX_REQUESTS:
            raise RuntimeError("More than 12 paid requests forbidden")
        if (STATE["tier_adjusted_estimate_usd"] + NEXT_RESERVE_USD
                > MAX_ESTIMATE_USD):
            raise RuntimeError("Client-side $1 estimate guard: stop before next request")
        attempt = {"direction": active["direction"],
                   "prompt_sha256": active["prompt_sha"],
                   "status": "request_started",
                   "number": STATE["api_request_count"] + 1}
        STATE["api_request_count"] += 1
        STATE["requests"].append(attempt)
        save()
        try:
            response = original_create(self, *args, **kwargs)
        except Exception as exc:
            attempt.update({"status": "transport_or_api_exception",
                            "error": type(exc).__name__ + ": " + str(exc)})
            STATE["status"] = "aborted_ambiguous_spend"
            save()
            raise
        # Persist raw response evidence BEFORE parsing, schema and budget guards.
        metadata = build_audit_api_metadata(response, maximum_web_search_calls=1)
        searches = int(metadata.get("web_search_calls_completed", 0))
        attempt.update({"status": "response_received",
                        "response_id": getattr(response, "id", None),
                        "service_tier": getattr(response, "service_tier", None),
                        "metadata": metadata})
        (OUT / "raw-responses").mkdir(parents=True, exist_ok=True)
        (OUT / "raw-responses" / (active["direction"] + ".json")).write_text(
            json.dumps({"direction": active["direction"],
                        "response_id": getattr(response, "id", None),
                        "raw_output_text": getattr(response, "output_text", None),
                        "api": metadata}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        STATE["search_actions_completed"] += searches
        standard, adjusted, tier = cost(response, searches)
        attempt.update({"standard_estimate_usd": standard,
                        "tier_adjusted_estimate_usd": adjusted,
                        "service_tier": tier, "status": "response_saved"})
        STATE["standard_price_estimate_usd"] = round(
            STATE["standard_price_estimate_usd"] + standard, 9)
        STATE["tier_adjusted_estimate_usd"] = round(
            STATE["tier_adjusted_estimate_usd"] + adjusted, 9)
        save()
        if STATE["tier_adjusted_estimate_usd"] > MAX_ESTIMATE_USD:
            STATE["status"] = "over_client_estimate_after_response"
            save()
            raise RuntimeError("Client estimate $1 exceeded; API response safely saved")
        return response

    OpenAI.__init__, Responses.create = zero_retry, tracked_create
    original_matrix = primary._BASE_RUN_MATRIX
    real_search = primary._base.run_search_request

    def metered_runner(*, direction_id, prompt, **kwargs):
        if any(row["direction"] == direction_id for row in STATE["completed_passes"]):
            raise RuntimeError("Repeated Primary direction forbidden")
        active.update({"direction": direction_id,
                       "prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()})
        try:
            payload, metadata = real_search(direction_id=direction_id, prompt=prompt,
                                            **kwargs)
            STATE["completed_passes"].append({
                "direction": direction_id, "payload": payload, "api": metadata})
            save()
            return payload, metadata
        finally:
            active.update({"direction": None, "prompt_sha": None})

    def meter_matrix(*args, **kwargs):
        kwargs["search_runner"] = metered_runner
        return original_matrix(*args, **kwargs)

    primary._BASE_RUN_MATRIX = meter_matrix
    try:
        path, report = primary.run_primary_recall_search(
            publication_date=DATE, api_key=os.environ["OPENAI_API_KEY"],
            model=MODEL, maximum_candidates=20,
            cutoff_at=datetime.fromisoformat(CUTOFF))
        if (report.get("status") != "complete"
                or len(report.get("directions", [])) != MAX_REQUESTS
                or STATE["api_request_count"] != MAX_REQUESTS
                or report.get("search_budget", {}).get("completed_calls") != MAX_REQUESTS):
            raise RuntimeError("Sol Primary 12/12 not confirmed")
        STATE.update({"status": "complete",
                      "research_runtime_path": str(path),
                      "final_primary_count": report.get("final_candidate_count")})
        save()
        print("SOL 2026-10-23 12/12 COMPLETE. Client estimate USD:",
              STATE["tier_adjusted_estimate_usd"])
    finally:
        OpenAI.__init__, Responses.create = original_init, original_create
        primary._BASE_RUN_MATRIX = original_matrix

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--paid", action="store_true")
    args = parser.parse_args()
    if args.offline == args.paid:
        print("Specify exactly one of --offline or --paid", file=sys.stderr)
        return 2
    try:
        if args.offline:
            offline()
        else:
            paid()
    except Exception as exc:
        if STATE["status"] not in {"aborted_ambiguous_spend",
                                   "over_client_estimate_after_response"}:
            STATE["status"] = "incomplete"
        STATE["error"] = type(exc).__name__ + ": " + str(exc)
        save()
        print("Sol shadow 23 failed:", STATE["error"], file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
