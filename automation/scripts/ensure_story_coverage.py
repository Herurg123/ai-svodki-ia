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
        max_output_tokens=10000,
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
            queries = payload.get("queries_used")
            if not isinstance(queries, list) or not queries:
                validation_error = "Coverage audit не заполнил queries_used"
            elif len(queries) > maximum_web_search_calls:
                validation_error = "queries_used превышает установленный лимит"

    result = AuditRequestResult(
        payload=payload if isinstance(payload, dict) else None,
        metadata=metadata,
        output_text=output_text,
        raw_response=response_to_plain(response),
        validation_error=validation_error,
    )
    _LAST_AUDIT_RESULT = result
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
        return value
    if isinstance(value, tuple) and len(value) == 2:
        payload, metadata = value
        if isinstance(payload, dict) and isinstance(metadata, dict):
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
        and api.get("status") == "completed"
    )


def _policy_audit_request(**kwargs: Any) -> AuditRequestResult:
    global _LAST_AUDIT_RESULT

    result = coerce_audit_result(globals()["run_audit_request"](**kwargs))
    _LAST_AUDIT_RESULT = result
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

    if _LAST_AUDIT_RESULT is not None:
        result = _LAST_AUDIT_RESULT
        report["api"] = result.metadata
        observed = result.metadata.get(
            "web_search_call_items_total",
            result.metadata.get(
                "observed_web_search_calls",
                result.metadata.get("web_search_calls", 0),
            ),
        )
        report["web_search_performed"] = int(observed or 0) > 0
        report.update(persist_audit_diagnostics(result, report_path.parent))
        payload_ok = (
            isinstance(result.payload, dict)
            and result.payload.get("status") == "ok"
        )
        if result.validation_error is None and payload_ok:
            report["audit_state"] = "completed_usable"
        else:
            report["audit_state"] = "completed_unusable"
            validation_error = result.validation_error
            if validation_error is None and isinstance(result.payload, dict):
                validation_error = (
                    "Coverage audit вернул status=error: "
                    + str(
                        result.payload.get("error_message")
                        or "причина не указана"
                    )
                )
            report["validation_error"] = validation_error
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
    report_path = _report_path()
    prior_report = _read_prior_report(report_path)
    _sync_policy_overrides()
    result = _policy.main()
    _finalize_report(report_path, prior_report)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
