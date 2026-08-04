from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_POLICY_PATH = Path(__file__).with_name("ensure_story_coverage_policy.py")
_POLICY_SPEC = importlib.util.spec_from_file_location(
    "ensure_story_coverage_policy",
    _POLICY_PATH,
)
assert _POLICY_SPEC and _POLICY_SPEC.loader
_policy = importlib.util.module_from_spec(_POLICY_SPEC)
sys.modules[_POLICY_SPEC.name] = _policy
_POLICY_SPEC.loader.exec_module(_policy)

# Re-export the policy surface so existing tests and callers keep importing the
# historical entry point. Transport diagnostics are overridden below.
for _name in dir(_policy):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_policy, _name)


@dataclass
class AuditRequestResult:
    payload: dict[str, Any] | None
    metadata: dict[str, Any]
    output_text: str
    raw_response: Any
    validation_error: str | None

    def __iter__(self):
        yield self.payload
        yield self.metadata


_LAST_AUDIT_RESULT: AuditRequestResult | None = None
_LAST_AUDIT_RESULTS: list[AuditRequestResult] = []


def build_audit_api_metadata(
    response: Any,
    *,
    maximum_web_search_calls: int,
) -> dict[str, Any]:
    metadata = _policy.build_audit_api_metadata(
        response,
        maximum_web_search_calls=maximum_web_search_calls,
    )
    statuses = metadata.get("web_search_call_statuses") or {}
    # Older SDK objects and test doubles may omit per-call status. Such items
    # were historically counted as performed, so retain that compatibility.
    metadata["web_search_calls"] = int(statuses.get("completed", 0)) + int(
        statuses.get("unknown", 0)
    )
    return metadata


def run_audit_request(
    *,
    api_key: str,
    model: str,
    prompt: str,
    maximum_web_search_calls: int,
) -> AuditRequestResult:
    global _LAST_AUDIT_RESULT

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=1200.0, max_retries=2)
    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[
            {
                "type": "web_search",
                "search_context_size": "medium",
                "return_token_budget": "default",
            }
        ],
        tool_choice="required",
        max_tool_calls=maximum_web_search_calls,
        include=["web_search_call.action.sources"],
        reasoning={"effort": "medium"},
        max_output_tokens=3500,
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_ai_targeted_coverage_audit",
                "strict": True,
                "schema": AUDIT_SCHEMA,
            }
        },
        store=False,
    )
    metadata = build_audit_api_metadata(
        response,
        maximum_web_search_calls=maximum_web_search_calls,
    )
    output_text = (getattr(response, "output_text", None) or "").strip()
    payload: Any = None
    validation_error: str | None = None

    if metadata.get("web_search_call_items_total", 0) < 1:
        validation_error = "Coverage audit не вернул ни одного web_search_call"
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
            if payload.get("direction_id") not in AUDIT_DIRECTION_IDS:
                validation_error = "Coverage audit вернул неизвестный direction_id"
            elif payload.get("status") not in {
                "complete",
                "complete_with_gaps",
                "error",
            }:
                validation_error = "Coverage audit вернул неизвестный status"
            elif not metadata.get("actual_queries"):
                validation_error = (
                    "Coverage audit не сохранил фактический поисковый запрос"
                )

    result = AuditRequestResult(
        payload=payload if isinstance(payload, dict) else None,
        metadata=metadata,
        output_text=output_text,
        raw_response=response_to_plain(response),
        validation_error=validation_error,
    )
    _LAST_AUDIT_RESULT = result
    _LAST_AUDIT_RESULTS.append(result)
    if validation_error is None and metadata.get("budget_overrun"):
        print(
            "::warning title=Coverage audit web-search budget::"
            "Responses API вернул больше web_search_call, чем настроено: "
            f"{metadata.get('observed_web_search_calls')}>"
            f"{maximum_web_search_calls}. Ответ завершён и пригоден, "
            "поэтому короткий выпуск не блокируется.",
            file=sys.stderr,
        )
    return result


