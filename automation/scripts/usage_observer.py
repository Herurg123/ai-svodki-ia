"""Local, publication-neutral accounting around the existing paid transports.

Never retries, changes arguments, or stores prompts, credentials or response text.
The directory is opt-in so historical imports and offline callers remain inert.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def field(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def search_counts(response: Any) -> dict[str, int]:
    searches = navigation = incomplete = 0
    for item in field(response, "output", []) or []:
        if field(item, "type") != "web_search_call":
            continue
        action = field(field(item, "action", {}), "type")
        if action == "search":
            if field(item, "status") == "completed":
                searches += 1
            else:
                incomplete += 1
        elif action in {"open_page", "find_in_page"}:
            navigation += 1
    return {"search_operations": searches, "navigation_items": navigation,
            "incomplete_search_operations": incomplete}


def _save(path: Path, record: dict[str, Any]) -> None:
    """Accounting failure must not repeat or discard an already-paid response."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception as exc:
        # Do not include exception text: transports may put secrets in it.
        print(f"::warning title=Usage accounting::journal_write_failed ({type(exc).__name__})",
              file=sys.stderr)


def call_with_usage(
    stage: str, callback: Callable[..., Any], *, usage_model: str | None = None,
    usage_kind: str = "text", usage_identity: str | None = None,
    usage_metadata: dict[str, Any] | None = None, **kwargs: Any,
) -> Any:
    directory = os.environ.get("AI_DIGEST_USAGE_DIR")
    if not directory:
        return callback(**kwargs)
    attempt = uuid.uuid4().hex
    if usage_metadata is not None:
        usage_metadata["attempt_id"] = attempt
    path = Path(directory) / f"{attempt}.json"
    record = {
        "usage_event_version": 1, "attempt_id": attempt,
        "publication_date": os.environ.get("AI_DIGEST_PUBLICATION_DATE"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "stage": stage, "kind": usage_kind,
        "local_request_id": usage_identity,
        "model": usage_model or kwargs.get("model"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "state": "started", "usage": None,
    }
    _save(path, record)
    try:
        response = callback(**kwargs)
    except BaseException as exc:
        record.update(state="outcome_unknown", error_type=type(exc).__name__)
        _save(path, record)
        raise
    try:
        transport = field(response, "_transport", {}) or {}
        record.update(
            state="response_received", response_id=field(response, "id"),
            provider_request_id=field(transport, "openai_request_id"),
            response_status=field(response, "status"),
            model=field(response, "model") or record["model"],
            service_tier=field(response, "service_tier"),
            usage=plain(field(response, "usage")),
            finished_at=datetime.now(timezone.utc).isoformat(),
            **search_counts(response),
        )
        _save(path, record)
    except Exception as exc:
        print(f"::warning title=Usage accounting::response_metadata_failed ({type(exc).__name__})",
              file=sys.stderr)
    return response
