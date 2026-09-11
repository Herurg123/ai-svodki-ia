#!/usr/bin/env python3
"""Durable, fail-closed state machine for Coverage editorial completion.

This module is intentionally narrow. It protects only editorial completion that
runs from a saved Coverage candidate pool. It never performs research or search,
never stores request prompts, and never guesses whether an ambiguous provider
request was billed.

The durable state lives under ``automation/preview/production-daily`` so it is
included in failed-run artifacts and survives rollback of the dated digest
directory. Request content is represented only by a SHA-256 binding; the raw
provider response is persisted because replaying parse/validation after a crash
must not buy the same editorial response twice.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

VERSION = 1
PENDING_STATES = {
    "required",
    "prepared",
    "request_started",
    "response_saved",
    "failed_before_request",
    "unknown_after_request",
}


class EditorialRepairError(RuntimeError):
    """The repair state is unsafe, ambiguous, or internally inconsistent."""


@dataclass(frozen=True)
class RepairContext:
    publication_date: str
    state_dir: Path
    journal_path: Path
    response_path: Path
    persisted_research_path: Path
    archive_path: Path
    artifact_dir: Path
    model: str
    intent_sha256: str
    research_sha256: str
    candidate_pool_sha256: str
    archive_sha256: str
    artifact_identity_sha256: str
    search_window_sha256: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        _plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EditorialRepairError(f"missing repair input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EditorialRepairError(f"invalid repair JSON: {path}") from exc


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result.pop(field, None)
    result[field] = canonical_sha256(result)
    return result


def _verify_seal(value: dict[str, Any], field: str, label: str) -> None:
    expected = str(value.get(field) or "")
    body = dict(value)
    body.pop(field, None)
    if not expected or expected != canonical_sha256(body):
        raise EditorialRepairError(f"{label} integrity check failed")


def _artifact_identity(artifact_dir: Path) -> str:
    names = (
        "run-info.json",
        "candidates.json",
        "stories.json",
        "digest.json",
        "editorial-output.json",
        "editorial-output-raw.json",
        "article.html",
        "meta.json",
    )
    rows: list[dict[str, str]] = []
    for name in names:
        path = artifact_dir / name
        if path.is_file():
            rows.append({"name": name, "sha256": _file_sha256(path)})
    return canonical_sha256(rows)


def _journal_path(state_dir: Path, publication_date: str) -> Path:
    return state_dir / f"editorial-repair-{publication_date}.json"


def _response_path(state_dir: Path, publication_date: str) -> Path:
    return state_dir / f"editorial-repair-{publication_date}.response.json"


def _legacy_pending(report: Any) -> bool:
    return bool(
        isinstance(report, dict)
        and (
            report.get("editorial_rerun_required") is True
            and report.get("editorial_rerun_performed") is not True
            or report.get("editorial_completion_required") is True
            and report.get("editorial_completion_performed") is not True
        )
    )


def _legacy_safe_pre_request_failure(report: dict[str, Any]) -> bool:
    error = str(report.get("editorial_repair_error") or report.get("error") or "")
    return bool(
        "ModuleNotFoundError" in error
        and "No module named 'openai'" in error
    )


def _identity_record(context: RepairContext) -> dict[str, Any]:
    return {
        "version": VERSION,
        "publication_date": context.publication_date,
        "intent_sha256": context.intent_sha256,
        "research_sha256": context.research_sha256,
        "candidate_pool_sha256": context.candidate_pool_sha256,
        "archive_sha256": context.archive_sha256,
        "artifact_identity_sha256": context.artifact_identity_sha256,
        "search_window_sha256": context.search_window_sha256,
        "model": context.model,
        "persisted_research_file": context.persisted_research_path.name,
        "response_file": context.response_path.name,
    }


def _context(
    *,
    publication_date: str,
    state_dir: Path,
    persisted_research_path: Path,
    archive_path: Path,
    artifact_dir: Path,
    model: str,
) -> RepairContext:
    state_dir = state_dir.resolve()
    persisted_research_path = persisted_research_path.resolve()
    archive_path = archive_path.resolve()
    artifact_dir = artifact_dir.resolve()
    research = _read_json(persisted_research_path)
    archive = _read_json(archive_path)
    if not isinstance(research, dict) or research.get("publication_date") != publication_date:
        raise EditorialRepairError("persisted Coverage research/date mismatch")
    candidates = research.get("candidates")
    if not isinstance(candidates, list):
        raise EditorialRepairError("persisted Coverage research has no candidates[]")
    search_window = research.get("search_window")
    if not isinstance(search_window, dict):
        raise EditorialRepairError("persisted Coverage research has no search_window")
    model = str(model or "").strip()
    if not model:
        raise EditorialRepairError("editorial repair model is missing")
    research_sha = canonical_sha256(research)
    candidate_sha = canonical_sha256(candidates)
    archive_sha = canonical_sha256(archive)
    artifact_sha = _artifact_identity(artifact_dir)
    window_sha = canonical_sha256(search_window)
    intent = canonical_sha256(
        {
            "version": VERSION,
            "publication_date": publication_date,
            "research_sha256": research_sha,
            "candidate_pool_sha256": candidate_sha,
            "archive_sha256": archive_sha,
            "artifact_identity_sha256": artifact_sha,
            "search_window_sha256": window_sha,
            "model": model,
        }
    )
    return RepairContext(
        publication_date=publication_date,
        state_dir=state_dir,
        journal_path=_journal_path(state_dir, publication_date),
        response_path=_response_path(state_dir, publication_date),
        persisted_research_path=persisted_research_path,
        archive_path=archive_path,
        artifact_dir=artifact_dir,
        model=model,
        intent_sha256=intent,
        research_sha256=research_sha,
        candidate_pool_sha256=candidate_sha,
        archive_sha256=archive_sha,
        artifact_identity_sha256=artifact_sha,
        search_window_sha256=window_sha,
    )


def _write_journal(context: RepairContext, value: dict[str, Any]) -> dict[str, Any]:
    sealed = _seal(value, "journal_sha256")
    _atomic_json(context.journal_path, sealed)
    return sealed


def _load_journal(context: RepairContext) -> dict[str, Any]:
    value = _read_json(context.journal_path)
    if not isinstance(value, dict):
        raise EditorialRepairError("editorial repair journal is not an object")
    _verify_seal(value, "journal_sha256", "editorial repair journal")
    expected = _identity_record(context)
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise EditorialRepairError(f"editorial repair identity mismatch: {key}")
    return value


def prepare_required(
    *,
    publication_date: str,
    state_dir: Path,
    persisted_research_path: Path,
    archive_path: Path,
    artifact_dir: Path,
    model: str,
    legacy_report_path: Path | None = None,
) -> RepairContext:
    """Persist the repair obligation before any child/import/provider call."""
    context = _context(
        publication_date=publication_date,
        state_dir=state_dir,
        persisted_research_path=persisted_research_path,
        archive_path=archive_path,
        artifact_dir=artifact_dir,
        model=model,
    )
    if context.journal_path.is_file():
        _load_journal(context)
        return context

    legacy_retry_authorized = False
    legacy_retry_reason = None
    if legacy_report_path is not None and legacy_report_path.is_file():
        legacy = _read_json(legacy_report_path)
        if _legacy_pending(legacy):
            if not isinstance(legacy, dict) or not _legacy_safe_pre_request_failure(legacy):
                raise EditorialRepairError(
                    "legacy repair is pending but provider admission is ambiguous; automatic retry forbidden"
                )
            legacy_retry_authorized = True
            legacy_retry_reason = "proven_pre_request_missing_openai_sdk"

    now = _now()
    _write_journal(
        context,
        {
            **_identity_record(context),
            "state": "required",
            "created_at": now,
            "updated_at": now,
            "request_sha256": None,
            "response_sha256": None,
            "failure_type": None,
            "legacy_retry_authorized": legacy_retry_authorized,
            "legacy_retry_reason": legacy_retry_reason,
            "validated_editorial_sha256": None,
        },
    )
    return context


def load_required(
    *,
    publication_date: str,
    state_dir: Path,
    persisted_research_path: Path,
    archive_path: Path,
    artifact_dir: Path,
    model: str,
) -> RepairContext:
    context = _context(
        publication_date=publication_date,
        state_dir=state_dir,
        persisted_research_path=persisted_research_path,
        archive_path=archive_path,
        artifact_dir=artifact_dir,
        model=model,
    )
    _load_journal(context)
    return context


def request_sha256(kwargs: dict[str, Any]) -> str:
    """Bind model/prompt/schema/limits without persisting request content."""
    return canonical_sha256(kwargs)


def _response_payload(response: Any) -> dict[str, Any]:
    def get(name: str, default: Any = None) -> Any:
        return response.get(name, default) if isinstance(response, dict) else getattr(response, name, default)

    transport = _plain(get("_transport", {}) or {})
    return {
        "id": get("id"),
        "model": get("model"),
        "status": get("status"),
        "service_tier": get("service_tier"),
        "usage": _plain(get("usage")),
        "error": _plain(get("error")),
        "output_text": str(get("output_text") or ""),
        "provider_request_id": (
            transport.get("openai_request_id") if isinstance(transport, dict) else None
        ),
    }


def _write_response(context: RepairContext, request_sha: str, response: Any) -> str:
    value = _seal(
        {
            "version": VERSION,
            "publication_date": context.publication_date,
            "intent_sha256": context.intent_sha256,
            "request_sha256": request_sha,
            "saved_at": _now(),
            "response": _response_payload(response),
        },
        "response_sha256",
    )
    _atomic_json(context.response_path, value)
    return str(value["response_sha256"])


def _load_response(context: RepairContext, request_sha: str) -> tuple[dict[str, Any], str]:
    value = _read_json(context.response_path)
    if not isinstance(value, dict):
        raise EditorialRepairError("editorial repair response is not an object")
    _verify_seal(value, "response_sha256", "editorial repair response")
    if value.get("publication_date") != context.publication_date:
        raise EditorialRepairError("editorial repair response date mismatch")
    if value.get("intent_sha256") != context.intent_sha256:
        raise EditorialRepairError("editorial repair response intent mismatch")
    if value.get("request_sha256") != request_sha:
        raise EditorialRepairError("editorial repair response request mismatch")
    response = value.get("response")
    if not isinstance(response, dict):
        raise EditorialRepairError("editorial repair response payload missing")
    return response, str(value["response_sha256"])


def _replay(response: dict[str, Any]) -> Any:
    transport: dict[str, Any] = {}
    if response.get("provider_request_id"):
        transport["openai_request_id"] = response["provider_request_id"]
    return SimpleNamespace(
        id=response.get("id"),
        model=response.get("model"),
        status=response.get("status"),
        service_tier=response.get("service_tier"),
        usage=response.get("usage"),
        error=response.get("error"),
        output_text=response.get("output_text") or "",
        output=[],
        _transport=transport,
    )


def prepare_request(context: RepairContext, request_sha: str) -> Any | None:
    journal = _load_journal(context)
    state = str(journal.get("state") or "")
    saved_request = journal.get("request_sha256")
    if saved_request not in {None, request_sha}:
        raise EditorialRepairError("editorial repair request contract changed")

    if state == "validated":
        response, saved_sha = _load_response(context, request_sha)
        if journal.get("response_sha256") != saved_sha:
            raise EditorialRepairError("validated repair response hash mismatch")
        return _replay(response)
    if state == "response_saved":
        response, saved_sha = _load_response(context, request_sha)
        if journal.get("response_sha256") != saved_sha:
            raise EditorialRepairError("saved repair response hash mismatch")
        return _replay(response)
    if state == "request_started":
        if context.response_path.is_file():
            response, saved_sha = _load_response(context, request_sha)
            journal.update(
                state="response_saved",
                response_sha256=saved_sha,
                recovered_after_interruption=True,
                updated_at=_now(),
            )
            _write_journal(context, journal)
            return _replay(response)
        journal.update(state="unknown_after_request", updated_at=_now())
        _write_journal(context, journal)
        raise EditorialRepairError(
            "editorial repair request outcome is ambiguous; automatic retry forbidden"
        )
    if state == "unknown_after_request":
        raise EditorialRepairError(
            "editorial repair outcome remains unknown; automatic retry forbidden"
        )
    if state == "failed_before_request":
        journal.update(
            state="required",
            retry_after_pre_request_failure=True,
            updated_at=_now(),
        )
        _write_journal(context, journal)
        state = "required"
    if state == "required":
        journal.update(
            state="prepared",
            request_sha256=request_sha,
            prepared_at=_now(),
            updated_at=_now(),
        )
        _write_journal(context, journal)
        return None
    if state == "prepared":
        return None
    raise EditorialRepairError(f"unknown editorial repair state: {state}")


def begin_request(context: RepairContext, request_sha: str) -> None:
    journal = _load_journal(context)
    if journal.get("state") != "prepared" or journal.get("request_sha256") != request_sha:
        raise EditorialRepairError("editorial repair cannot enter request_started")
    journal.update(state="request_started", request_started_at=_now(), updated_at=_now())
    _write_journal(context, journal)


def mark_failed_before_request(context: RepairContext, failure_type: str) -> None:
    journal = _load_journal(context)
    if journal.get("state") not in {"required", "prepared"}:
        return
    journal.update(
        state="failed_before_request",
        failure_type=str(failure_type)[:200],
        failed_before_request_at=_now(),
        updated_at=_now(),
    )
    _write_journal(context, journal)


def mark_unknown_after_request(context: RepairContext, failure_type: str) -> None:
    journal = _load_journal(context)
    if journal.get("state") != "request_started":
        return
    journal.update(
        state="unknown_after_request",
        failure_type=str(failure_type)[:200],
        unknown_after_request_at=_now(),
        updated_at=_now(),
    )
    _write_journal(context, journal)


def save_response(context: RepairContext, request_sha: str, response: Any) -> None:
    journal = _load_journal(context)
    if journal.get("state") != "request_started" or journal.get("request_sha256") != request_sha:
        raise EditorialRepairError("editorial repair response cannot be saved from current state")
    response_sha = _write_response(context, request_sha, response)
    journal.update(
        state="response_saved",
        response_sha256=response_sha,
        response_saved_at=_now(),
        updated_at=_now(),
    )
    _write_journal(context, journal)


def mark_validated(context: RepairContext) -> None:
    journal = _load_journal(context)
    if journal.get("state") == "validated":
        return
    if journal.get("state") != "response_saved":
        raise EditorialRepairError("editorial repair cannot validate without saved response")
    request_sha = str(journal.get("request_sha256") or "")
    if not request_sha:
        raise EditorialRepairError("editorial repair request hash missing")
    response, response_sha = _load_response(context, request_sha)
    if journal.get("response_sha256") != response_sha:
        raise EditorialRepairError("editorial repair response hash mismatch")
    raw_path = context.artifact_dir / "editorial-output-raw.json"
    raw = _read_json(raw_path)
    try:
        response_json = json.loads(str(response.get("output_text") or ""))
    except json.JSONDecodeError as exc:
        raise EditorialRepairError("saved editorial response is not valid JSON") from exc
    raw_sha = canonical_sha256(raw)
    if canonical_sha256(response_json) != raw_sha:
        raise EditorialRepairError(
            "saved editorial response does not match editorial-output-raw.json"
        )
    journal.update(
        state="validated",
        validated_at=_now(),
        validated_editorial_sha256=raw_sha,
        updated_at=_now(),
    )
    _write_journal(context, journal)


def clone_no_retry_callback(callback: Callable[..., Any]) -> Callable[..., Any]:
    """Return the same Responses resource on a client with SDK retries disabled."""
    resource = getattr(callback, "__self__", None)
    client = getattr(resource, "_client", None)
    with_options = getattr(client, "with_options", None)
    if not callable(with_options):
        raise EditorialRepairError("cannot create no-retry OpenAI client for repair")
    strict_client = with_options(max_retries=0)
    responses = getattr(strict_client, "responses", None)
    strict_callback = getattr(responses, "create", None)
    if not callable(strict_callback):
        raise EditorialRepairError("no-retry client does not expose responses.create")
    return strict_callback


def _read_coverage(state_dir: Path) -> dict[str, Any] | None:
    path = state_dir / "coverage-audit.json"
    if not path.is_file():
        return None
    value = _read_json(path)
    if not isinstance(value, dict):
        raise EditorialRepairError("coverage-audit.json is not an object")
    return value


def journal_state(state_dir: Path, publication_date: str) -> str | None:
    path = _journal_path(state_dir.resolve(), publication_date)
    if not path.is_file():
        return None
    value = _read_json(path)
    if not isinstance(value, dict):
        raise EditorialRepairError("editorial repair journal is not an object")
    _verify_seal(value, "journal_sha256", "editorial repair journal")
    return str(value.get("state") or "")


def recovery_pending(bundle_root: Path, publication_date: str) -> bool:
    state_dir = bundle_root.resolve() / "production-daily"
    try:
        coverage = _read_coverage(state_dir)
        if _legacy_pending(coverage):
            return True
        state = journal_state(state_dir, publication_date)
        return state is not None and state != "validated"
    except EditorialRepairError:
        return True


def restore_state_from_bundle(
    *, bundle_root: Path, target_state_dir: Path, publication_date: str
) -> dict[str, Any]:
    """Copy repair state only from the bundle selected for candidates/audit."""
    source_state = bundle_root.resolve() / "production-daily"
    target_state = target_state_dir.resolve()
    copied: list[str] = []
    for source in (
        _journal_path(source_state, publication_date),
        _response_path(source_state, publication_date),
    ):
        if not source.is_file():
            continue
        target = target_state / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and _file_sha256(target) != _file_sha256(source):
            raise EditorialRepairError(
                f"conflicting editorial repair state for {source.name}"
            )
        if not target.is_file():
            shutil.copy2(source, target)
            copied.append(source.name)
    return {"source_state_dir": str(source_state), "copied": copied}


def publication_safe(artifact_dir: Path, state_dir: Path | None = None) -> None:
    artifact_dir = artifact_dir.resolve()
    state_dir = (state_dir or artifact_dir.parent / "production-daily").resolve()
    date = artifact_dir.name
    coverage = _read_coverage(state_dir)
    if isinstance(coverage, dict):
        date = str(coverage.get("publication_date") or date)
        if _legacy_pending(coverage):
            raise EditorialRepairError(
                "Coverage requires editorial repair/completion but did not record completion"
            )

    path = _journal_path(state_dir, date)
    if not path.is_file():
        return
    journal = _read_json(path)
    if not isinstance(journal, dict):
        raise EditorialRepairError("editorial repair journal is not an object")
    _verify_seal(journal, "journal_sha256", "editorial repair journal")
    if journal.get("state") != "validated":
        raise EditorialRepairError(
            f"publication blocked by editorial repair state={journal.get('state') or 'missing'}"
        )
    response_path = state_dir / str(journal.get("response_file") or "")
    if not response_path.is_file():
        raise EditorialRepairError("validated repair response file is missing")
    response = _read_json(response_path)
    if not isinstance(response, dict):
        raise EditorialRepairError("validated repair response is not an object")
    _verify_seal(response, "response_sha256", "editorial repair response")
    request_sha = str(journal.get("request_sha256") or "")
    if response.get("request_sha256") != request_sha:
        raise EditorialRepairError("validated repair request binding mismatch")
    payload = response.get("response")
    if not isinstance(payload, dict):
        raise EditorialRepairError("validated repair response payload missing")
    try:
        response_json = json.loads(str(payload.get("output_text") or ""))
    except json.JSONDecodeError as exc:
        raise EditorialRepairError("validated repair response is invalid JSON") from exc
    raw = _read_json(artifact_dir / "editorial-output-raw.json")
    if canonical_sha256(response_json) != canonical_sha256(raw):
        raise EditorialRepairError("validated repair no longer matches final editorial artifact")


def summary(state_dir: Path, publication_date: str) -> dict[str, Any]:
    path = _journal_path(state_dir.resolve(), publication_date)
    if not path.is_file():
        return {"status": "absent"}
    value = _read_json(path)
    if not isinstance(value, dict):
        raise EditorialRepairError("editorial repair journal is not an object")
    _verify_seal(value, "journal_sha256", "editorial repair journal")
    return {
        "status": "present",
        "state": value.get("state"),
        "intent_sha256": value.get("intent_sha256"),
        "request_sha256": value.get("request_sha256"),
        "response_sha256": value.get("response_sha256"),
        "legacy_retry_authorized": value.get("legacy_retry_authorized"),
    }
