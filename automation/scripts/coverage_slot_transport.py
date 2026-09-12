from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from coverage_slot_guard import CoverageSlotReservation


def _plain_object(value: Any) -> Any:
    if isinstance(value, dict):
        obj = SimpleNamespace()
        for key, item in value.items():
            setattr(obj, str(key), _plain_object(item))
        return obj
    if isinstance(value, list):
        return [_plain_object(item) for item in value]
    return value


def _plain_output_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    direct = value.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    output = value.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "\n".join(part for part in parts if part).strip()


def _parse_response(
    runtime: Any,
    response: Any,
    *,
    maximum_web_search_calls: int,
    raw_response: Any,
) -> tuple[Any, dict[str, Any]]:
    metadata = runtime.build_audit_api_metadata(
        response,
        maximum_web_search_calls=maximum_web_search_calls,
    )
    total_tool_calls = (
        maximum_web_search_calls + runtime.COVERAGE_NAVIGATION_TOOL_ALLOWANCE
        if maximum_web_search_calls == 1
        else maximum_web_search_calls
    )
    metadata["configured_search_operations"] = maximum_web_search_calls
    metadata["configured_total_tool_calls"] = total_tool_calls
    metadata["navigation_tool_allowance"] = (
        runtime.COVERAGE_NAVIGATION_TOOL_ALLOWANCE
        if maximum_web_search_calls == 1
        else 0
    )
    output_text = (getattr(response, "output_text", None) or "").strip()
    payload: Any = None
    validation_error: str | None = None

    if metadata.get("web_search_calls_completed", 0) < 1:
        validation_error = (
            "Coverage audit не завершил ни одной поисковой операции "
            "web_search action.type=search"
        )
    elif getattr(response, "status", None) != "completed":
        validation_error = (
            "Coverage audit не завершён: "
            f"status={getattr(response, 'status', None)!r}"
        )
    elif not output_text:
        validation_error = "Coverage audit вернул пустой output_text"
    else:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            validation_error = f"Coverage audit вернул некорректный JSON: {exc}"
        if validation_error is None and not isinstance(payload, dict):
            validation_error = "Coverage audit должен вернуть JSON-объект"
        if validation_error is None:
            if payload.get("direction_id") not in runtime.AUDIT_DIRECTION_IDS:
                validation_error = "Coverage audit вернул неизвестный direction_id"
            elif payload.get("status") not in {"complete", "complete_with_gaps", "error"}:
                validation_error = "Coverage audit вернул неизвестный status"
            elif not metadata.get("actual_queries"):
                validation_error = "Coverage audit не сохранил фактический поисковый запрос"

    if isinstance(payload, dict):
        if payload.get("status") == "ok":
            payload["status"] = "complete"
        if payload.get("direction_id") not in runtime.AUDIT_DIRECTION_IDS:
            inferred = next(
                (item for item in runtime.AUDIT_DIRECTION_IDS if item in output_text),
                None,
            )
            if inferred:
                payload["direction_id"] = inferred
        payload.setdefault("rejections", [])

    snapshot = {
        "payload": payload if isinstance(payload, dict) else None,
        "metadata": metadata,
        "output_text": output_text,
        "validation_error": validation_error,
    }
    result = runtime.AuditRequestResult(
        payload=payload if isinstance(payload, dict) else None,
        metadata=metadata,
        output_text=output_text,
        raw_response=raw_response,
        validation_error=validation_error,
    )
    runtime._LAST_AUDIT_RESULT = result
    if result not in runtime._LAST_AUDIT_RESULTS:
        runtime._LAST_AUDIT_RESULTS.append(result)
    return result, snapshot


def _raise_if_invalid(runtime: Any, result: Any) -> Any:
    if result.validation_error:
        raise runtime.CoverageAuditResponseError(result.validation_error, result.metadata)
    return result


def protected_policy_audit_request(
    runtime: Any,
    reservation: CoverageSlotReservation,
    *,
    api_key: str,
    model: str,
    prompt: str,
    maximum_web_search_calls: int,
    allowed_domains: list[str] | tuple[str, ...] | None = None,
) -> Any:
    """Execute one protected optional Coverage call with no SDK retry."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=0)
    web_search_tool: dict[str, Any] = {
        "type": "web_search",
        "search_context_size": "medium",
        "return_token_budget": "default",
    }
    if allowed_domains:
        web_search_tool["filters"] = {"allowed_domains": list(allowed_domains)}
    total_tool_calls = (
        maximum_web_search_calls + runtime.COVERAGE_NAVIGATION_TOOL_ALLOWANCE
        if maximum_web_search_calls == 1
        else maximum_web_search_calls
    )

    reservation.mark_request_started()
    response = runtime.call_with_usage(
        "coverage",
        client.responses.create,
        model=model,
        input=prompt,
        tools=[web_search_tool],
        tool_choice="required",
        max_tool_calls=total_tool_calls,
        include=["web_search_call.action.sources"],
        reasoning={"effort": "medium"},
        max_output_tokens=3500,
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_ai_targeted_coverage_audit",
                "strict": True,
                "schema": runtime.AUDIT_SCHEMA,
            }
        },
        store=False,
    )

    raw_response = runtime.response_to_plain(response)
    reservation.save_raw_response(raw_response)
    result, snapshot = _parse_response(
        runtime,
        response,
        maximum_web_search_calls=maximum_web_search_calls,
        raw_response=raw_response,
    )
    reservation.save_result_snapshot(snapshot)
    return _raise_if_invalid(runtime, result)


def replay_raw_response(
    runtime: Any,
    raw_response: Any,
    *,
    maximum_web_search_calls: int = 1,
) -> tuple[Any, dict[str, Any]]:
    """Reparse the durably saved provider response without another wire call."""
    if not isinstance(raw_response, dict):
        raise RuntimeError("saved Coverage optional-slot raw response must be an object")
    response = _plain_object(raw_response)
    setattr(response, "output_text", _plain_output_text(raw_response))
    result, snapshot = _parse_response(
        runtime,
        response,
        maximum_web_search_calls=maximum_web_search_calls,
        raw_response=raw_response,
    )
    return _raise_if_invalid(runtime, result), snapshot


def replay_result_snapshot(runtime: Any, snapshot: dict[str, Any]) -> Any:
    """Reconstruct the established audit result without another wire call."""
    payload = snapshot.get("payload")
    metadata = snapshot.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError("saved Coverage optional-slot metadata is missing")
    validation_error = snapshot.get("validation_error")
    result = runtime.AuditRequestResult(
        payload=payload if isinstance(payload, dict) else None,
        metadata=metadata,
        output_text=str(snapshot.get("output_text") or ""),
        raw_response=None,
        validation_error=(str(validation_error) if validation_error else None),
    )
    runtime._LAST_AUDIT_RESULT = result
    if result not in runtime._LAST_AUDIT_RESULTS:
        runtime._LAST_AUDIT_RESULTS.append(result)
    return _raise_if_invalid(runtime, result)
