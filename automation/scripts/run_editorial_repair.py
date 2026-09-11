#!/usr/bin/env python3
"""Run Coverage editorial completion with durable at-most-once semantics.

The parent Coverage wrapper must create the durable obligation first. This child
accepts only saved research, patches the generator's existing usage observer at
runtime, disables SDK retries for the one protected editorial request, persists
the response before parsing, and marks the obligation validated only after the
normal generator finishes successfully.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from editorial_repair_guard import (
    EditorialRepairError,
    begin_request,
    clone_no_retry_callback,
    journal_state,
    load_required,
    mark_failed_before_request,
    mark_unknown_after_request,
    mark_validated,
    prepare_request,
    request_sha256,
    save_response,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _take_option(argv: list[str], name: str) -> tuple[list[str], str | None]:
    result: list[str] = [argv[0]]
    found: str | None = None
    index = 1
    while index < len(argv):
        value = argv[index]
        if value == name:
            if index + 1 >= len(argv):
                raise EditorialRepairError(f"{name} requires a value")
            found = argv[index + 1]
            index += 2
            continue
        prefix = name + "="
        if value.startswith(prefix):
            found = value[len(prefix):]
            index += 1
            continue
        result.append(value)
        index += 1
    return result, found


def _required_path(value: str | None, label: str) -> Path:
    if value is None or not value.strip():
        raise EditorialRepairError(f"missing {label}")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPOSITORY_ROOT / path).resolve()


def _argv_value(argv: list[str], name: str) -> str | None:
    for index, value in enumerate(argv):
        if value == name and index + 1 < len(argv):
            return argv[index + 1]
        prefix = name + "="
        if value.startswith(prefix):
            return value[len(prefix):]
    return None


def main() -> int:
    forwarded = list(sys.argv)
    forwarded, persisted_value = _take_option(
        forwarded, "--repair-persisted-research"
    )
    forwarded, state_value = _take_option(forwarded, "--repair-state-dir")
    forwarded, archive_value = _take_option(forwarded, "--repair-archive")
    forwarded, artifact_value = _take_option(forwarded, "--repair-artifact-dir")

    publication_date = (_argv_value(forwarded, "--publication-date") or "").strip()
    if not publication_date:
        raise EditorialRepairError("missing --publication-date")
    model = (_argv_value(forwarded, "--model") or "").strip()
    if not model:
        import os

        model = os.getenv("OPENAI_TEXT_MODEL", "").strip()
    state_dir = _required_path(state_value, "repair state dir")
    persisted_research = _required_path(
        persisted_value, "repair persisted research"
    )
    archive = _required_path(archive_value, "repair archive")
    artifact_dir = _required_path(artifact_value, "repair artifact dir")

    context = load_required(
        publication_date=publication_date,
        state_dir=state_dir,
        persisted_research_path=persisted_research,
        archive_path=archive,
        artifact_dir=artifact_dir,
        model=model,
    )

    try:
        import generate_digest_preview
        import run_digest_preview
    except BaseException as exc:
        mark_failed_before_request(context, type(exc).__name__)
        print(
            f"Editorial repair failed before provider request: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    original_call = generate_digest_preview.call_with_usage
    editorial_calls = 0

    def protected_call(
        stage: str,
        callback: Any,
        *,
        usage_model: str | None = None,
        usage_kind: str = "text",
        usage_identity: str | None = None,
        usage_metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        nonlocal editorial_calls
        if stage != "editorial":
            raise EditorialRepairError(
                f"protected editorial completion forbids paid stage={stage}"
            )
        editorial_calls += 1
        if editorial_calls > 1:
            raise EditorialRepairError(
                "protected editorial completion attempted more than one editorial transport"
            )
        binding = request_sha256(kwargs)
        replay = prepare_request(context, binding)
        if replay is not None:
            return replay
        try:
            strict_callback = clone_no_retry_callback(callback)
        except BaseException as exc:
            mark_failed_before_request(context, type(exc).__name__)
            raise
        begin_request(context, binding)
        try:
            response = original_call(
                stage,
                strict_callback,
                usage_model=usage_model,
                usage_kind=usage_kind,
                usage_identity=usage_identity,
                usage_metadata=usage_metadata,
                **kwargs,
            )
        except BaseException as exc:
            mark_unknown_after_request(context, type(exc).__name__)
            raise
        save_response(context, binding, response)
        return response

    generate_digest_preview.call_with_usage = protected_call
    sys.argv = forwarded
    try:
        result = int(run_digest_preview.main())
    except BaseException as exc:
        state = journal_state(state_dir, publication_date)
        if state in {"required", "prepared"}:
            mark_failed_before_request(context, type(exc).__name__)
        print(
            f"Editorial repair runner failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    if result != 0:
        state = journal_state(state_dir, publication_date)
        if state in {"required", "prepared"}:
            mark_failed_before_request(context, "generator_nonzero_before_request")
        return result

    try:
        mark_validated(context)
    except EditorialRepairError as exc:
        print(f"Editorial repair validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