def coerce_audit_result(value: Any) -> AuditRequestResult:
    if isinstance(value, AuditRequestResult):
        value.metadata.setdefault(
            "web_search_calls_completed",
            int(value.metadata.get("web_search_calls", 0) or 0),
        )
        value.metadata.setdefault(
            "web_search_call_items_total",
            int(
                value.metadata.get(
                    "observed_web_search_calls",
                    value.metadata.get("web_search_calls", 0),
                )
                or 0
            ),
        )
        return value
    if isinstance(value, tuple) and len(value) == 2:
        payload, metadata = value
        if isinstance(payload, dict) and isinstance(metadata, dict):
            legacy_queries = payload.get("queries_used")
            if not metadata.get("actual_queries") and isinstance(
                legacy_queries, list
            ):
                metadata["actual_queries"] = [
                    str(item.get("query", "")).strip()
                    for item in legacy_queries
                    if isinstance(item, dict) and str(item.get("query", "")).strip()
                ]
            metadata.setdefault(
                "web_search_calls_completed",
                int(metadata.get("web_search_calls", 0) or 0),
            )
            metadata.setdefault(
                "web_search_call_items_total",
                int(metadata.get("web_search_calls", 0) or 0),
            )
            return AuditRequestResult(
                payload=payload,
                metadata=metadata,
                output_text=json.dumps(payload, ensure_ascii=False),
                raw_response=None,
                validation_error=None,
            )
    raise RuntimeError("Coverage audit вернул результат неожиданного типа")


