#!/usr/bin/env python3
"""Run generate_digest_preview with resilient editorial handling.

Fresh production research is collected by Primary Recall v2: twelve mandatory,
one-search discovery passes with deterministic budget allocation. Generated
research is staged below automation/fixtures/research/.runtime so the legacy
generator's caller-input guard stays intact. Internal runtime research may carry
a controlled healing overlap; only trusted ignored runtime artifacts can override
the legacy generator's canonical continuity start for sanitation/validation.
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
PRODUCTION_PREVIEW_ROOT = PREVIEW_ROOT / "production-daily"
TRUSTED_RUNTIME_RESEARCH_ROOT = (
    REPOSITORY_ROOT / "automation" / "fixtures" / "research" / ".runtime"
)
PRIMARY_RECALL_SEARCH_CALLS = 12

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


def without_option(argv: list[str], name: str) -> list[str]:
    result: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == name:
            index += 2
            continue
        result.append(argv[index])
        index += 1
    return result


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _trusted_runtime_research_path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    candidate = (REPOSITORY_ROOT / value).resolve()
    runtime_root = TRUSTED_RUNTIME_RESEARCH_ROOT.resolve()
    fixture_root = runtime_root.parent
    trusted = False
    try:
        candidate.relative_to(runtime_root)
        trusted = True
    except ValueError:
        # Coverage historically stages its transient rerun artifact directly
        # below automation/fixtures/research as a hidden .coverage-audit-*.json
        # file. It is workflow-generated and removed after the rerun, so accept
        # only that exact hidden-file shape; arbitrary caller fixtures remain
        # subject to the canonical archive continuity window.
        trusted = bool(
            candidate.parent == fixture_root
            and candidate.name.startswith(".coverage-audit-")
            and candidate.suffix == ".json"
        )
    return candidate if trusted and candidate.is_file() else None


def patch_trusted_runtime_window(generator: Any, research_input: str | None) -> bool:
    """Use the saved effective window only for internally generated inputs.

    Caller-supplied fixtures keep the generator's historical strict continuity
    semantics. Trusted Primary/Hybrid ``.runtime`` inputs and the Coverage
    ``.coverage-audit-*.json`` handoff preserve both saved window boundaries so
    a retry cannot silently discard healing-overlap candidates.
    """
    path = _trusted_runtime_research_path(research_input)
    if path is None:
        return False
    payload = _read_json(path)
    window = payload.get("search_window") if isinstance(payload, dict) else None
    if not isinstance(window, dict):
        raise RuntimeError("trusted runtime research-input не содержит search_window")
    start_raw = window.get("start_at")
    end_raw = window.get("end_at")
    if not isinstance(start_raw, str) or not isinstance(end_raw, str):
        raise RuntimeError("trusted runtime search_window не содержит start_at/end_at")
    start_at = generator.parse_aware_datetime(start_raw, "runtime.search_window.start_at")
    end_at = generator.parse_aware_datetime(end_raw, "runtime.search_window.end_at")
    if start_at > end_at:
        raise RuntimeError("trusted runtime search_window имеет start_at > end_at")

    def expected_search_window(
        publication_date: Any,
        archive: dict[str, Any],
        config: dict[str, Any],
        *,
        cutoff_at: Any = None,
    ) -> tuple[Any, Any]:
        del publication_date, archive, config, cutoff_at
        return start_at, end_at

    generator.expected_search_window = expected_search_window
    return True


def normalize_completed_empty_research(output_dir: Path) -> bool:
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
    if not isinstance(response, dict) or response.get("response_status") != "completed":
        return False
    try:
        completed_searches = int(response.get("web_search_calls", 0) or 0)
    except (TypeError, ValueError):
        return False
    if completed_searches < 1:
        return False
    messages = " ".join(
        str(value or "")
        for value in (candidates.get("error_message"), research.get("error"), run_info.get("error"))
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
        "Primary recall v2 завершил все 12 Web Search без кандидатов; пустой "
        "пул передан hybrid completeness и обязательному coverage audit."
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
    return isinstance(candidates.get("candidates"), list)


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


def _primary_recall_model(forwarded: list[str]) -> str:
    return argv_value(forwarded, "--model") or os.getenv("OPENAI_TEXT_MODEL", "").strip() or "gpt-5.6-terra"


def _maximum_candidates(forwarded: list[str]) -> int:
    try:
        return int(argv_value(forwarded, "--maximum-candidates", "20") or 20)
    except ValueError:
        return 20


def _verify_trusted_source_freshness(
    *, forwarded: list[str], publication_date: str
) -> dict[str, Any] | None:
    """Verify source dates before any trusted runtime research reaches editorial.

    The same gate therefore covers fresh Primary research, Hybrid merged research
    and Coverage's hidden merged handoff without adding a paid model call.
    Caller-supplied fixtures remain offline and unchanged.
    """
    research_path = _trusted_runtime_research_path(research_input_from_argv(forwarded))
    if research_path is None:
        return None
    from source_freshness import verify_research_file

    report_path = PRODUCTION_PREVIEW_ROOT / f"source-freshness-{publication_date}.json"
    run = verify_research_file(
        research_path,
        publication_date=publication_date,
        report_path=report_path,
    )
    print(
        "Source Freshness Proof v1 completed: "
        f"stage={run.get('stage')}, eligible {run.get('eligible_before')} -> "
        f"{run.get('eligible_after')}; paid API calls=0."
    )
    return run


def _run_fresh_primary_recall(
    *, forwarded: list[str], publication_date: str
) -> tuple[list[str], dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY отсутствует для fresh primary recall v2")
    from primary_recall_search import run_primary_recall_search

    research_path, report = run_primary_recall_search(
        publication_date=publication_date,
        api_key=api_key,
        model=_primary_recall_model(forwarded),
        maximum_candidates=_maximum_candidates(forwarded),
    )
    try:
        relative_research = research_path.resolve().relative_to(REPOSITORY_ROOT)
    except ValueError as exc:
        raise RuntimeError("primary recall research path escaped repository root") from exc
    injected = [*without_option(forwarded, "--research-input"), "--research-input", str(relative_research)]
    return injected, report


def _mark_primary_recall_artifact(
    *, output_dir: Path, publication_date: str, report: dict[str, Any]
) -> None:
    report_path = PRODUCTION_PREVIEW_ROOT / f"primary-recall-{publication_date}.json"
    if report_path.is_file():
        shutil.copy2(report_path, output_dir / "primary-recall.json")
    else:
        _write_json(output_dir / "primary-recall.json", report)
    run_info_path = output_dir / "run-info.json"
    run_info = _read_json(run_info_path)
    if run_info is not None:
        research = run_info.get("research")
        if not isinstance(research, dict):
            research = {}
            run_info["research"] = research
        directions = [item for item in report.get("directions", []) if isinstance(item, dict)]
        call_items_total = sum(
            int((item.get("api") or {}).get("web_search_call_items_total", 0) or 0)
            for item in directions
            if isinstance(item.get("api"), dict)
        )
        navigation_items_total = sum(
            int((item.get("api") or {}).get("web_search_navigation_items_total", 0) or 0)
            for item in directions
            if isinstance(item.get("api"), dict)
        )
        research["mode"] = "primary_recall_v2"
        research["primary_recall_version"] = 2
        research["response"] = {
            "response_id": None,
            "response_status": "completed",
            "web_search_calls": PRIMARY_RECALL_SEARCH_CALLS,
            "web_search_call_items_total": call_items_total,
            "navigation_items_total": navigation_items_total,
            "actual_queries": [
                query
                for direction in directions
                for query in (
                    direction.get("api", {}).get("actual_queries", [])
                    if isinstance(direction.get("api"), dict) else []
                )
            ],
            "consulted_sources": [
                source
                for direction in directions
                for source in (
                    direction.get("api", {}).get("consulted_sources", [])
                    if isinstance(direction.get("api"), dict) else []
                )
            ],
        }
        _write_json(run_info_path, run_info)
    input_info_path = output_dir / "research-input-info.json"
    input_info = _read_json(input_info_path) or {}
    input_info["mode"] = "primary_recall_v2"
    input_info["primary_recall_version"] = 2
    input_info["completed_search_calls"] = PRIMARY_RECALL_SEARCH_CALLS
    input_info["trusted_runtime_input"] = True
    _write_json(input_info_path, input_info)


def _agency_rescue_survival_report(
    *, output_dir: Path, publication_date: str, hybrid_error: Exception
) -> dict[str, Any] | None:
    """Preserve a successfully discovered rescue event when Hybrid itself fails.

    The rescue already spent its single operation and persisted a trusted merged
    research path. Returning a synthetic Hybrid report lets the existing
    trusted-runtime Source Freshness Proof + editorial rerun path process that
    candidate. We never rerun Hybrid or the rescue here.
    """
    rescue = _read_json(output_dir / "agency-discovery-rescue.json")
    if not isinstance(rescue, dict) or int(rescue.get("added_count", 0) or 0) < 1:
        return None
    merged_path = rescue.get("merged_research_path")
    if not isinstance(merged_path, str) or _trusted_runtime_research_path(merged_path) is None:
        return None
    return {
        "version": 1,
        "status": "complete_with_gaps",
        "publication_date": publication_date,
        "strategy": "agency_rescue_survived_hybrid_failure",
        "agency_discovery_rescue": rescue,
        "accepted_candidates": list(rescue.get("accepted_candidates") or []),
        "editorial_rerun_needed": True,
        "merged_research_path": merged_path,
        "hybrid_error": f"{type(hybrid_error).__name__}: {hybrid_error}",
        "search_budget": {
            "maximum_calls": 4,
            "completed_calls": None,
            "status": "hybrid_failed_without_retry",
        },
        "pipeline_search_budget": {
            "primary_maximum": 12,
            "agency_discovery_rescue_maximum": 1,
            "hybrid_maximum": 4,
            "coverage_maximum": 7,
            "maximum_total": 24,
        },
    }


def _run_hybrid_completeness(
    *, forwarded: list[str], output_dir: Path, publication_date: str,
    fresh_primary_recall: bool = False,
) -> tuple[dict[str, Any] | None, bool]:
    if research_input_from_argv(forwarded) and not fresh_primary_recall:
        return None, False
    if not provisional_artifact_is_reusable(output_dir):
        return None, False
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("::warning title=Hybrid completeness skipped::OPENAI_API_KEY отсутствует; сохранён primary result.")
        return None, False
    model = _primary_recall_model(forwarded)
    maximum_candidates = _maximum_candidates(forwarded)
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
        report = _agency_rescue_survival_report(
            output_dir=output_dir,
            publication_date=publication_date,
            hybrid_error=exc,
        )
        if report is None:
            print(
                "::warning title=Hybrid completeness failed open::"
                f"{type(exc).__name__}: {exc}. Primary result сохранён без изменений."
            )
            return None, False
        print(
            "::warning title=Hybrid completeness failed after agency rescue::"
            f"{type(exc).__name__}: {exc}. Rescue candidate сохранён и будет "
            "передан штатному Source Freshness Proof/editorial rerun без второго search."
        )
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
    if _trusted_runtime_research_path(str(relative_merged)) is None:
        report["editorial_rerun_error"] = "merged research path is not trusted runtime ingress"
        persist_report(output_dir, report)
        return report, False
    snapshot = _snapshot_artifact(output_dir)
    clean_forwarded = without_option(forwarded, "--research-input")
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--allow-provisional-editorial",
        *clean_forwarded[1:],
        "--research-input",
        str(relative_merged),
    ]
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, env=os.environ.copy(), check=False)
    if completed.returncode != 0:
        _restore_artifact(output_dir, snapshot)
        merged_payload = _read_json(merged_path)
        coverage_handoff_preserved = bool(
            isinstance(merged_payload, dict)
            and isinstance(merged_payload.get("candidates"), list)
        )
        if coverage_handoff_preserved:
            _write_json(output_dir / "candidates.json", merged_payload)
        report["editorial_rerun_performed"] = False
        report["coverage_handoff_preserved"] = coverage_handoff_preserved
        report["editorial_rerun_error"] = (
            f"hybrid editorial rerun exited with code {completed.returncode}; "
            "primary editorial artifact restored, merged candidates preserved for coverage"
            if coverage_handoff_preserved
            else f"hybrid editorial rerun exited with code {completed.returncode}; primary artifact restored"
        )
        persist_report(output_dir, report)
        if coverage_handoff_preserved:
            print(
                "::warning title=Hybrid editorial rerun rolled back::"
                "Редакционный artifact восстановлен; валидный merged candidate pool "
                "сохранён в candidates.json для обязательного Coverage."
            )
        else:
            print(
                "::warning title=Hybrid editorial rerun rolled back::"
                "Primary artifact restored; merged handoff unavailable."
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

    publication_date = publication_date_from_argv(forwarded)
    caller_research_input = research_input_from_argv(forwarded)
    fresh_primary_recall = False
    primary_report: dict[str, Any] | None = None
    if publication_date and caller_research_input is None:
        try:
            forwarded, primary_report = _run_fresh_primary_recall(
                forwarded=forwarded, publication_date=publication_date
            )
            fresh_primary_recall = True
            print(
                "Primary recall v2 completed: 12 mandatory one-search passes; "
                f"final candidates={primary_report.get('final_candidate_count', 0)}."
            )
        except Exception as exc:
            print(
                "::error title=Primary recall v2 incomplete::"
                f"{type(exc).__name__}: {exc}. Fresh production research is fail-closed."
            )
            return 1

    if publication_date and _trusted_runtime_research_path(
        research_input_from_argv(forwarded)
    ) is not None:
        try:
            _verify_trusted_source_freshness(
                forwarded=forwarded,
                publication_date=publication_date,
            )
        except Exception as exc:
            print(
                "::error title=Source freshness verification failed::"
                f"{type(exc).__name__}: {exc}. Trusted production research is fail-closed."
            )
            return 1

    sys.argv = forwarded
    patch_editorial_policy()
    import generate_digest_preview

    patch_editorial_policy(generate_digest_preview)
    patch_editorial_source_validation(generate_digest_preview)
    internal_window = patch_trusted_runtime_window(
        generate_digest_preview,
        research_input_from_argv(forwarded),
    )
    if internal_window:
        print("Trusted runtime research window accepted for sanitation/editorial validation.")
    result = int(generate_digest_preview.main())

    output_dir = PREVIEW_ROOT / publication_date if publication_date else None
    if (
        fresh_primary_recall and publication_date and output_dir is not None
        and primary_report is not None and output_dir.is_dir()
    ):
        _mark_primary_recall_artifact(
            output_dir=output_dir,
            publication_date=publication_date,
            report=primary_report,
        )

    empty_research_normalized = False
    if result != 0 and allow_provisional and output_dir is not None:
        empty_research_normalized = normalize_completed_empty_research(output_dir)

    if publication_date and output_dir is not None and provisional_artifact_is_reusable(output_dir):
        _report, rerun_succeeded = _run_hybrid_completeness(
            forwarded=forwarded,
            output_dir=output_dir,
            publication_date=publication_date,
            fresh_primary_recall=fresh_primary_recall,
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
            "Primary recall v2 completed with zero candidates; continuing to "
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
