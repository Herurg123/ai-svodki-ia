#!/usr/bin/env python3
"""Run generate_digest_preview with resilient editorial handling.

The underlying generator writes research and parsed editorial artifacts before
its final policy validation.  This wrapper keeps completed paid research
reusable, lets mandatory coverage audit rescue an empty primary pool, and
applies deterministic runtime fixes before validation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PREVIEW_ROOT = REPOSITORY_ROOT / "automation" / "preview"

from editorial_policy_runtime import (
    actual_prohibited_agent_form,
    patch_editorial_policy,
    patch_editorial_source_validation,
)

EMPTY_RESEARCH_MARKERS = (
    "не найдено ни одного",
    "не осталось ни одного достойного",
    "не удалось подтвердить ни одного",
    "пул кандидатов пуст",
)


def publication_date_from_argv(argv: list[str]) -> str | None:
    try:
        index = argv.index("--publication-date")
    except ValueError:
        return None
    if index + 1 >= len(argv):
        return None
    value = argv[index + 1].strip()
    return value or None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_completed_empty_research(output_dir: Path) -> bool:
    """Convert a completed zero-candidate response into audit-ready research.

    Only the editorial outcome is relaxed. Transport failures, incomplete API
    responses, malformed artifacts and empty results without a completed Web
    Search remain hard failures.
    """

    run_info_path = output_dir / "run-info.json"
    candidates_path = output_dir / "candidates.json"
    run_info = _read_json(run_info_path)
    candidates = _read_json(candidates_path)
    if run_info is None or candidates is None:
        return False
    if candidates.get("candidates") != []:
        return False
    if not isinstance(candidates.get("coverage"), list):
        return False
    if not isinstance(candidates.get("search_window"), dict):
        return False

    research = run_info.get("research")
    if not isinstance(research, dict):
        return False
    response = research.get("response")
    if not isinstance(response, dict):
        return False
    if response.get("response_status") != "completed":
        return False
    try:
        completed_searches = int(response.get("web_search_calls", 0) or 0)
    except (TypeError, ValueError):
        return False
    if completed_searches < 1:
        return False

    messages = " ".join(
        str(value or "")
        for value in (
            candidates.get("error_message"),
            research.get("error"),
            run_info.get("error"),
        )
    ).casefold()
    if not any(marker in messages for marker in EMPTY_RESEARCH_MARKERS):
        return False

    candidates["status"] = "ok"
    candidates["error_message"] = None
    _write_json(candidates_path, candidates)

    research["status"] = "ok"
    research["error"] = None
    warnings = run_info.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        run_info["warnings"] = warnings
    warning = (
        "Основной research завершил Web Search без кандидатов; пустой пул "
        "передан обязательному coverage audit."
    )
    if warning not in warnings:
        warnings.append(warning)
    _write_json(run_info_path, run_info)
    return True


def provisional_artifact_is_reusable(output_dir: Path) -> bool:
    required = (
        output_dir / "run-info.json",
        output_dir / "candidates.json",
        output_dir / "research-output-raw.json",
    )
    if not all(path.is_file() for path in required):
        return False
    run_info = _read_json(output_dir / "run-info.json")
    candidates = _read_json(output_dir / "candidates.json")
    if run_info is None or candidates is None:
        return False
    research = run_info.get("research")
    if not isinstance(research, dict) or research.get("status") != "ok":
        return False
    if not isinstance(candidates.get("candidates"), list):
        return False
    # A parsed editorial response is useful but not mandatory. Research-only
    # recovery must remain possible after an editorial transport failure.
    return True


def main() -> int:
    allow_provisional = False
    forwarded: list[str] = [sys.argv[0]]
    for arg in sys.argv[1:]:
        if arg == "--allow-provisional-editorial":
            allow_provisional = True
        else:
            forwarded.append(arg)
    sys.argv = forwarded

    patch_editorial_policy()
    import generate_digest_preview

    patch_editorial_policy(generate_digest_preview)
    patch_editorial_source_validation(generate_digest_preview)
    result = int(generate_digest_preview.main())
    if result == 0 or not allow_provisional:
        return result

    publication_date = publication_date_from_argv(forwarded)
    if not publication_date:
        return result
    output_dir = PREVIEW_ROOT / publication_date
    empty_research_normalized = normalize_completed_empty_research(output_dir)
    if not provisional_artifact_is_reusable(output_dir):
        return result

    if empty_research_normalized:
        print(
            "Primary research completed with zero candidates; continuing to "
            "the mandatory six-direction coverage audit."
        )
    else:
        print(
            "Initial editorial is provisional, but paid research is reusable; "
            "continuing to mandatory coverage completion and editorial repair."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