def persist_audit_diagnostics(
    result: AuditRequestResult,
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "coverage-audit-output.txt"
    response_path = output_dir / "coverage-audit-response.json"
    output_path.write_text(
        result.output_text + ("\n" if result.output_text else ""),
        encoding="utf-8",
    )
    response_path.write_text(
        json.dumps(
            result.raw_response,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "api_output_path": str(output_path),
        "api_response_path": str(response_path),
    }


def completed_prior_audit(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return False
    audit_state = payload.get("audit_state")
    if audit_state is not None and audit_state != "completed_usable":
        return False
    api = payload.get("api") or {}
    return (
        payload.get("web_search_performed") is True
        and isinstance(api, dict)
        and api.get("status") in {"completed", "partial"}
    )


def _policy_audit_request(**kwargs: Any) -> AuditRequestResult:
    global _LAST_AUDIT_RESULT

    result = coerce_audit_result(globals()["run_audit_request"](**kwargs))
    _LAST_AUDIT_RESULT = result
    if result not in _LAST_AUDIT_RESULTS:
        _LAST_AUDIT_RESULTS.append(result)
    if isinstance(result.payload, dict):
        # Compatibility for pre-plan unit doubles. Real API responses are
        # constrained by the strict per-direction schema above.
        if result.payload.get("status") == "ok":
            result.payload["status"] = "complete"
        if result.payload.get("direction_id") not in AUDIT_DIRECTION_IDS:
            prompt = str(kwargs.get("prompt") or "")
            inferred = next(
                (item for item in AUDIT_DIRECTION_IDS if item in prompt),
                None,
            )
            if inferred:
                result.payload["direction_id"] = inferred
        result.payload.setdefault("rejections", [])
    if result.validation_error:
        raise CoverageAuditResponseError(result.validation_error, result.metadata)
    return result


def _report_path() -> Path | None:
    try:
        index = sys.argv.index("--report")
        return Path(sys.argv[index + 1])
    except (ValueError, IndexError):
        return None


def _read_prior_report(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _sync_policy_overrides() -> None:
    for name in (
        "RUNTIME_RESEARCH_ROOT",
        "PERSISTED_RESEARCH_ROOT",
        "PROMPT_PATH",
        "GENERATOR_PATH",
        "rerun_editorial",
    ):
        setattr(_policy, name, globals()[name])
    _policy.run_audit_request = _policy_audit_request


def _finalize_report(
    report_path: Path | None,
    prior_report: dict[str, Any] | None,
) -> None:
    if report_path is None or not report_path.is_file():
        return
    report = read_json(report_path)
    if not isinstance(report, dict):
        return

    report.setdefault("audit_state", "not_started")
    report.setdefault("validation_error", None)
    report.setdefault("error_stage", None)
    report.setdefault("api_output_path", None)
    report.setdefault("api_response_path", None)

    if _LAST_AUDIT_RESULTS:
        results = list(_LAST_AUDIT_RESULTS)
        report["api_attempts"] = [item.metadata for item in results]
        observed = sum(
            int(
                item.metadata.get(
                    "web_search_call_items_total",
                    item.metadata.get("observed_web_search_calls", 0),
                )
                or 0
            )
            for item in results
        )
        report["web_search_performed"] = observed > 0
        diagnostic_paths: list[dict[str, str]] = []
        for index, item in enumerate(results, start=1):
            direction = (
                str(item.payload.get("direction_id"))
                if isinstance(item.payload, dict)
                else "unknown"
            )
            pass_dir = report_path.parent / "coverage-audit-passes"
            pass_dir.mkdir(parents=True, exist_ok=True)
            output_path = pass_dir / f"{index:02d}-{direction}-output.txt"
            response_path = pass_dir / f"{index:02d}-{direction}-response.json"
            output_path.write_text(
                item.output_text + ("\n" if item.output_text else ""),
                encoding="utf-8",
            )
            response_path.write_text(
                json.dumps(
                    item.raw_response,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
                + "\n",
                encoding="utf-8",
            )
            diagnostic_paths.append(
                {
                    "direction_id": direction,
                    "api_output_path": str(output_path),
                    "api_response_path": str(response_path),
                }
            )
        report["api_diagnostic_paths"] = diagnostic_paths

        # Preserve canonical single-response paths for recovery artifacts and
        # compatibility with the July 31 diagnostic format.
        last_result = results[-1]
        report.update(
            persist_audit_diagnostics(last_result, report_path.parent)
        )
        if len(results) == 1:
            report["api"] = last_result.metadata

        audit_status = report.get("audit_status")
        usable_statuses = {
            "complete",
            "complete_with_gaps",
            "partial",
            "budget_exhausted",
        }
        if report.get("status") == "ok" and audit_status in usable_statuses:
            report["audit_state"] = "completed_usable"
        else:
            report["audit_state"] = "completed_unusable"
            validation_errors = [
                item.validation_error
                for item in results
                if item.validation_error
            ]
            if validation_errors:
                report["validation_error"] = "; ".join(validation_errors)
            elif audit_status == "error":
                report["validation_error"] = (
                    "Ни одно обязательное направление audit не было "
                    "подтверждено фактическим поиском"
                )
            report["error_stage"] = "response_validation"
    elif report.get("prior_audit_reused"):
        prior_state = (prior_report or {}).get("audit_state")
        if prior_state in {"completed_usable", "completed_unusable"}:
            report["audit_state"] = prior_state
        else:
            prior_api = (prior_report or {}).get("api") or {}
            prior_usable = (
                (prior_report or {}).get("status") == "ok"
                and isinstance(prior_api, dict)
                and prior_api.get("status") == "completed"
                and not (prior_report or {}).get("audit_error")
                and not (prior_report or {}).get("error")
            )
            report["audit_state"] = (
                "completed_usable" if prior_usable else "completed_unusable"
            )
        for key in ("api_output_path", "api_response_path", "validation_error"):
            if (prior_report or {}).get(key) is not None:
                report[key] = (prior_report or {}).get(key)
        if report["audit_state"] == "completed_unusable":
            report["error_stage"] = "response_validation"

    write_json(report_path, report)


def main() -> int:
    global _LAST_AUDIT_RESULT

    _LAST_AUDIT_RESULT = None
    _LAST_AUDIT_RESULTS.clear()
    report_path = _report_path()
    prior_report = _read_prior_report(report_path)
    _sync_policy_overrides()
    result = _policy.main()
    _finalize_report(report_path, prior_report)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
