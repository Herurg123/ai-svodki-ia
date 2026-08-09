#!/usr/bin/env python3
"""Run generate_digest_preview with resilient editorial handling.

The underlying generator writes research and parsed editorial artifacts before
its final policy validation. This wrapper keeps completed paid research
reusable, adds a small independent hybrid completeness layer after fresh primary
research, lets mandatory coverage audit rescue a short/empty pool, and applies
deterministic runtime fixes before validation.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
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


def argv_value(argv: list[str], name: str, default: str | None = None) -> str | None:
    try:
        index = argv.index(name)
    except ValueError:
        return default
    if index + 1 >= len(argv):
        return default
    value = argv[index + 1].strip()
    return value or default


def research_input_from_argv(argv: list[str]) -> str | None:
    return argv_value(argv, "--research-input")


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
        "передан hybrid completeness и обязательному coverage audit."
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


def _snapshot_artifact(output_dir: Path) -> dict[Path, bytes]:
    if not output_dir.is_dir():
        return {}
    return {
        path.relative_to(output_dir): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }


def _restore_artifact(output_dir: Path, snapshot: dict[Path, bytes]) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative, content in snapshot.items():
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _run_hybrid_completeness(
    *,
    forwarded: list[str],
    output_dir: Path,
    publication_date: str,
) -> tuple[dict[str, Any] | None, bool]:
    """Run paid completeness only after a fresh primary research call.

    A --research-input invocation is an editorial rerun/recovery path and must
    never recursively pay for completeness again.
    """

    if research_input_from_argv(forwarded):
        return None, False
    if not provisional_artifact_is_reusable(output_dir):
        return None, False

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print(
            "::warning title=Hybrid completeness skipped::"
            "OPENAI_API_KEY отсутствует; сохранён baseline primary result."
        )
        return None, False

    model = (
        argv_value(forwarded, "--model")
        or os.getenv("OPENAI_TEXT_MODEL", "").strip()
        or "gpt-5.6-terra"
    )
    try:
        maximum_candidates = int(argv_value(forwarded, "--maximum-candidates", "20") or 20)
    except ValueError:
        maximum_candidates = 20

    from hybrid_search_completeness import persist_report, run_hybrid_completeness

    try:
        report = run_hybrid_completeness(
            artifact_dir=output_dir,
            archive_path=REPOSITORY_ROOT / "automation" / "archive" / "index.json",
            publication_date=publication_date,
            api_key=api_key,
            model=model,
            maximum_search_calls=4,
            maximum_candidates=maximum_candidates,
        )
    except Exception as exc:
        print(
            "::warning title=Hybrid completeness failed open::"
            f"{type(exc).__name__}: {exc}. Основной research сохранён без изменений."
        )
        return None, False

    merged_path_raw = report.get("merged_research_path")
    if not report.get("editorial_rerun_needed") or not isinstance(merged_path_raw, str):
        print(
            "Hybrid completeness completed with "
            f"{report.get('search_budget', {}).get('completed_calls', 0)} search operations; "
            "no additional candidate required editorial rerun."
        )
        persist_report(output_dir, report)
        return report, False

    merged_path = Path(merged_path_raw)
    try:
        relative_merged = merged_path.resolve().relative_to(REPOSITORY_ROOT)
    except ValueError:
        report["editorial_rerun_error"] = "merged research path escaped repository root"
        persist_report(output_dir, report)
        return report, False

    snapshot = _snapshot_artifact(output_dir)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--allow-provisional-editorial",
        *forwarded[1:],
        "--research-input",
        str(relative_merged),
    ]
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=os.environ.copy(),
        check=False,
    )
    if completed.returncode != 0:
        _restore_artifact(output_dir, snapshot)
        report["editorial_rerun_performed"] = False
        report["editorial_rerun_error"] = (
            f"hybrid editorial rerun exited with code {completed.returncode}; "
            "baseline primary artifact restored"
        )
        persist_report(output_dir, report)
        print(
            "::warning title=Hybrid editorial rerun rolled back::"
            "Новые кандидаты сохранены в диагностике, но baseline artifact восстановлен."
        )
        return report, False

    report["editorial_rerun_performed"] = True
    report["editorial_rerun_error"] = None
    persist_report(output_dir, report)
    print(
        "Hybrid completeness added "
        f"{len(report.get('accepted_candidates') or [])} candidate(s) after "
        f"{report.get('search_budget', {}).get('completed_calls', 0)} search operations."
    )
    return report, True


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

    publication_date = publication_date_from_argv(forwarded)
    output_dir = PREVIEW_ROOT / publication_date if publication_date else None
    empty_research_normalized = False
    if result != 0 and allow_provisional and output_dir is not None:
        empty_research_normalized = normalize_completed_empty_research(output_dir)

    if publication_date and output_dir is not None and provisional_artifact_is_reusable(output_dir):
        _report, rerun_succeeded = _run_hybrid_completeness(
            forwarded=forwarded,
            output_dir=output_dir,
            publication_date=publication_date,
        )
        if rerun_succeeded:
            result = 0

    if result == 0 or not allow_provisional:
        return result

    if not publication_date or output_dir is None:
        return result
    if not provisional_artifact_is_reusable(output_dir):
        return result

    if empty_research_normalized:
        print(
            "Primary research completed with zero candidates; continuing to "
            "hybrid completeness and the mandatory six-direction coverage audit."
        )
    else:
        print(
            "Initial editorial is provisional, but paid research is reusable; "
            "continuing to hybrid completeness / mandatory coverage completion "
            "and editorial repair."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
