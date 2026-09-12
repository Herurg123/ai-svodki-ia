#!/usr/bin/env python3
"""Agency discovery rescue v6: additive observability over preserved v5.

P2 intentionally does not change the Reuters-only query, provider routing, tool
configuration, search budget, ranking, freshness, merge policy, or retry rules.
It adds a bounded redacted request/response capture around the already-existing
single search and derives orthogonal diagnostics for transport, response parsing,
provider source metadata, model output, route/validation rejection, dedupe/cap,
and actual additions.

The v3/v4/v5 implementations remain preserved compatibility/recovery assets.
Recovery reuses their persisted state; v6 never authorizes a second search from
missing diagnostics.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import agency_discovery_rescue_v5 as v5
from ensure_story_coverage_policy import build_audit_api_metadata, response_to_plain
from story_coverage import write_json
from usage_observer import call_with_usage

v4 = v5.v4
v3 = v4.v3

AGENCY_DISCOVERY_RESCUE_VERSION = 6
AGENCY_DISCOVERY_RESCUE_STRATEGY = v5.AGENCY_DISCOVERY_RESCUE_STRATEGY
AGENCY_DISCOVERY_RESCUE_DIRECTION = v5.AGENCY_DISCOVERY_RESCUE_DIRECTION
AGENCY_DISCOVERY_RESCUE_QUERY = v5.AGENCY_DISCOVERY_RESCUE_QUERY
AGENCY_DISCOVERY_ALLOWED_DOMAINS = v5.AGENCY_DISCOVERY_ALLOWED_DOMAINS
AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE = v5.AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE
AUDIT_CANDIDATE_SCHEMA = v5.AUDIT_CANDIDATE_SCHEMA
MAXIMUM_SEARCH_OPERATIONS = v5.MAXIMUM_SEARCH_OPERATIONS
PIPELINE_MAXIMUM_SEARCH_OPERATIONS = v5.PIPELINE_MAXIMUM_SEARCH_OPERATIONS
PRODUCTION_PREVIEW_ROOT = v5.PRODUCTION_PREVIEW_ROOT

TRANSPORT_CAPTURE_VERSION = 1
MAXIMUM_CAPTURE_BYTES = 262_144
MAXIMUM_CAPTURE_TEXT_CHARS = 32_768

SearchRunner = Callable[..., tuple[dict[str, Any], dict[str, Any]]]


def _capture_paths(
    artifact_dir: Path, output_root: Path, publication_date: str
) -> tuple[Path, Path]:
    return (
        artifact_dir / "agency-discovery-rescue-transport.json",
        output_root / f"agency-discovery-rescue-transport-{publication_date}.json",
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request_contract(*, model: str, prompt: str) -> dict[str, Any]:
    schema_text = json.dumps(v3.RESCUE_SCHEMA, ensure_ascii=False, sort_keys=True)
    return {
        "model": model,
        "query": AGENCY_DISCOVERY_RESCUE_QUERY,
        "prompt_sha256": _sha256_text(prompt),
        "prompt_chars": len(prompt),
        "tools": [v3._web_search_tool()],
        "tool_choice": "required",
        "max_tool_calls": v3.MAXIMUM_TOOL_CALLS,
        "include": ["web_search_call.action.sources"],
        "reasoning": {"effort": "medium"},
        "max_output_tokens": 5000,
        "response_schema_name": "daily_ai_agency_discovery_rescue",
        "response_schema_sha256": _sha256_text(schema_text),
        "store": False,
        "sdk_max_retries": 2,
    }


def _response_capture(response: Any) -> dict[str, Any]:
    plain = response_to_plain(response)
    encoded = json.dumps(
        plain,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload: dict[str, Any] = {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
        "truncated": len(encoded) > MAXIMUM_CAPTURE_BYTES,
    }
    if len(encoded) <= MAXIMUM_CAPTURE_BYTES:
        payload["raw"] = plain
        return payload

    output_text = str(getattr(response, "output_text", None) or "")
    payload["raw"] = {
        "id": getattr(response, "id", None),
        "status": getattr(response, "status", None),
        "model": getattr(response, "model", None),
        "output_text": output_text[:MAXIMUM_CAPTURE_TEXT_CHARS],
        "output_text_truncated": len(output_text) > MAXIMUM_CAPTURE_TEXT_CHARS,
        "output": response_to_plain((getattr(response, "output", None) or [])[:32]),
        "usage": response_to_plain(getattr(response, "usage", None)),
        "error": response_to_plain(getattr(response, "error", None)),
        "incomplete_details": response_to_plain(
            getattr(response, "incomplete_details", None)
        ),
    }
    return payload


def _persist_capture(
    capture: dict[str, Any],
    *,
    artifact_dir: Path,
    output_root: Path,
    publication_date: str,
) -> None:
    for path in _capture_paths(artifact_dir, output_root, publication_date):
        write_json(path, capture)


def _load_capture(
    artifact_dir: Path, output_root: Path, publication_date: str
) -> dict[str, Any] | None:
    for path in _capture_paths(artifact_dir, output_root, publication_date):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("publication_date") == publication_date:
            return value
    return None


def classify_source_metadata(api: Any) -> dict[str, Any]:
    """Classify provider source metadata without collapsing unknown into empty."""
    counts = {key: 0 for key in ("missing", "null", "empty", "nonempty", "malformed")}
    search_actions = 0
    if isinstance(api, dict):
        rows = api.get("web_search_call_items")
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict) or row.get("action_type") != "search":
                    continue
                search_actions += 1
                action = row.get("action")
                if not isinstance(action, dict):
                    counts["malformed"] += 1
                    continue
                if "sources" not in action:
                    counts["missing"] += 1
                    continue
                sources = action.get("sources")
                if sources is None:
                    counts["null"] += 1
                elif isinstance(sources, list):
                    counts["nonempty" if sources else "empty"] += 1
                else:
                    counts["malformed"] += 1
    active = [key for key, count in counts.items() if count]
    if search_actions == 0:
        state = "unknown"
    elif len(active) == 1:
        state = active[0]
    else:
        state = "mixed"
    return {
        "state": state,
        "search_actions": search_actions,
        "counts": counts,
        "available": state in {"empty", "nonempty"},
    }


def _rejection_axes(report: dict[str, Any]) -> dict[str, int]:
    axes = {
        "host": 0,
        "window": 0,
        "schema": 0,
        "duplicate": 0,
        "archive_duplicate": 0,
        "cap": 0,
        "other": 0,
    }
    for raw in report.get("rejections") or []:
        if not isinstance(raw, dict):
            continue
        reason = str(raw.get("reason_code") or "")
        errors = [str(item) for item in (raw.get("errors") or [])]
        joined = " ".join(errors)
        if reason == "non_direct_reuters_ap_source":
            axes["host"] += 1
        elif reason == "duplicate_existing_event" or "дубликат существующего кандидата" in joined:
            axes["duplicate"] += 1
        elif reason == "archive_exact_url_duplicate":
            axes["archive_duplicate"] += 1
        elif "вне редакционного окна" in joined:
            axes["window"] += 1
        elif "достигнут maximum_candidates" in joined:
            axes["cap"] += 1
        elif errors:
            axes["schema"] += 1
        elif reason in {
            "search_response_error",
            "search_transport_error",
            "search_outcome_indeterminate",
            "search_window_missing",
            "merge_input_invalid",
            "merge_exception",
            "primary_diagnostics_missing",
        }:
            axes["other"] += 1
        else:
            axes["other"] += 1
    return axes


def build_observability(
    report: dict[str, Any], capture: dict[str, Any] | None
) -> dict[str, Any]:
    rejection_axes = _rejection_axes(report)
    pre_merge_eligible = int(report.get("validated_count", 0) or 0)
    post_validation = max(
        0,
        pre_merge_eligible - rejection_axes["window"] - rejection_axes["schema"],
    )
    model_rejections = report.get("model_rejections")
    if not isinstance(model_rejections, list):
        model_rejections = []

    transport_state = "not_attempted"
    parse_state = "not_attempted"
    if isinstance(capture, dict):
        transport_state = str(capture.get("transport_state") or "unknown")
        parse_state = str(capture.get("response_parse_status") or "unknown")
    elif report.get("executed"):
        transport_state = "legacy_or_injected_unobserved"
        parse_state = "legacy_or_injected_unobserved"

    return {
        "version": 1,
        "request_contract": (
            copy.deepcopy(capture.get("request_contract"))
            if isinstance(capture, dict)
            else None
        ),
        "transport": {
            "state": transport_state,
            "capture_available": isinstance(capture, dict),
            "raw_response_saved_before_parse": bool(
                isinstance(capture, dict) and capture.get("raw_response_saved_before_parse") is True
            ),
            "response_capture_truncated": (
                bool((capture.get("response") or {}).get("truncated"))
                if isinstance(capture, dict) and isinstance(capture.get("response"), dict)
                else None
            ),
        },
        "response_parse": {"state": parse_state},
        "source_metadata": classify_source_metadata(report.get("api")),
        "model": {
            "candidate_count": int(report.get("raw_count", 0) or 0),
            "rejection_count": len(model_rejections),
        },
        "post_model_route": {
            "pre_merge_eligible_count": pre_merge_eligible,
            "host_rejection_count": rejection_axes["host"],
            "archive_duplicate_count": rejection_axes["archive_duplicate"],
            "existing_event_duplicate_count": rejection_axes["duplicate"],
        },
        "merge_validation": {
            "post_validation_count": post_validation,
            "window_rejection_count": rejection_axes["window"],
            "schema_rejection_count": rejection_axes["schema"],
            "cap_rejection_count": rejection_axes["cap"],
            "other_rejection_count": rejection_axes["other"],
        },
        "result": {
            "accepted_count": int(report.get("accepted_count", 0) or 0),
            "added_count": int(report.get("added_count", 0) or 0),
            "state": report.get("state"),
        },
        "zero_search_budget_change": True,
    }


def _instrumented_search_runner(
    *, artifact_dir: Path, output_root: Path, publication_date: str
) -> SearchRunner:
    def run(*, api_key: str, model: str, prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        from openai import OpenAI

        capture: dict[str, Any] = {
            "version": TRANSPORT_CAPTURE_VERSION,
            "publication_date": publication_date,
            "search_strategy": AGENCY_DISCOVERY_RESCUE_STRATEGY,
            "request_contract": _request_contract(model=model, prompt=prompt),
            "transport_state": "request_prepared",
            "response_parse_status": "not_started",
            "raw_response_saved_before_parse": False,
        }
        _persist_capture(
            capture,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )

        client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
        capture["transport_state"] = "request_started"
        _persist_capture(
            capture,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )
        try:
            response = call_with_usage(
                "agency",
                client.responses.create,
                model=model,
                input=prompt,
                tools=[v3._web_search_tool()],
                tool_choice="required",
                max_tool_calls=v3.MAXIMUM_TOOL_CALLS,
                include=["web_search_call.action.sources"],
                reasoning={"effort": "medium"},
                max_output_tokens=5000,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "daily_ai_agency_discovery_rescue",
                        "strict": True,
                        "schema": v3.RESCUE_SCHEMA,
                    }
                },
                store=False,
            )
        except Exception as exc:
            capture["transport_state"] = "transport_error"
            capture["transport_error"] = f"{type(exc).__name__}: {exc}"[:2048]
            _persist_capture(
                capture,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            raise

        capture["transport_state"] = "response_saved"
        capture["response"] = _response_capture(response)
        capture["raw_response_saved_before_parse"] = True
        _persist_capture(
            capture,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )

        metadata = build_audit_api_metadata(
            response, maximum_web_search_calls=MAXIMUM_SEARCH_OPERATIONS
        )
        metadata["configured_search_operations"] = MAXIMUM_SEARCH_OPERATIONS
        metadata["configured_total_tool_calls"] = v3.MAXIMUM_TOOL_CALLS
        metadata["navigation_tool_allowance"] = v3.NAVIGATION_TOOL_ALLOWANCE
        metadata["allowed_domains"] = list(AGENCY_DISCOVERY_ALLOWED_DOMAINS)
        metadata["search_context_size"] = AGENCY_DISCOVERY_SEARCH_CONTEXT_SIZE

        def response_error(message: str) -> None:
            capture["response_parse_status"] = "response_error"
            capture["response_parse_error"] = message[:2048]
            _persist_capture(
                capture,
                artifact_dir=artifact_dir,
                output_root=output_root,
                publication_date=publication_date,
            )
            raise v3.AgencyDiscoveryResponseError(message, metadata)

        completed = int(metadata.get("web_search_calls_completed", 0) or 0)
        if completed != MAXIMUM_SEARCH_OPERATIONS:
            response_error(
                "Agency discovery rescue должен завершить ровно один Web Search, "
                f"получено {completed}"
            )
        actual_queries = list(metadata.get("actual_queries") or [])
        if len(actual_queries) != 1:
            response_error(
                "Agency discovery rescue должен выполнить один logical query, "
                f"получено {len(actual_queries)}"
            )
        if v3._clean(actual_queries[0]) != AGENCY_DISCOVERY_RESCUE_QUERY:
            response_error(
                "Agency discovery rescue выполнил неожиданный query: "
                f"{actual_queries[0]!r}"
            )
        if getattr(response, "status", None) != "completed":
            response_error(
                "Agency discovery rescue не завершён: "
                f"status={getattr(response, 'status', None)!r}"
            )
        output_text = (getattr(response, "output_text", None) or "").strip()
        if not output_text:
            response_error("Agency discovery rescue вернул пустой output_text")
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            response_error(f"Agency discovery rescue вернул некорректный JSON: {exc}")
        if not isinstance(payload, dict):
            response_error("Agency discovery rescue должен вернуть JSON-объект")
        if payload.get("direction_id") != AGENCY_DISCOVERY_RESCUE_DIRECTION:
            response_error("Agency discovery rescue вернул чужой direction_id")
        if payload.get("status") not in {"complete", "complete_with_gaps"}:
            response_error(
                "Agency discovery rescue вернул непригодный status="
                f"{payload.get('status')!r}"
            )

        capture["response_parse_status"] = "parsed_valid"
        capture["parsed_candidate_count"] = len(payload.get("candidates") or [])
        capture["parsed_model_rejection_count"] = len(payload.get("rejections") or [])
        _persist_capture(
            capture,
            artifact_dir=artifact_dir,
            output_root=output_root,
            publication_date=publication_date,
        )
        return payload, metadata

    return run


def _persist_report(
    report: dict[str, Any], *, artifact_dir: Path, output_root: Path,
    publication_date: str
) -> None:
    """Compatibility surface used by same-day recovery."""
    v5._persist_report(
        report,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )


def run_agency_discovery_rescue(
    *,
    artifact_dir: Path,
    archive_path: Path,
    publication_date: str,
    api_key: str,
    model: str,
    maximum_candidates: int = 20,
    search_runner: SearchRunner | None = None,
    output_root: Path = PRODUCTION_PREVIEW_ROOT,
) -> dict[str, Any]:
    runner = search_runner or _instrumented_search_runner(
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )
    report = v5.run_agency_discovery_rescue(
        artifact_dir=artifact_dir,
        archive_path=archive_path,
        publication_date=publication_date,
        api_key=api_key,
        model=model,
        maximum_candidates=maximum_candidates,
        search_runner=runner,
        output_root=output_root,
    )
    result = copy.deepcopy(report)
    result["version"] = AGENCY_DISCOVERY_RESCUE_VERSION
    capture = _load_capture(artifact_dir, output_root, publication_date)
    result["pre_merge_eligible_count"] = int(result.get("validated_count", 0) or 0)
    result["observability"] = build_observability(result, capture)
    result["post_validation_count"] = result["observability"]["merge_validation"][
        "post_validation_count"
    ]
    result["source_metadata_state"] = result["observability"]["source_metadata"]["state"]
    result["transport_capture_available"] = isinstance(capture, dict)
    if isinstance(capture, dict):
        artifact_capture, diagnostic_capture = _capture_paths(
            artifact_dir, output_root, publication_date
        )
        result["transport_capture_paths"] = {
            "artifact": str(artifact_capture),
            "diagnostic": str(diagnostic_capture),
        }
    _persist_report(
        result,
        artifact_dir=artifact_dir,
        output_root=output_root,
        publication_date=publication_date,
    )
    return result
