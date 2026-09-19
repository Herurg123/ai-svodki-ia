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
import sys
from pathlib import Path
from typing import Any

from coverage_slot_guard import (
    CoverageSlotError,
    load_journal,
    load_raw_response,
    sha256_value,
    validated_processed_snapshot,
    validated_result_snapshot,
)
from coverage_slot_transport import replay_raw_response

_BASE_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v7_base.py")
_BASE_SPEC = importlib.util.spec_from_file_location(
    "ensure_story_coverage_p3b_v7_reviewed_base", _BASE_PATH
)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

# Preserve wrapper-owned loader bindings. The reviewed baseline itself re-exports
# historical private names (including ``_base``), and copying that binding would
# make the remediation layer accidentally call into a much older runtime module.
_WRAPPER_LOADER_NAMES = {"_base", "_BASE_PATH", "_BASE_SPEC", "_WRAPPER_LOADER_NAMES"}
for _name, _value in list(vars(_base).items()):
    if _name in _WRAPPER_LOADER_NAMES:
        continue
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = _value

# This is still P3b runtime v7. The preserved file split is forensic only, not a
# semantic or durable-contract version bump.
P3B_RUNTIME_VERSION = 7

_REMEDIATION_INTERNALS = {
    "_base",
    "_BASE_PATH",
    "_BASE_SPEC",
    "_WRAPPER_LOADER_NAMES",
    "_REMEDIATION_INTERNALS",
    "_sync_p3b_public_hooks",
    "_candidate_is_stale_historical_p3b",
    "_without_stale_p3b_candidates",
    "_install_revocation_predicate",
    "_positive_snapshot",
    "_validate_current_p3b_request_identity",
    "_validate_saved_result_against_raw",
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
    # snapshot can re-admit a row immediately after preflight removed it. Install
    # it on the reviewed base as well: its nested compatibility sync mirrors that
    # global into v6 immediately before child execution.
    _base._without_stale_p3b_candidates = _without_stale_p3b_candidates
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


def _positive_snapshot(journal: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    saved = journal.get("processed_snapshot")
    if not isinstance(saved, dict):
        return None, None
    diagnostic = saved.get(_base._v6._v2._P3B_DIAGNOSTIC_KEY)
    if not isinstance(diagnostic, dict):
        return (saved, None) if saved.get("candidates") else (None, None)
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
    return (saved, diagnostic) if positive else (None, diagnostic)


def _load_stale_positive_snapshot(
    state_dir: Path, publication_date: str
) -> dict[str, Any] | None:
    """Strict equivalent of the reviewed loader: invalid journal is not absence."""
    journal = load_journal(Path(state_dir), publication_date)
    if not isinstance(journal, dict) or str(journal.get("state") or "") != "processed":
        return None
    saved, diagnostic = _positive_snapshot(journal)
    if not isinstance(saved, dict):
        return None
    if not isinstance(diagnostic, dict):
        return copy.deepcopy(saved)
    if int(diagnostic.get("binder_evidence_version", 0) or 0) == P3B_BINDER_EVIDENCE_VERSION:
        # Current semantic evidence is reusable only when the durable writer
        # also proves the exact processed bytes against this request/response.
        # Pre-lineage current snapshots are quarantined like stale positives:
        # the spent slot is not refunded and no provider/page I/O is reopened.
        if validated_processed_snapshot(journal) is not None:
            return None
        return copy.deepcopy(saved)
    return copy.deepcopy(saved)


def _validate_current_p3b_request_identity(
    *,
    journal: dict[str, Any],
    publication_date: str,
    search_window: dict[str, Any] | None,
) -> None:
    """Recompute current reusable P3b request identity when CLI inputs are present.

    Stale evidence-v1..v5 is revoked rather than replayed, so current model/request
    drift is not used to block its deterministic sanitation. For a current
    evidence-v6 positive, however, complete/reusable recovery may rely on the
    saved proof; model/query/prompt/signal identity must therefore still match.
    """
    if str(journal.get("state") or "") != "processed":
        return
    saved, diagnostic = _positive_snapshot(journal)
    if not isinstance(saved, dict) or not isinstance(diagnostic, dict):
        return
    if int(diagnostic.get("binder_evidence_version", 0) or 0) != P3B_BINDER_EVIDENCE_VERSION:
        return
    if str(journal.get("owner") or "") != str(P3B_SLOT_OWNER):
        return

    model = str(_base._cli_arg("--model") or "").strip()
    archive_raw = _base._cli_arg("--archive")
    # Direct helper/unit callers may not have a CLI. Production main always does.
    if not model and not archive_raw:
        return
    if not model or not archive_raw:
        raise CoverageSlotError(
            "current P3b durable request identity cannot be proven without model and archive"
        )
    if not isinstance(search_window, dict):
        raise CoverageSlotError(
            "current P3b durable request identity cannot be proven without search window"
        )

    archive_path = Path(archive_raw)
    try:
        archive = _base._read_json(archive_path)
    except Exception as exc:
        raise CoverageSlotError(
            f"current P3b archive identity is unreadable: {exc}"
        ) from exc
    if not isinstance(archive, dict):
        raise CoverageSlotError("current P3b archive identity must be an object")

    try:
        active_signal = _base._v6.select_p3b_signal(
            _base._v6._p3b_signals(publication_date)
        )
    except Exception as exc:
        raise CoverageSlotError(
            f"current P3b signal identity cannot be reconstructed: {exc}"
        ) from exc
    if not isinstance(active_signal, dict):
        raise CoverageSlotError("current P3b signal identity is no longer provable")
    saved_signal = str(diagnostic.get("signal_id") or "").strip()
    active_signal_id = str(active_signal.get("signal_id") or "").strip()
    if not saved_signal or saved_signal != active_signal_id:
        raise CoverageSlotError("current P3b signal identity drift")

    try:
        query = _base._v6.build_p3b_query(active_signal)
        prompt = _base._v6.build_p3b_prompt(
            search_window=search_window,
            signal=active_signal,
            archive=_base._v6._runtime._compact_recent_archive(archive),
        )
        contract = _base._v6._v2._request_contract_v2(
            model=model,
            query=query,
            prompt=prompt,
            signal=active_signal,
        )
        expected_hash = sha256_value(contract)
    except Exception as exc:
        raise CoverageSlotError(
            f"current P3b request identity cannot be reconstructed: {exc}"
        ) from exc
    if str(journal.get("request_contract_sha256") or "") != expected_hash:
        raise CoverageSlotError("current P3b request/model identity drift")


def _validate_saved_result_against_raw(
    *,
    journal: dict[str, Any],
    publication_date: str,
    state_dir: Path,
) -> None:
    """Prove a saved parsed snapshot is exactly reproducible from durable raw bytes."""
    if str(journal.get("state") or "") not in {"response_saved", "processed"}:
        return
    saved = journal.get("result_snapshot")
    if not isinstance(saved, dict):
        return
    raw_response = load_raw_response(state_dir, publication_date)
    try:
        _result, replayed_snapshot = replay_raw_response(
            _base._v6._runtime,
            raw_response,
            maximum_web_search_calls=1,
        )
    except BaseException as exc:
        raise CoverageSlotError(
            "Coverage optional-slot saved raw response cannot be deterministically "
            f"replayed: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(replayed_snapshot, dict):
        raise CoverageSlotError(
            "Coverage optional-slot raw replay did not produce a parsed snapshot"
        )
    if sha256_value(replayed_snapshot) != sha256_value(saved):
        raise CoverageSlotError(
            "Coverage optional-slot saved result snapshot does not match deterministic raw replay"
        )


def _validate_optional_slot_journal(
    *,
    publication_date: str,
    artifact_dir: Path,
    state_dir: Path,
) -> dict[str, Any] | None:
    """Validate durable state before complete/reusable shortcuts.

    Reservation identity belongs to the pre-optional Coverage plan and is not
    reconstructed from post-editorial candidates.json or the post-request
    processed plan. New result/processed lineage is instead authenticated by
    hashes written by the durable slot writer and chained to the exact request
    contract plus saved raw response. Historical journals without those lineage
    fields remain readable for fail-closed migration, but are not thereby proven
    reusable by the active P3a/P3b runtime.
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
        # Response bytes remain the transport authority. Validate their hash and,
        # when a parsed snapshot exists, prove current deterministic parsing
        # reproduces those exact saved bytes without provider/network I/O.
        load_raw_response(state_dir, publication_date)
        _validate_saved_result_against_raw(
            journal=journal,
            publication_date=publication_date,
            state_dir=state_dir,
        )
        validated_result_snapshot(journal)

    if state == "processed":
        processed = journal.get("processed_snapshot")
        if not isinstance(processed, dict):
            raise CoverageSlotError(
                "processed Coverage optional-slot journal is missing its deterministic processed snapshot"
            )
        if not isinstance(processed.get("candidates"), list):
            raise CoverageSlotError(
                "processed Coverage optional-slot snapshot has invalid candidates"
            )
        budget = processed.get("search_budget")
        if not isinstance(budget, dict) or not all(
            key in budget for key in ("maximum_calls", "completed_calls", "remaining_calls")
        ):
            raise CoverageSlotError(
                "processed Coverage optional-slot snapshot has invalid search budget"
            )
        # If current lineage is declared, verify it exactly. A historical journal
        # with no lineage returns None here and is handled fail-closed by the
        # runtime rather than being promoted to a current reusable snapshot.
        validated_processed_snapshot(journal)

    search_window: dict[str, Any] | None = None
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
        candidate_window = research.get("search_window")
        if isinstance(candidate_window, dict):
            search_window = candidate_window
            expected = sha256_value(candidate_window)
            if str(journal.get("search_window_sha256") or "") != expected:
                raise CoverageSlotError("Coverage optional-slot search-window identity mismatch")

    _validate_current_p3b_request_identity(
        journal=journal,
        publication_date=publication_date,
        search_window=search_window,
    )
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