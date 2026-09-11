#!/usr/bin/env python3
"""Crash-safe at-most-once contract for Coverage editorial repair.

Only the Mandatory Coverage hidden research input activates this contract.
Request content is never persisted: an exact hash binds the transport request,
while the provider response is saved so recovery can replay it without a second
paid editorial call.
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

VERSION = 1


class EditorialRepairError(RuntimeError):
    pass


@dataclass(frozen=True)
class Context:
    date: str
    research: Path
    research_sha: str
    model: str
    state_dir: Path
    journal: Path
    response: Path


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
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def digest(value: Any) -> str:
    raw = json.dumps(
        _plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise EditorialRepairError(f"invalid or missing repair JSON: {path}") from exc


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def _seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result.pop(field, None)
    result[field] = digest(result)
    return result


def _verify(value: dict[str, Any], field: str, label: str) -> None:
    expected = str(value.get(field) or "")
    body = dict(value)
    body.pop(field, None)
    if not expected or expected != digest(body):
        raise EditorialRepairError(f"{label} integrity check failed")


def _arg(argv: Iterable[str], flag: str) -> str | None:
    values = list(argv)
    for i, value in enumerate(values):
        if value == flag and i + 1 < len(values):
            return values[i + 1]
        if value.startswith(flag + "="):
            return value.split("=", 1)[1]
    return None


def context_from_argv(
    stage: str,
    kwargs: dict[str, Any],
    *,
    argv: Iterable[str],
    usage_dir: str | None,
    cwd: Path | None = None,
) -> Context | None:
    if stage != "editorial":
        return None
    date = (_arg(argv, "--publication-date") or os.getenv("AI_DIGEST_PUBLICATION_DATE") or "").strip()
    research_arg = (_arg(argv, "--research-input") or "").strip()
    if not date or not research_arg:
        return None
    base = (cwd or Path.cwd()).resolve()
    research = Path(research_arg)
    research = research.resolve() if research.is_absolute() else (base / research).resolve()
    if research.name != f".coverage-audit-{date}.json":
        return None
    payload = _read(research)
    if not isinstance(payload, dict) or payload.get("publication_date") != date:
        raise EditorialRepairError("Coverage repair research/date mismatch")
    model = str(kwargs.get("model") or "").strip()
    if not model:
        raise EditorialRepairError("Coverage repair model is missing")
    research_sha = digest(payload)
    state_dir = Path(usage_dir).resolve().parent if usage_dir else base / "automation/preview/production-daily"
    stem = f"editorial-repair-{date}-{research_sha[:16]}"
    return Context(
        date=date,
        research=research,
        research_sha=research_sha,
        model=model,
        state_dir=state_dir,
        journal=state_dir / f"{stem}.json",
        response=state_dir / f"{stem}.response.json",
    )


def request_sha(kwargs: dict[str, Any]) -> str:
    return digest(kwargs)


def _journal_identity(ctx: Context) -> dict[str, Any]:
    return {"version": VERSION, "publication_date": ctx.date, "research_sha256": ctx.research_sha, "model": ctx.model}


def _save_journal(ctx: Context, value: dict[str, Any]) -> dict[str, Any]:
    sealed = _seal(value, "journal_sha256")
    _write(ctx.journal, sealed)
    return sealed


def _load_journal(ctx: Context) -> dict[str, Any]:
    value = _read(ctx.journal)
    if not isinstance(value, dict):
        raise EditorialRepairError("repair journal is not an object")
    _verify(value, "journal_sha256", "repair journal")
    for key, expected in _journal_identity(ctx).items():
        if value.get(key) != expected:
            raise EditorialRepairError(f"repair journal identity mismatch: {key}")
    return value


def _new_journal(ctx: Context) -> dict[str, Any]:
    now = _now()
    return _save_journal(ctx, {
        **_journal_identity(ctx),
        "state": "prepared",
        "created_at": now,
        "updated_at": now,
        "request_sha256": None,
        "response_file": ctx.response.name,
        "response_sha256": None,
        "failure_type": None,
        "applied_editorial_sha256": None,
    })


def _path(value: Any, cwd: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (cwd / path).resolve()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _restore_from_selected_bundle(ctx: Context) -> None:
    recovery_file = ctx.state_dir / "recovery.json"
    if not recovery_file.is_file():
        return
    report = _read(recovery_file)
    if not isinstance(report, dict):
        raise EditorialRepairError("recovery.json is not an object")
    cwd = Path.cwd().resolve()
    selected = _path(report.get("selected_source"), cwd)
    recovery_root = _path(report.get("recovery_root"), cwd)
    if selected is None or recovery_root is None:
        return
    if not _inside(selected, recovery_root):
        raise EditorialRepairError("selected recovery source is outside recovery_root")
    bundle_root = selected.parent
    for key in ("merged_coverage_research", "prior_coverage_audit"):
        row = report.get(key)
        if not isinstance(row, dict):
            continue
        source = _path(row.get("source"), cwd)
        if source is not None and not _inside(source, bundle_root):
            raise EditorialRepairError(f"{key} came from a different artifact bundle")

    selected_state = bundle_root / "production-daily"
    pattern = f"editorial-repair-{ctx.date}-*.json"
    journals = [
        p.resolve() for p in recovery_root.rglob(pattern)
        if p.is_file() and not p.name.endswith(".response.json")
    ]
    if any(not _inside(p, selected_state) for p in journals):
        raise EditorialRepairError("same-date repair state exists outside selected artifact bundle")
    source_journal = selected_state / ctx.journal.name
    source_response = selected_state / ctx.response.name
    if ctx.journal.exists():
        return
    if source_journal.is_file():
        ctx.state_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_journal, ctx.journal)
        if source_response.is_file():
            shutil.copy2(source_response, ctx.response)
    elif journals:
        raise EditorialRepairError("selected bundle repair state belongs to different research")


def _response_payload(response: Any) -> dict[str, Any]:
    def get(name: str, default: Any = None) -> Any:
        return response.get(name, default) if isinstance(response, dict) else getattr(response, name, default)
    transport = _plain(get("_transport", {}) or {})
    return {
        "id": get("id"), "model": get("model"), "status": get("status"),
        "service_tier": get("service_tier"), "usage": _plain(get("usage")),
        "error": _plain(get("error")), "output_text": str(get("output_text") or ""),
        "provider_request_id": transport.get("openai_request_id") if isinstance(transport, dict) else None,
    }


def _save_response(ctx: Context, binding: str, response: Any) -> str:
    value = _seal({
        "version": VERSION,
        "publication_date": ctx.date,
        "research_sha256": ctx.research_sha,
        "request_sha256": binding,
        "saved_at": _now(),
        "response": _response_payload(response),
    }, "response_sha256")
    _write(ctx.response, value)
    return str(value["response_sha256"])


def _load_response(ctx: Context, binding: str) -> tuple[dict[str, Any], str]:
    value = _read(ctx.response)
    if not isinstance(value, dict):
        raise EditorialRepairError("repair response is not an object")
    _verify(value, "response_sha256", "repair response")
    if value.get("publication_date") != ctx.date or value.get("research_sha256") != ctx.research_sha:
        raise EditorialRepairError("repair response identity mismatch")
    if value.get("request_sha256") != binding:
        raise EditorialRepairError("repair response request binding mismatch")
    response = value.get("response")
    if not isinstance(response, dict):
        raise EditorialRepairError("repair response payload missing")
    return response, str(value["response_sha256"])


def _replay(value: dict[str, Any]) -> Any:
    transport = {}
    if value.get("provider_request_id"):
        transport["openai_request_id"] = value["provider_request_id"]
    return SimpleNamespace(
        id=value.get("id"), model=value.get("model"), status=value.get("status"),
        service_tier=value.get("service_tier"), usage=value.get("usage"), error=value.get("error"),
        output_text=value.get("output_text") or "", output=[], _transport=transport,
    )


def check_or_prepare(ctx: Context, binding: str) -> Any | None:
    _restore_from_selected_bundle(ctx)
    journal = _load_journal(ctx) if ctx.journal.is_file() else _new_journal(ctx)
    state = str(journal.get("state") or "")
    if journal.get("request_sha256") not in {None, binding}:
        raise EditorialRepairError("repair request binding changed")
    if state in {"response_saved", "applied"}:
        response, saved_sha = _load_response(ctx, binding)
        if journal.get("response_sha256") not in {None, saved_sha}:
            raise EditorialRepairError("repair response hash disagrees with journal")
        return _replay(response)
    if state == "request_started":
        if ctx.response.is_file():
            response, saved_sha = _load_response(ctx, binding)
            journal.update(
                state="response_saved", response_sha256=saved_sha,
                request_sha256=binding, recovered_after_interruption=True, updated_at=_now()
            )
            _save_journal(ctx, journal)
            return _replay(response)
        raise EditorialRepairError("repair request outcome is ambiguous; automatic retry forbidden")
    if state == "failed_terminal":
        raise EditorialRepairError("repair failed_terminal; automatic retry forbidden")
    if state != "prepared":
        raise EditorialRepairError(f"unknown repair state: {state}")
    return None


def begin(ctx: Context, binding: str) -> None:
    journal = _load_journal(ctx)
    if journal.get("state") != "prepared" or journal.get("request_sha256") not in {None, binding}:
        raise EditorialRepairError("repair cannot enter request_started")
    journal.update(state="request_started", request_sha256=binding, request_started_at=_now(), updated_at=_now())
    _save_journal(ctx, journal)


def fail_terminal(ctx: Context, failure_type: str) -> None:
    journal = _load_journal(ctx)
    if journal.get("state") != "request_started":
        raise EditorialRepairError("repair cannot enter failed_terminal")
    journal.update(state="failed_terminal", failure_type=str(failure_type)[:200], failed_at=_now(), updated_at=_now())
    _save_journal(ctx, journal)


def save_response(ctx: Context, binding: str, response: Any) -> None:
    journal = _load_journal(ctx)
    if journal.get("state") != "request_started":
        raise EditorialRepairError("repair response cannot be saved from current state")
    saved_sha = _save_response(ctx, binding, response)
    journal.update(state="response_saved", response_sha256=saved_sha, response_saved_at=_now(), updated_at=_now())
    _save_journal(ctx, journal)


def _obligation_pending(report: dict[str, Any]) -> bool:
    return bool(
        report.get("editorial_rerun_required") is True and report.get("editorial_rerun_performed") is not True
        or report.get("editorial_completion_required") is True and report.get("editorial_completion_performed") is not True
    )


def recovery_pending(root: Path, date: str) -> bool:
    for path in root.rglob("coverage-audit.json"):
        if not path.is_file():
            continue
        try:
            value = _read(path)
        except EditorialRepairError:
            continue
        if isinstance(value, dict) and value.get("publication_date") == date and _obligation_pending(value):
            return True
    for path in root.rglob(f"editorial-repair-{date}-*.json"):
        if not path.is_file() or path.name.endswith(".response.json"):
            continue
        try:
            value = _read(path)
            if not isinstance(value, dict):
                return True
            _verify(value, "journal_sha256", "repair journal")
            if value.get("state") != "applied":
                return True
        except EditorialRepairError:
            return True
    return False


def publication_safe(artifact_dir: Path, state_dir: Path | None = None) -> None:
    artifact_dir = artifact_dir.resolve()
    state_dir = (state_dir or artifact_dir.parent / "production-daily").resolve()
    coverage_file = state_dir / "coverage-audit.json"
    coverage = _read(coverage_file) if coverage_file.is_file() else None
    if coverage is not None and not isinstance(coverage, dict):
        raise EditorialRepairError("coverage-audit.json is not an object")
    date = str((coverage or {}).get("publication_date") or artifact_dir.name)
    if isinstance(coverage, dict) and _obligation_pending(coverage):
        raise EditorialRepairError("Coverage requires editorial repair/completion but it was not performed")

    merged_file = state_dir / f"coverage-audit-merged-candidates-{date}.json"
    merged_sha = digest(_read(merged_file)) if merged_file.is_file() else None
    raw_file = artifact_dir / "editorial-output-raw.json"
    raw_value = _read(raw_file) if raw_file.is_file() else None
    raw_sha = digest(raw_value) if raw_value is not None else None
    performed = bool(isinstance(coverage, dict) and (
        coverage.get("editorial_rerun_performed") is True
        or coverage.get("editorial_completion_performed") is True
    ))

    for path in sorted(state_dir.glob(f"editorial-repair-{date}-*.json")):
        if path.name.endswith(".response.json"):
            continue
        journal = _read(path)
        if not isinstance(journal, dict):
            raise EditorialRepairError("repair journal is not an object")
        _verify(journal, "journal_sha256", "repair journal")
        state = str(journal.get("state") or "")
        if state == "applied":
            if merged_sha is not None and journal.get("research_sha256") != merged_sha:
                raise EditorialRepairError("applied repair does not match persisted Coverage research")
            continue
        if state != "response_saved":
            raise EditorialRepairError(f"publication blocked by repair state={state or 'missing'}")
        if not performed:
            raise EditorialRepairError("response saved but Coverage did not record repair completion")
        if merged_sha is None or journal.get("research_sha256") != merged_sha:
            raise EditorialRepairError("saved repair does not match persisted Coverage research")
        if raw_sha is None:
            raise EditorialRepairError("editorial-output-raw.json missing for repair reconciliation")
        ctx = Context(
            date=date, research=Path("."), research_sha=str(journal.get("research_sha256") or ""),
            model=str(journal.get("model") or ""), state_dir=state_dir, journal=path,
            response=state_dir / str(journal.get("response_file") or ""),
        )
        binding = str(journal.get("request_sha256") or "")
        if not binding:
            raise EditorialRepairError("saved repair has no request binding")
        response, saved_sha = _load_response(ctx, binding)
        if journal.get("response_sha256") != saved_sha:
            raise EditorialRepairError("repair response hash disagrees with journal")
        try:
            response_json = json.loads(str(response.get("output_text") or ""))
        except json.JSONDecodeError as exc:
            raise EditorialRepairError("saved repair output_text is invalid JSON") from exc
        if digest(response_json) != raw_sha:
            raise EditorialRepairError("saved repair response does not match editorial-output-raw.json")
        journal.update(state="applied", applied_at=_now(), updated_at=_now(), applied_editorial_sha256=raw_sha)
        _save_journal(ctx, journal)
