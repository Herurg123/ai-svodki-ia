#!/usr/bin/env python3
"""P3b v7 final-review remediation over the preserved reviewed v7 baseline.

``ensure_story_coverage_p3b_v7_base.py`` is the exact independently reviewed
52e110 baseline. This active layer changes only recovery correctness:

* genuine production P3b v1 positive candidate provenance is revocable alongside
  the later v2+ representation without broad title/string heuristics;
* an invalid/untrusted durable optional-slot journal is distinct from a missing
  journal and fails closed before complete/reusable shortcuts;
* a recovery-input-only pending marker can deterministically finalize after a
  crash that happened after sanitation mutations but before ``completed``.

No provider call, retry, page refetch, search-budget refund, query/routing change,
or durable optional-slot journal rewrite is introduced here.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from coverage_slot_guard import (
    CoverageSlotError,
    load_journal,
    load_raw_response,
    sha256_value,
)

_BASE_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v7_base.py")
_BASE_SPEC = importlib.util.spec_from_file_location(
    "ensure_story_coverage_p3b_v7_reviewed_base", _BASE_PATH
)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_base, _name)

# This is still P3b runtime v7. The preserved file split is forensic only, not a
# semantic or durable-contract version bump.
P3B_RUNTIME_VERSION = 7

_REMEDIATION_INTERNALS = {
    "_base",
    "_BASE_PATH",
    "_BASE_SPEC",
    "_REMEDIATION_INTERNALS",
    "_sync_p3b_public_hooks",
    "_candidate_is_stale_historical_p3b",
    "_without_stale_p3b_candidates",
    "_install_revocation_predicate",
    "_validate_optional_slot_journal",
    "_repair_recovery_input_only_marker",
    "recovery_preflight",
    "_load_stale_positive_snapshot",
    "execute_audit_plan",
    "main",
    "__getattr__",
}


def __getattr__(name: str) -> Any:
    return getattr(_base, name)


def _install_revocation_predicate() -> None:
    # v6 migration and v7 sanitation must use one predicate or the durable stale
    # snapshot can re-admit a row immediately after preflight removed it.
    _base._v6._without_stale_p3b_candidates = _without_stale_p3b_candidates


def _sync_p3b_public_hooks() -> None:
    """Push sanctioned compatibility seams into the reviewed base, then harden it."""
    for name, value in list(globals().items()):
        if name in _REMEDIATION_INTERNALS or (name.startswith("__") and name.endswith("__")):
            continue
        try:
            exists = hasattr(_base, name)
        except Exception:
            exists = False
        if exists:
            setattr(_base, name, value)
    _base._sync_p3b_public_hooks()
    _install_revocation_predicate()


def _candidate_is_stale_historical_p3b(item: Any, stale_signal_id: str) -> bool:
    """Match only production-reachable positive P3b provenance generations.

    Original P3b/v1 admission wrote direction + exact signal ids + binding
    version=1, but predated authoritative-page proof fields. v2 and every later
    preserved generation kept the same direction/signal provenance while writing
    the hardened binding version and authoritative-page proof marker. Nothing
    else is inferred from title, URL, source type, or generic P3b-looking fields.
    """
    if not isinstance(item, dict) or not stale_signal_id:
        return False
    if item.get("audit_direction") != "weak_source_exact_binding":
        return False
    signal_ids = {
        str(value or "").strip()
        for value in item.get("resolution_signal_ids") or []
        if str(value or "").strip()
    }
    if stale_signal_id not in signal_ids:
        return False
    try:
        binding_version = int(item.get("p3b_exact_binding_version", 0) or 0)
    except (TypeError, ValueError):
        return False

    # Preserved original production admission shape. Requiring both late proof
    # fields to be absent/empty prevents a loose "version 1-ish" heuristic.
    if binding_version == 1:
        return bool(
            not str(item.get("p3b_authoritative_page_url") or "").strip()
            and not str(item.get("p3b_authoritative_page_proof") or "").strip()
        )

    # v2..v5 historical positives and current-shape stale positives carry the
    # authoritative-page proof marker. Current evidence-v6 is filtered earlier
    # by the processed-snapshot evidence version and is therefore not revoked.
    return bool(
        binding_version == P3B_EXACT_BINDING_VERSION
        and str(item.get("p3b_authoritative_page_proof") or "").strip()
    )


def _without_stale_p3b_candidates(
    plan: dict[str, Any], signal: dict[str, Any] | None,
) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    candidates = result.get("candidates")
    if not isinstance(candidates, list):
        return result
    stale_signal_id = str((signal or {}).get("signal_id") or "").strip()
    if not stale_signal_id:
        return result
    result["candidates"] = [
        item
        for item in candidates
        if not _candidate_is_stale_historical_p3b(item, stale_signal_id)
    ]
    return result


_install_revocation_predicate()


def _load_stale_positive_snapshot(
    state_dir: Path, publication_date: str
) -> dict[str, Any] | None:
    """Strict equivalent of the reviewed loader: invalid journal is not absence."""
    journal = load_journal(Path(state_dir), publication_date)
    if not isinstance(journal, dict) or str(journal.get("state") or "") != "processed":
        return None
    saved = journal.get("processed_snapshot")
    if not isinstance(saved, dict):
        return None
    diagnostic = saved.get(_base._v6._v2._P3B_DIAGNOSTIC_KEY)
    if not isinstance(diagnostic, dict):
        return copy.deepcopy(saved) if saved.get("candidates") else None
    positive = (
        diagnostic.get("status") == "bound_candidate"
        or diagnostic.get("disposition") == "positive_exact_binding"
        or int(diagnostic.get("candidate_count", 0) or 0) > 0
        or any(
            isinstance(item, dict)
            and item.get("audit_direction") == "weak_source_exact_binding"
            for item in saved.get("candidates") or []
        )
    )
    if not positive:
        return None
    if int(diagnostic.get("binder_evidence_version", 0) or 0) == P3B_BINDER_EVIDENCE_VERSION:
        return None
    return copy.deepcopy(saved)


def _validate_optional_slot_journal(
    *,
    publication_date: str,
    artifact_dir: Path,
    state_dir: Path,
) -> dict[str, Any] | None:
    """Validate durable state needed before any complete/reusable shortcut.

    Missing is a normal state. Existing but malformed, structurally incompatible,
    response-corrupt, or inconsistent with the current artifact's durable
    search-window/bundle identity is untrusted and therefore raises fail-closed.
    The journal and saved response remain byte-for-byte untouched.
    """
    journal = load_journal(state_dir, publication_date)
    if journal is None:
        return None

    state = str(journal.get("state") or "")
    if state not in {"reserved", "request_started", "response_saved", "processed"}:
        raise CoverageSlotError(
            f"Coverage optional-slot journal has invalid state for recovery: {state!r}"
        )

    identity_keys = (
        "owner",
        "search_window_sha256",
        "request_contract_sha256",
        "bundle_identity_sha256",
    )
    for key in identity_keys:
        if not str(journal.get(key) or "").strip():
            raise CoverageSlotError(
                f"Coverage optional-slot journal is missing durable identity field: {key}"
            )

    request_contract = journal.get("request_contract")
    if not isinstance(request_contract, dict):
        raise CoverageSlotError("Coverage optional-slot journal request contract is missing")
    if str(request_contract.get("owner") or "") != str(journal.get("owner") or ""):
        raise CoverageSlotError("Coverage optional-slot request owner identity mismatch")
    if str(request_contract.get("request_contract_sha256") or "") != str(
        journal.get("request_contract_sha256") or ""
    ):
        raise CoverageSlotError("Coverage optional-slot request hash identity mismatch")

    if state in {"request_started", "response_saved", "processed"}:
        if journal.get("slot_consumed_or_ambiguous") is not True:
            raise CoverageSlotError(
                "Coverage optional-slot consumed state lost its durable consumption marker"
            )
        if journal.get("wire_attempt_admitted") is not True:
            raise CoverageSlotError(
                "Coverage optional-slot consumed state lost its wire-attempt marker"
            )
    if state in {"response_saved", "processed"}:
        # Validates saved-response existence, bytes hash and JSON decoding. No
        # provider replay or page fetch occurs.
        load_raw_response(state_dir, publication_date)

    candidates_path = Path(artifact_dir) / "candidates.json"
    if candidates_path.is_file():
        try:
            research = _base._read_json(candidates_path)
        except Exception as exc:
            raise CoverageSlotError(
                f"current Coverage research is unreadable during durable identity validation: {exc}"
            ) from exc
        if not isinstance(research, dict):
            raise CoverageSlotError("current Coverage research must be an object")
        search_window = research.get("search_window")
        if isinstance(search_window, dict):
            expected = sha256_value(search_window)
            if str(journal.get("search_window_sha256") or "") != expected:
                raise CoverageSlotError("Coverage optional-slot search-window identity mismatch")
        try:
            bundle_identity = _base._v6._P3A._bundle_identity(research)
        except Exception as exc:
            raise CoverageSlotError(
                f"current Coverage bundle identity is not provable: {exc}"
            ) from exc
        expected_bundle = sha256_value(bundle_identity)
        if str(journal.get("bundle_identity_sha256") or "") != expected_bundle:
            raise CoverageSlotError("Coverage optional-slot bundle identity mismatch")

    return journal


def _repair_recovery_input_only_marker(
    *,
    marker_path: Path,
    marker: dict[str, Any] | None,
    report_path: Path,
    persisted_research_path: Path,
) -> None:
    """Finalize a benign pending marker only after clean inputs are re-proven."""
    if not isinstance(marker, dict):
        return
    if marker.get("state") != "pending":
        return
    if marker.get("publication_snapshot_invalidated") is not False:
        return
    signal_id = str(marker.get("stale_signal_id") or "").strip()
    if not signal_id:
        raise CoverageSlotError(
            "non-invalidating pending P3b recovery marker has no stale signal identity"
        )
    signal = {"signal_id": signal_id}

    for path, original_key, clean_key in (
        (
            persisted_research_path,
            "original_persisted_research_sha256",
            "clean_persisted_research_sha256",
        ),
        (report_path, "original_report_sha256", "clean_report_sha256"),
    ):
        if marker.get(original_key) and not path.is_file():
            raise CoverageSlotError(
                f"pending P3b sanitation cannot prove completion because {path.name} disappeared"
            )
        if not path.is_file():
            continue
        try:
            value = _base._read_json(path)
        except Exception as exc:
            raise CoverageSlotError(
                f"pending P3b sanitation cannot re-read {path.name}: {exc}"
            ) from exc
        _cleaned, removed = _base._sanitize_candidate_containers(value, signal)
        if removed:
            return
        marker[clean_key] = _base._sha256_bytes(path.read_bytes())

    marker["state"] = "completed"
    marker["reason"] = "stale_positive_p3b_recovery_inputs_sanitized"
    marker["postflight_errors"] = []
    _base._atomic_write_json(marker_path, marker)


def recovery_preflight(
    *,
    publication_date: str,
    artifact_dir: Path,
    report_path: Path,
    state_dir: Path | None = None,
) -> dict[str, Any] | None:
    _sync_p3b_public_hooks()
    state_dir = Path(state_dir if state_dir is not None else STATE_DIR)
    artifact_dir = Path(artifact_dir)
    report_path = Path(report_path)

    _validate_optional_slot_journal(
        publication_date=publication_date,
        artifact_dir=artifact_dir,
        state_dir=state_dir,
    )

    # The reviewed base still owns the mutation ordering/backups/quarantine. Our
    # installed predicate makes both base preflight and v6 child migration use the
    # same historical-generation revocation semantics.
    context = _base.recovery_preflight(
        publication_date=publication_date,
        artifact_dir=artifact_dir,
        report_path=report_path,
        state_dir=state_dir,
    )

    if context is None:
        marker_path = _base._revocation_marker_path(state_dir, publication_date)
        marker = _base._load_marker(marker_path)
        _repair_recovery_input_only_marker(
            marker_path=marker_path,
            marker=marker,
            report_path=report_path,
            persisted_research_path=_base._persisted_research_path(
                state_dir, publication_date
            ),
        )
    return context


def execute_audit_plan(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    return _base.execute_audit_plan(*args, **kwargs)


def main() -> int:
    _sync_p3b_public_hooks()
    publication_date = str(_base._cli_arg("--publication-date") or "").strip()
    artifact_raw = _base._cli_arg("--artifact-dir")
    report_raw = _base._cli_arg("--report")
    if not publication_date or not artifact_raw or not report_raw:
        return int(_base._v6.main())

    artifact_dir = Path(artifact_raw)
    report_path = Path(report_raw)
    context = recovery_preflight(
        publication_date=publication_date,
        artifact_dir=artifact_dir,
        report_path=report_path,
        state_dir=Path(STATE_DIR),
    )
    child_code = int(_base._v6.main())
    return int(
        _base._postflight(
            context,
            child_code=child_code,
            artifact_dir=artifact_dir,
            report_path=report_path,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
