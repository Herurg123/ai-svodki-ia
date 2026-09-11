#!/usr/bin/env python3
"""P0 editorial-repair boundary over the established Coverage entrypoint.

The pre-P0 public implementation is retained verbatim in
``ensure_story_coverage_pre_p0.py`` so existing Retrieval Quality behavior,
monkeypatch hooks and search budgets remain unchanged. This wrapper replaces
only Coverage's saved-research editorial rerun with a durable at-most-once
completion path and converts a failed required completion into a non-zero result.

Compatibility seam removal target: after 2026-10-03, once saved-artifact recovery
and public import hooks have been proven against a consolidated implementation.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from editorial_repair_guard import (
    EditorialRepairError,
    journal_state,
    prepare_required,
    publication_safe,
    summary as repair_summary,
)

_PRE_PATH = Path(__file__).with_name("ensure_story_coverage_pre_p0.py")
_PRE_SPEC = importlib.util.spec_from_file_location(
    "ensure_story_coverage_pre_p0", _PRE_PATH
)
assert _PRE_SPEC and _PRE_SPEC.loader
_pre = importlib.util.module_from_spec(_PRE_SPEC)
sys.modules[_PRE_SPEC.name] = _pre
_PRE_SPEC.loader.exec_module(_pre)

for _name in dir(_pre):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_pre, _name)


def __getattr__(name: str) -> Any:
    return getattr(_pre, name)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPOSITORY_ROOT / "automation" / "preview" / "production-daily"
ARCHIVE_PATH = REPOSITORY_ROOT / "automation" / "archive" / "index.json"
REPAIR_RUNNER = Path(__file__).with_name("run_editorial_repair.py")
_PRE_RERUN = _pre.rerun_editorial
_ATTEMPTED_THIS_PROCESS = False


def _arg(name: str, default: str | None = None) -> str | None:
    for index, value in enumerate(sys.argv):
        if value == name and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        prefix = name + "="
        if value.startswith(prefix):
            return value[len(prefix):]
    return default


def _int_arg(name: str, default: int) -> int:
    try:
        return int(_arg(name, str(default)) or default)
    except ValueError:
        return default


def _report_path() -> Path | None:
    value = _arg("--report")
    if not value:
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPOSITORY_ROOT / path).resolve()


def _read_report(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_report(path: Path | None, value: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _coverage_runtime_research(publication_date: str) -> Path:
    return (
        REPOSITORY_ROOT
        / "automation"
        / "fixtures"
        / "research"
        / f".coverage-audit-{publication_date}.json"
    )


def _persisted_research(publication_date: str) -> Path:
    return STATE_DIR / f"coverage-audit-merged-candidates-{publication_date}.json"


def _artifact_dir(publication_date: str) -> Path:
    return REPOSITORY_ROOT / "automation" / "preview" / publication_date


def _model() -> str:
    return os.getenv("OPENAI_TEXT_MODEL", "").strip() or "gpt-5.6-terra"


def _is_coverage_research(path: Path, publication_date: str) -> bool:
    return path.name == f".coverage-audit-{publication_date}.json"


def _ensure_runtime_copy(publication_date: str) -> Path:
    persisted = _persisted_research(publication_date)
    if not persisted.is_file():
        raise EditorialRepairError(
            f"persisted Coverage research missing: {persisted}"
        )
    runtime = _coverage_runtime_research(publication_date)
    runtime.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(persisted, runtime)
    return runtime


def rerun_editorial(
    *,
    publication_date: str,
    merged_research_path: Path,
    minimum_total: int,
    maximum_candidates: int,
    maximum_selected_stories: int,
) -> None:
    """Use durable completion only for Mandatory Coverage saved research."""
    global _ATTEMPTED_THIS_PROCESS
    merged_research_path = Path(merged_research_path)
    if not _is_coverage_research(merged_research_path, publication_date):
        return _PRE_RERUN(
            publication_date=publication_date,
            merged_research_path=merged_research_path,
            minimum_total=minimum_total,
            maximum_candidates=maximum_candidates,
            maximum_selected_stories=maximum_selected_stories,
        )

    persisted = _persisted_research(publication_date)
    if not persisted.is_file():
        raise EditorialRepairError(
            "Coverage wrote runtime research but durable merged research is missing"
        )
    legacy_report = STATE_DIR / "coverage-audit.json"
    prepare_required(
        publication_date=publication_date,
        state_dir=STATE_DIR,
        persisted_research_path=persisted,
        archive_path=ARCHIVE_PATH,
        artifact_dir=_artifact_dir(publication_date),
        model=_model(),
        legacy_report_path=legacy_report,
    )
    _ATTEMPTED_THIS_PROCESS = True

    command = [
        sys.executable,
        str(REPAIR_RUNNER),
        "--publication-date",
        publication_date,
        "--minimum-candidates",
        str(minimum_total),
        "--maximum-candidates",
        str(maximum_candidates),
        "--minimum-selected-stories",
        str(minimum_total),
        "--maximum-selected-stories",
        str(maximum_selected_stories),
        "--research-input",
        str(merged_research_path.resolve().relative_to(REPOSITORY_ROOT)),
        "--repair-persisted-research",
        str(persisted.resolve().relative_to(REPOSITORY_ROOT)),
        "--repair-state-dir",
        str(STATE_DIR.resolve().relative_to(REPOSITORY_ROOT)),
        "--repair-archive",
        str(ARCHIVE_PATH.resolve().relative_to(REPOSITORY_ROOT)),
        "--repair-artifact-dir",
        str(_artifact_dir(publication_date).resolve().relative_to(REPOSITORY_ROOT)),
    ]
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode, command, output=completed.stdout
        )


def _completed_audit_evidence(report: dict[str, Any]) -> bool:
    required = set(getattr(_pre, "AUDIT_DIRECTION_IDS", ()))
    checked = set(report.get("checked_directions") or ())
    api = report.get("api") or {}
    return bool(
        report.get("audit_status") in {"complete", "complete_with_gaps"}
        and required
        and checked == required
        and isinstance(api, dict)
        and api.get("status") == "completed"
        and report.get("web_search_performed") is True
    )


def _record_guard_error(path: Path | None, error: BaseException) -> None:
    report = _read_report(path) or {}
    report["status"] = "error"
    report["mode"] = "editorial_repair_blocked"
    report["editorial_repair_guard"] = {
        "status": "error",
        "error_type": type(error).__name__,
        "error": str(error),
    }
    _write_report(path, report)


def _resume_pending(publication_date: str) -> None:
    runtime = _ensure_runtime_copy(publication_date)
    rerun_editorial(
        publication_date=publication_date,
        merged_research_path=runtime,
        minimum_total=_int_arg("--usual-total", 7),
        maximum_candidates=_int_arg("--maximum-candidates", 20),
        maximum_selected_stories=_int_arg("--maximum-selected-stories", 12),
    )


def _finalize_report(path: Path | None, publication_date: str) -> None:
    report = _read_report(path)
    if report is None:
        return
    if _completed_audit_evidence(report):
        report["audit_state"] = "completed_usable"
    state = journal_state(STATE_DIR, publication_date)
    if state is not None:
        report["editorial_repair_guard"] = repair_summary(
            STATE_DIR, publication_date
        )
        if state == "validated":
            report["editorial_rerun_required"] = True
            report["editorial_rerun_performed"] = True
            if report.get("editorial_completion_required") is True:
                report["editorial_completion_performed"] = True
            if report.get("mode") in {
                "existing_digest_after_editorial_repair_error",
                "existing_digest_after_empty_editorial_rerun",
                "existing_short_digest_after_reused_audit",
                "existing_short_digest_after_best_effort_audit",
                "existing_short_digest",
            }:
                report["mode"] = "recovered_pending_editorial_repair"
            report["status"] = "ok"
    _write_report(path, report)


def _sync_p0() -> None:
    _pre.rerun_editorial = rerun_editorial
    if hasattr(_pre, "_v8"):
        _pre._v8.rerun_editorial = rerun_editorial
    if hasattr(_pre, "_sync_direct_hooks"):
        _pre._sync_direct_hooks()


def main() -> int:
    global _ATTEMPTED_THIS_PROCESS
    _ATTEMPTED_THIS_PROCESS = False
    _sync_p0()
    publication_date = (_arg("--publication-date") or "").strip()
    report_path = _report_path()
    result = int(_pre.main())
    if result != 0 or not publication_date:
        return result

    state = journal_state(STATE_DIR, publication_date)
    if state is not None and state != "validated":
        if _ATTEMPTED_THIS_PROCESS:
            error = EditorialRepairError(
                f"required editorial completion remains state={state}"
            )
            _record_guard_error(report_path, error)
            print(f"Coverage editorial repair blocked publication: {error}", file=sys.stderr)
            return 1
        try:
            _resume_pending(publication_date)
        except BaseException as exc:
            _record_guard_error(report_path, exc)
            print(
                f"Coverage pending editorial repair could not resume: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 1

    _finalize_report(report_path, publication_date)
    try:
        publication_safe(_artifact_dir(publication_date), state_dir=STATE_DIR)
    except EditorialRepairError as exc:
        _record_guard_error(report_path, exc)
        print(f"Coverage editorial repair blocked publication: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
