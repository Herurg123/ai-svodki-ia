#!/usr/bin/env python3
"""Independent offline acceptance controls for step 4; no transport is invoked."""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

import ensure_story_coverage as coverage
import source_freshness as freshness
from source_resolution_evidence import collect_source_failure_signals

WINDOW = {"start_at": "2026-09-05T00:00:00+03:00", "end_at": "2026-09-05T12:00:00+03:00"}
URL = "https://example.test/openai/science-model"
ALTERNATIVE_URL = "https://authority.test/openai/coding-model"


def schema_errors(schema, value, path="$"):
    """Validate the JSON-Schema features used by the local strict candidate schema."""
    errors = []
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected]
    valid_type = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if expected and not any(valid_type[name](value) for name in types):
        return [f"{path}: expected {types}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value outside enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0): errors.append(f"{path}: shorter than minLength")
        if schema.get("pattern") and not re.search(schema["pattern"], value): errors.append(f"{path}: pattern mismatch")
    if isinstance(value, int) and not isinstance(value, bool):
        if value < schema.get("minimum", value): errors.append(f"{path}: below minimum")
        if value > schema.get("maximum", value): errors.append(f"{path}: above maximum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0): errors.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]: errors.append(f"{path}: more than maxItems")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value): errors.extend(schema_errors(schema["items"], item, f"{path}[{index}]"))
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value: errors.append(f"{path}: missing required {key}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props: errors.append(f"{path}: unexpected property {key}")
        for key, item in value.items():
            if key in props: errors.extend(schema_errors(props[key], item, f"{path}.{key}"))
    return errors


def source_failure_lead() -> dict:
    original = {
        "id": "reused-id-is-not-identity", "title": "OpenAI launches new model for science",
        "organization": "OpenAI", "event_type": "product_release",
        "event_summary": "A model for scientific research.", "event_date": "2026-09-05",
        "event_at": "2026-09-05T07:00:00+03:00", "event_time_precision": "datetime",
        "event_origin_url": URL, "event_evidence_kind": "official_release",
        "event_date_evidence": "Official release timestamp: 2026-09-05T07:00:00+03:00",
        "verification_status": "verified",
        "freshness_status": "new_event", "recommendation": "include", "significance_score": 4,
        "primary_source": {"title": "Science-model release", "publisher": "Example", "url": URL}, "supporting_sources": [],
    }
    primary = {"accepted_events": [original], "final_candidates": [
        {"title": original["title"], "primary_url": URL}
    ]}
    failed_candidate = json.loads(json.dumps(original))
    def blocked(_url):
        raise freshness.SourceFreshnessError("HTTP 403")
    record = freshness.verify_candidate(
        failed_candidate,
        start_at=__import__("datetime").datetime.fromisoformat(WINDOW["start_at"]),
        end_at=__import__("datetime").datetime.fromisoformat(WINDOW["end_at"]),
        fetcher=blocked,
    )
    assert record["status"] == "excluded_unverified_freshness"
    assert record["event_freshness_status"] == "fresh"
    source = {"runs": [{"search_window": WINDOW, "candidates": [record]}]}
    leads = collect_source_failure_signals(source, primary, search_window=WINDOW)
    assert len(leads) == 1
    return leads[0], record


def main() -> int:
    lead, original_source_record = source_failure_lead()
    distinct_event = {
        "title": "OpenAI launches new model for coding",
        "organization": "OpenAI", "event_type": "product_release",
        "event_summary": "OpenAI released a coding model for software-development workflows on 5 September.",
        "event_date": "2026-09-05", "event_at": "2026-09-05T08:00:00+03:00",
        "event_time_precision": "datetime", "event_origin_url": ALTERNATIVE_URL,
        "event_evidence_kind": "official_release",
        "event_date_evidence": "Official release timestamp: 2026-09-05T08:00:00+03:00",
        "published_date": "2026-09-05", "published_at": "2026-09-05T08:05:00+03:00",
        "time_precision": "datetime", "topic": "AI coding products",
        "keywords": ["OpenAI", "coding", "model"], "geography": "world",
        "category": "coding", "source_type": "official",
        "verification_status": "verified", "freshness_status": "new_event",
        "recommendation": "include", "significance_score": 4,
        "primary_source": {"title": "Coding-model release", "publisher": "Different authoritative publisher", "url": ALTERNATIVE_URL},
        "supporting_sources": [],
        "verified_facts": ["OpenAI announced a coding model.", "The release is dated 5 September."],
        "significance": "The release affects AI coding workflows.", "limitations": "Synthetic control.",
        "archive_status": "none", "archive_reason": "Different coding release.",
        "verification_notes": "Verified in synthetic authoritative-source control.",
        "freshness_reason": "New release in window.", "legal_scale": "not_applicable",
        "legal_scale_reason": "", "curiosity_eligible": False, "curiosity_verification": "",
    }
    candidate_schema_errors = schema_errors(coverage.AUDIT_CANDIDATE_SCHEMA, distinct_event)
    # This fake public page is only a deterministic admissibility control. It
    # proves the normal event/source gates do not bind the new candidate to the
    # old 403 event; it is not an observed provider result.
    checked_alternative = json.loads(json.dumps(distinct_event))
    source_record = freshness.verify_candidate(
        checked_alternative,
        start_at=__import__("datetime").datetime.fromisoformat(WINDOW["start_at"]),
        end_at=__import__("datetime").datetime.fromisoformat(WINDOW["end_at"]),
        fetcher=lambda url: (
            '<meta property="article:published_time" content="2026-09-05T08:05:00+03:00">', url, 200,
        ),
    )
    matched = coverage._candidate_matches_cluster(distinct_event, [lead])
    related = coverage._signals_related(
        lead,
        {"title": distinct_event["title"], "entities": ["OpenAI"], "evidence_reason": distinct_event["event_summary"]},
    )
    mandatory = [
        {"direction_id": direction, "attempt": 1, "status": "checked",
         "api": {"status": "completed", "web_search_calls_completed": 1,
                 "web_search_call_items_total": 1}}
        for direction in coverage.AUDIT_DIRECTION_IDS
    ]
    plan = {
        "publication_date": "2026-09-05", "audit_status": "complete_with_gaps",
        "checked_directions": list(coverage.AUDIT_DIRECTION_IDS), "attempts": mandatory,
        "search_budget": {"maximum_calls": 7, "completed_calls": 6, "remaining_calls": 1},
    }
    resolution_query = coverage.build_resolution_query([lead])
    metadata = {"status": "completed", "web_search_calls_completed": 1,
                "web_search_call_items_total": 1, "actual_queries": [resolution_query],
                "consulted_sources": [ALTERNATIVE_URL]}
    with tempfile.TemporaryDirectory() as raw:
        checkpoint = Path(raw) / "coverage-audit.json"
        response = SimpleNamespace(
            # API payload remains the strict-schema raw candidate. Source
            # Freshness diagnostics are applied only after resolution below.
            payload={"status": "complete", "candidates": [distinct_event], "rejections": [], "notes": "synthetic"},
            metadata=metadata,
        )
        with patch.object(coverage._runtime, "_report_path", return_value=checkpoint), \
             patch.object(coverage._runtime, "_policy_audit_request", return_value=response):
            resolved = coverage._run_resolution(
                plan=plan, signals=[lead], api_key="unused", model="unused",
                search_window=WINDOW, archive={}, maximum_web_search_calls=7,
            )
    resolution = resolved["attempts"][-1]
    post_resolution_candidate = json.loads(json.dumps(resolved["candidates"][0]))
    post_resolution_source_record = freshness.verify_candidate(
        post_resolution_candidate,
        start_at=__import__("datetime").datetime.fromisoformat(WINDOW["start_at"]),
        end_at=__import__("datetime").datetime.fromisoformat(WINDOW["end_at"]),
        fetcher=lambda url: (
            '<meta property="article:published_time" content="2026-09-05T08:05:00+03:00">', url, 200,
        ),
    )
    baseline_bridge_exists = (Path("/workspace/scratch/b0ff9bbd56a1/ai-svodki-base") /
                              "automation/scripts/source_resolution_evidence.py").is_file()
    result = {
        "status": "FAIL" if matched else "PASS",
        "case": "source-freshness event identity must not accept a same-company different event",
        "saved_source_failure_title": lead["title"],
        "event_identity_tokens": lead["event_identity_tokens"],
        "alternative_title": distinct_event["title"],
        "candidate_matches_cluster": matched,
        "signals_related": related,
        "expected_candidate_matches_cluster": False,
        "invariant": "Alternative source must corroborate the original event, not merely another news item about the same organization.",
        "synthetic_admissible_control": {
            "observed_production": False,
            "source_failure_event": {key: lead["rejection_evidence"]["candidate"][key] for key in (
                "title", "event_summary", "event_date", "event_at", "primary_source")},
            "source_failure_gate_record": {
                "status": original_source_record["status"],
                "event_freshness_status": original_source_record["event_freshness_status"],
                "source_url": original_source_record["sources"][0]["url"],
                "source_error": original_source_record["sources"][0]["error"],
            },
            "alternative_event": {key: checked_alternative[key] for key in (
                "title", "event_summary", "event_date", "event_at", "published_date", "published_at", "primary_source", "recommendation",
                "verification_status", "freshness_status")},
            "coverage_candidate_schema_errors": candidate_schema_errors,
            "raw_api_response_is_distinct_event": response.payload["candidates"] == [distinct_event],
            "actual_query_equals_build_resolution_query": resolution["actual_queries"] == [resolution_query],
            "event_and_source_gate_record": source_record,
            "post_resolution_source_gate_record": post_resolution_source_record,
            "quality_after_source_gate": resolved["retrieval_quality"],
            "resolution_candidate_count": resolution["candidate_count"],
            "resolution_outcome": resolution["outcome"],
            "resolution_disposition": resolution["resolution_disposition"],
            "quality": resolved["retrieval_quality"],
            "budget": resolved["search_budget"],
        },
        "baseline_comparison": {
            "baseline_commit": "b474b06bc00f365b9737ece4dd0912c1892489e7",
            "baseline_source_failure_bridge_exists": baseline_bridge_exists,
            "same_source_failure_lead_reachable_in_baseline": False,
            "reason": "The baseline has no source_resolution_evidence module, so a Source Freshness 403 cannot enter the Coverage resolution cluster through this new route.",
        },
        "network_calls": 0,
        "paid_api_calls": 0,
    }
    out = ROOT / "automation/audits/experiments/2026-09-07-terra-independent-review.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if matched else 0


if __name__ == "__main__":
    raise SystemExit(main())
