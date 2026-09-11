#!/usr/bin/env python3
"""Durable at-most-once journal for Coverage-triggered editorial repair.

The journal is intentionally narrow: it activates only for the hidden
``.coverage-audit-YYYY-MM-DD.json`` research input used by Mandatory Coverage.
It never stores request prompts. A request hash binds the exact Responses API
arguments; the authoritative response text is saved separately so a recovery
can replay it without issuing a second paid editorial request.
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
from typing import Any, Iterable

CONTRACT_VERSION = 1
PENDING_STATES = {"prepared", "request_started", "response_saved", "failed_terminal"}
TERMINAL_SAFE_STATE = "applied"


class EditorialRepairJournalError(RuntimeError):
    """The repair state is unsafe or internally inconsistent."""


@dataclass(frozen=True)
class RepairContext:
    publication_date: str
    research_path: Path
    research_sha256: str
    model: str
    state_dir: Path
    journal_path: Path
    response_path: Path


def _utc_now() -> str:
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


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EditorialRepairJournalError(f"missing repair state: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EditorialRepairJournalError(f"invalid repair JSON: {path}") from exc


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _seal(payload: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(payload)
    result.pop(field, None)
    result[field] = canonical_sha256(result)
    return result


def _verify_seal(payload: dict[str, Any], field: str, label: str) -> None:
    expected = str(payload.get(field) or "")
    body = dict(payload)
    body.pop(field, None)
    actual = canonical_sha256(body)
    if not expected or expected != actual:
        raise EditorialRepairJournalError(f"{label} integrity check failed")


def _argv_value(argv: Iterable[str], flag: str) -> str | None:
    values = list(argv)
    for index, value in enumerate(values):
        if value == flag and index + 1 < len(values):
            return values[index + 1]
        prefix = flag + "="
        if value.startswith(prefix):
            return value[len(prefix):]
    return None


def repair_context_from_argv(
    stage: str,
    kwargs: dict[str, Any],
    *,
    argv: Iterable[str],
    usage_dir: str | None,
    cwd: Path | None = None,
) -> RepairContext | None:
    """Return a context only for the Mandatory Coverage editorial rerun."""
    if stage != "editorial":
        return None
    publication_date = (
        _argv_value(argv, "--publication-date")
        or os.environ.get("AI_DIGEST_PUBLICATION_DATE")
        or ""
    ).strip()
    research_arg = (_argv_value(argv, "--research-input") or "").strip()
    if not publication_date or not research_arg:
        return None
    expected_name = f".coverage-audit-{publication_date}.json"
    research_path = Path(research_arg)
    base = (cwd or Path.cwd()).resolve()
    if not research_path.is_absolute():
        research_path = (base / research_path).resolve()
    else:
        research_path = research_path.resolve()
    if research_path.name != expected_name:
        return None
    payload = _read_json(research_path)
    if not isinstance(payload, dict) or payload.get("publication_date") != publication_date:
        raise EditorialRepairJournalError(
            "Coverage repair research does not match publication_date"
        )
    model = str(kwargs.get("model") or "").strip()
    if not model:
        raise EditorialRepairJournalError("Coverage repair model is missing")
    research_sha = canonical_sha256(payload)
    if usage_dir:
        state_dir = Path(usage_dir).resolve().parent
    else:
        state_dir = base / "automation" / "preview" / "production-daily"
    stem = f"editorial-repair-{publication_date}-{research_sha[:16]}"
    return RepairContext(
        publication_date=publication_date,
        research_path=research_path,
        research_sha256=research_sha,
        model=model,
        state_dir=state_dir,
        journal_path=state_dir / f"{stem}.json",
        response_path=state_dir / f"{stem}.response.json",
    )


def request_binding_sha256(kwargs: dict[str, Any]) -> str:
    """Hash exact transport arguments without persisting prompt/request content."""
    return canonical_sha256(kwargs)


def _journal_identity(context: RepairContext) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "publication_date": context.publication_date,
        "research_sha256": context.research_sha256,
        "model": context.model,
    }


def _write_journal(context: RepairContext, record: dict[str, Any]) -> dict[str, Any]:
    sealed = _seal(record, "journal_sha256")
    _atomic_json(context.journal_path, sealed)
    return sealed


def _load_journal(context: RepairContext) -> dict[str, Any]:
    payload = _read_json(context.journal_path)
    if not isinstance(payload, dict):
        raise EditorialRepairJournalError("repair journal must be a JSON object")
    _verify_seal(payload, "journal_sha256", "repair journal")
    expected = _journal_identity(context)
    for key, value in expected.items():
        if payload.get(key) != value:
            raise EditorialRepairJournalError(
                f"repair journal identity mismatch for {key}"
            )
    return payload


def _new_journal(context: RepairContext) -> dict[str, Any]:
    now = _utc_now()
    record = {
        **_journal_identity(context),
        "state": "prepared",
        "created_at": now,
        "updated_at": now,
        "request_binding_sha256": None,
        "response_file": context.response_path.name,
        "response_sha256": None,
        "failure_type": None,
        "applied_artifact_sha256": None,
    }
    return _write_journal(context, record)


def _path(value: Any, *, cwd: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (cwd / path).resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _recovery_report(context: RepairContext) -> dict[str, Any] | None:
    path = context.state_dir / "recovery.json"
    if not path.is_file():
        return None
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else None


def _assert_recovery_evidence_coherent(
    context: RepairContext, report: dict[str, Any]
) -> tuple[Path, Path] | None:
    cwd = Path.cwd().resolve()
    selected = _path(report.get("selected_source"), cwd=cwd)
    recovery_root = _path(report.get("recovery_root"), cwd=cwd)
    if selected is None or recovery_root is None:
        return None
    if not _is_within(selected, recovery_root):
        raise EditorialRepairJournalError(
            "selected recovery source is outside recovery_root"
        )
    bundle_root = selected.parent
    for key in ("merged_coverage_research", "prior_coverage_audit"):
        evidence = report.get(key)
        if not isinstance(evidence, dict):
            continue
        source = _path(evidence.get("source"), cwd=cwd)
        if source is not None and not _is_within(source, bundle_root):
            raise EditorialRepairJournalError(
                f"recovery evidence {key} came from a different artifact bundle"
            )
    return recovery_root, bundle_root


def restore_selected_bundle_state(context: RepairContext) -> None:
    """Restore repair state only from the artifact bundle that supplied candidates."""
    report = _recovery_report(context)
    if not report:
        return
    resolved = _assert_recovery_evidence_coherent(context, report)
    if resolved is None:
        return
    recovery_root, bundle_root = resolved
    selected_state_dir = bundle_root / "production-daily"
    pattern = f"editorial-repair-{context.publication_date}-*.json"
    all_journals = [
        path.resolve()
        for path in recovery_root.rglob(pattern)
        if path.is_file() and not path.name.endswith(".response.json")
    ]
    foreign = [path for path in all_journals if not _is_within(path, selected_state_dir)]
    if foreign:
        raise EditorialRepairJournalError(
            "same-date editorial repair state exists outside the selected artifact bundle"
        )
    source_journal = selected_state_dir / context.journal_path.name
    source_response = selected_state_dir / context.response_path.name
    if context.journal_path.exists():
        return
    if source_journal.is_file():
        context.state_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_journal, context.journal_path)
        if source_response.is_file():
            shutil.copy2(source_response, context.response_path)
    elif all_journals:
        raise EditorialRepairJournalError(
            "selected artifact bundle has editorial repair state for a different research payload"
        )


def _response_payload(response: Any) -> dict[str, Any]:
    def get(name: str, default: Any = None) -> Any:
        return response.get(name, default) if isinstance(response, dict) else getattr(response, name, default)

    transport = get("_transport", {}) or {}
    if not isinstance(transport, dict):
        transport = _plain(transport)
    request_id = transport.get("openai_request_id") if isinstance(transport, dict) else None
    return {
        "id": get("id"),
        "model": get("model"),
        "status": get("status"),
        "service_tier": get("service_tier"),
        "usage": _plain(get("usage")),
        "error": _plain(get("error")),
        "output_text": str(get("output_text") or ""),
        "provider_request_id": request_id,
    }


def _write_response(
    context: RepairContext,
    *,
    binding_sha256: str,
    response: Any,
) -> str:
    body = {
        "contract_version": CONTRACT_VERSION,
        "publication_date": context.publication_date,
        "research_sha256": context.research_sha256,
        "request_binding_sha256": binding_sha256,
        "saved_at": _utc_now(),
        "response": _response_payload(response),
    }
    sealed = _seal(body, "response_sha256")
    _atomic_json(context.response_path, sealed)
    return str(sealed["response_sha256"])


def _load_response(
    context: RepairContext, *, binding_sha256: str
) -> tuple[dict[str, Any], str]:
    payload = _read_json(context.response_path)
    if not isinstance(payload, dict):
        raise EditorialRepairJournalError("repair response must be a JSON object")
    _verify_seal(payload, "response_sha256", "repair response")
    if payload.get("publication_date") != context.publication_date:
        raise EditorialRepairJournalError("repair response publication_date mismatch")
    if payload.get("research_sha256") != context.research_sha256:
        raise EditorialRepairJournalError("repair response research mismatch")
    if payload.get("request_binding_sha256") != binding_sha256:
        raise EditorialRepairJournalError("repair response request binding mismatch")
    response = payload.get("response")
    if not isinstance(response, dict):
        raise EditorialRepairJournalError("repair response payload is missing")
    return response, str(payload["response_sha256"])


def _as_replay(response: dict[str, Any]) -> Any:
    transport = {}
    if response.get("provider_request_id"):
        transport["openai_request_id"] = response.get("provider_request_id")
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


def prepare_and_check_replay(
    context: RepairContext, *, binding_sha256: str
) -> Any | None:
    """Prepare an operation, replay a saved response, or fail closed."""
    restore_selected_bundle_state(context)
    journal = _load_journal(context) if context.journal_path.is_file() else _new_journal(context)
    state = str(journal.get("state") or "")
    saved_binding = journal.get("request_binding_sha256")
    if saved_binding not in {None, binding_sha256}:
        raise EditorialRepairJournalError("repair request binding changed")

    if state in {"response_saved", "applied"}:
        response, response_sha = _load_response(context, binding_sha256=binding_sha256)
        if journal.get("response_sha256") not in {None, response_sha}:
            raise EditorialRepairJournalError("repair response hash disagrees with journal")
        return _as_replay(response)

    if state == "request_started":
        # Crash boundary: the response file is authoritative if it was fsynced
        # before the journal state update. Otherwise provider outcome is unknown.
        if context.response_path.is_file():
            response, response_sha = _load_response(context, binding_sha256=binding_sha256)
            journal.update(
                state="response_saved",
                response_sha256=response_sha,
                request_binding_sha256=binding_sha256,
                updated_at=_utc_now(),
                recovered_after_interruption=True,
            )
            _write_journal(context, journal)
            return _as_replay(response)
        raise EditorialRepairJournalError(
            "editorial repair request_started has no saved response; outcome is ambiguous and automatic retry is forbidden"
        )

    if state == "failed_terminal":
        raise EditorialRepairJournalError(
            "editorial repair is failed_terminal; automatic retry is forbidden"
        )
    if state != "prepared":
        raise EditorialRepairJournalError(f"unknown editorial repair state: {state}")
    return None


def begin_request(context: RepairContext, *, binding_sha256: str) -> None:
    journal = _load_journal(context)
    if journal.get("state") != "prepared":
        raise EditorialRepairJournalError(
            f"cannot start repair from state={journal.get('state')}"
        )
    if journal.get("request_binding_sha256") not in {None, binding_sha256}:
        raise EditorialRepairJournalError("repair request binding changed before transport")
    journal.update(
        state="request_started",
        request_binding_sha256=binding_sha256,
        request_started_at=_utc_now(),
        updated_at=_utc_now(),
    )
    _write_journal(context, journal)


def mark_failed_terminal(context: RepairContext, *, failure_type: str) -> None:
    journal = _load_journal(context)
    if journal.get("state") != "request_started":
        raise EditorialRepairJournalError(
            f"cannot fail repair from state={journal.get('state')}"
        )
    journal.update(
        state="failed_terminal",
        failure_type=str(failure_type)[:200],
        failed_at=_utc_now(),
        updated_at=_utc_now(),
    )
    _write_journal(context, journal)


def save_response(
    context: RepairContext,
    *,
    binding_sha256: str,
    response: Any,
) -> None:
    journal = _load_journal(context)
    if journal.get("state") != "request_started":
        raise EditorialRepairJournalError(
            f"cannot save repair response from state={journal.get('state')}"
        )
    response_sha = _write_response(
        context, binding_sha256=binding_sha256, response=response
    )
    journal.update(
        state="response_saved",
        response_sha256=response_sha,
        response_saved_at=_utc_now(),
        updated_at=_utc_now(),
    )
    _write_journal(context, journal)


def _coverage_obligation_pending(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("editorial_rerun_required") is True
        and payload.get("editorial_rerun_performed") is not True
        or payload.get("editorial_completion_required") is True
        and payload.get("editorial_completion_performed") is not True
    )


def recovery_has_pending_editorial_repair(
    evidence_root: Path, publication_date: str
) -> bool:
    for path in evidence_root.rglob("coverage-audit.json"):
        if not path.is_file():
            continue
        try:
            payload = _read_json(path)
        except EditorialRepairJournalError:
            continue
        if (
            isinstance(payload, dict)
            and payload.get("publication_date") == publication_date
            and _coverage_obligation_pending(payload)
        ):
            return True
    pattern = f"editorial-repair-{publication_date}-*.json"
    for path in evidence_root.rglob(pattern):
        if not path.is_file() or path.name.endswith(".response.json"):
            continue
        try:
            payload = _read_json(path)
            if isinstance(payload, dict):
                _verify_seal(payload, "journal_sha256", "repair journal")
                if payload.get("state") != TERMINAL_SAFE_STATE:
                    return True
        except EditorialRepairJournalError:
            return True
    return False


def _infer_publication_date(artifact_dir: Path, coverage: dict[str, Any] | None) -> str:
    if isinstance(coverage, dict) and isinstance(coverage.get("publication_date"), str):
        return str(coverage["publication_date"])
    try:
        year, month, day = artifact_dir.name.split("-")
        if len(year) == 4 and len(month) == 2 and len(day) == 2:
            return artifact_dir.name
    except ValueError:
        pass
    meta_path = artifact_dir / "meta.json"
    if meta_path.is_file():
        meta = _read_json(meta_path)
        if isinstance(meta, dict):
            for key in ("publication_date", "date"):
                if isinstance(meta.get(key), str) and meta[key]:
                    return str(meta[key])
    raise EditorialRepairJournalError("cannot infer publication date for repair validation")


def _mark_applied(
    context: RepairContext,
    journal: dict[str, Any],
    *,
    artifact_raw_sha256: str,
) -> None:
    journal.update(
        state=TERMINAL_SAFE_STATE,
        applied_at=_utc_now(),
        updated_at=_utc_now(),
        applied_artifact_sha256=artifact_raw_sha256,
    )
    _write_journal(context, journal)


def assert_publication_safe(
    artifact_dir: Path,
    *,
    state_dir: Path | None = None,
) -> None:
    """Fail closed when a required editorial repair has not been durably applied."""
    artifact_dir = artifact_dir.resolve()
    state_dir = (state_dir or artifact_dir.parent / "production-daily").resolve()
    coverage_path = state_dir / "coverage-audit.json"
    coverage: dict[str, Any] | None = None
    if coverage_path.is_file():
        raw = _read_json(coverage_path)
        coverage = raw if isinstance(raw, dict) else None
    publication_date = _infer_publication_date(artifact_dir, coverage)
    if coverage and _coverage_obligation_pending(coverage):
        raise EditorialRepairJournalError(
            "publication blocked: Coverage requires editorial repair/completion but it was not performed"
        )

    candidates_path = artifact_dir / "candidates.json"
    candidates_sha: str | None = None
    if candidates_path.is_file():
        candidates_sha = canonical_sha256(_read_json(candidates_path))
    raw_editorial_path = artifact_dir / "editorial-output-raw.json"
    raw_editorial: Any | None = None
    raw_editorial_sha: str | None = None
    if raw_editorial_path.is_file():
        raw_editorial = _read_json(raw_editorial_path)
        raw_editorial_sha = canonical_sha256(raw_editorial)

    performed = bool(
        coverage
        and (
            coverage.get("editorial_rerun_performed") is True
            or coverage.get("editorial_completion_performed") is True
        )
    )
    pattern = f"editorial-repair-{publication_date}-*.json"
    for journal_path in sorted(state_dir.glob(pattern)):
        if journal_path.name.endswith(".response.json"):
            continue
        payload = _read_json(journal_path)
        if not isinstance(payload, dict):
            raise EditorialRepairJournalError("repair journal must be an object")
        _verify_seal(payload, "journal_sha256", "repair journal")
        state = str(payload.get("state") or "")
        if state == TERMINAL_SAFE_STATE:
            if candidates_sha and payload.get("research_sha256") != candidates_sha:
                raise EditorialRepairJournalError(
                    "applied repair research does not match current candidates.json"
                )
            continue
        if state != "response_saved":
            raise EditorialRepairJournalError(
                f"publication blocked by editorial repair state={state or 'missing'}"
            )
        if not performed:
            raise EditorialRepairJournalError(
                "publication blocked: response is saved but Coverage did not record repair completion"
            )
        if candidates_sha is None or payload.get("research_sha256") != candidates_sha:
            raise EditorialRepairJournalError(
                "saved repair response does not match current candidates.json"
            )
        if raw_editorial is None or raw_editorial_sha is None:
            raise EditorialRepairJournalError(
                "saved repair response cannot be reconciled without editorial-output-raw.json"
            )
        context = RepairContext(
            publication_date=publication_date,
            research_path=Path("."),
            research_sha256=str(payload.get("research_sha256") or ""),
            model=str(payload.get("model") or ""),
            state_dir=state_dir,
            journal_path=journal_path,
            response_path=state_dir / str(payload.get("response_file") or ""),
        )
        binding = str(payload.get("request_binding_sha256") or "")
        if not binding:
            raise EditorialRepairJournalError("saved repair response has no request binding")
        response, response_sha = _load_response(context, binding_sha256=binding)
        if payload.get("response_sha256") != response_sha:
            raise EditorialRepairJournalError("repair response hash disagrees with journal")
        output_text = str(response.get("output_text") or "")
        try:
            output_payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise EditorialRepairJournalError(
                "saved repair response output_text is not valid JSON"
            ) from exc
        if canonical_sha256(output_payload) != raw_editorial_sha:
            raise EditorialRepairJournalError(
                "saved repair response does not match current editorial-output-raw.json"
            )
        _mark_applied(
            context,
            payload,
            artifact_raw_sha256=raw_editorial_sha,
        )
