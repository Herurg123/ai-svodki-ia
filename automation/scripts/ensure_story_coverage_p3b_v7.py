#!/usr/bin/env python3
"""P3b v7: production recovery preflight over preserved v6 semantics.

v7 does not change the durable optional-slot request identity or binder semantics.
Binder v4 still uses durable VERSION=2 and semantic EVIDENCE_VERSION=6. The v7
change closes a production integration gap above ``execute_audit_plan``: an old
complete artifact or reusable Coverage recovery input could previously bypass the
v6 stale-positive postcondition entirely.

Before the historical production main is allowed to inspect complete/reusable
artifacts, v7 deterministically revokes only provenance-bound candidates admitted
by stale positive P3b evidence, writes a durable pending marker, sanitizes both
current and persisted recovery research, and quarantines ``stories.json`` when the
publishable snapshot can be affected. The optional-slot journal is deliberately
left byte-for-byte unchanged. A successful child run must rebuild a clean story
set before an invalidating marker can become completed; crashes and failures keep
publication fail-closed.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from coverage_slot_guard import CoverageSlotError, load_journal

_V6_PATH = Path(__file__).with_name("ensure_story_coverage_p3b_v6.py")
_V6_SPEC = importlib.util.spec_from_file_location(
    "ensure_story_coverage_p3b_v6_preserved", _V6_PATH
)
assert _V6_SPEC and _V6_SPEC.loader
_v6 = importlib.util.module_from_spec(_V6_SPEC)
sys.modules[_V6_SPEC.name] = _v6
_V6_SPEC.loader.exec_module(_v6)

for _name in dir(_v6):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_v6, _name)

P3B_RUNTIME_VERSION = 7
P3B_RECOVERY_PREFLIGHT_VERSION = 1
_REVOCATION_PREFIX = "coverage-p3b-v7-revocation-"

_V7_INTERNALS = {
    "_v6",
    "_V6_PATH",
    "_V6_SPEC",
    "_V7_INTERNALS",
    "_REVOCATION_PREFIX",
    "_sync_p3b_public_hooks",
    "_canonical_bytes",
    "_sha256_bytes",
    "_atomic_write_bytes",
    "_atomic_write_json",
    "_read_json",
    "_cli_arg",
    "_revocation_marker_path",
    "_persisted_research_path",
    "_backup_path",
    "_load_stale_positive_snapshot",
    "_signal_from_marker_or_snapshot",
    "_sanitize_candidate_containers",
    "_revoked_candidates",
    "_candidate_fingerprints",
    "_object_mentions_revoked",
    "_backup_once",
    "_load_marker",
    "recovery_preflight",
    "_postflight",
    "execute_audit_plan",
    "main",
    "__getattr__",
}


def __getattr__(name: str) -> Any:
    return getattr(_v6, name)


def _sync_p3b_public_hooks() -> None:
    """Propagate sanctioned public monkeypatch seams into preserved v6."""
    for name, value in list(globals().items()):
        if name in _V7_INTERNALS or (name.startswith("__") and name.endswith("__")):
            continue
        try:
            exists = hasattr(_v6, name)
        except Exception:
            exists = False
        if exists:
            setattr(_v6, name, value)
    _v6._sync_p3b_public_hooks()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            directory = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_bytes(path, _canonical_bytes(value) + b"\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _cli_arg(name: str) -> str | None:
    for index, value in enumerate(sys.argv):
        if value == name and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        prefix = name + "="
        if value.startswith(prefix):
            return value[len(prefix) :]
    return None


def _revocation_marker_path(state_dir: Path, publication_date: str) -> Path:
    return Path(state_dir) / f"{_REVOCATION_PREFIX}{publication_date}.json"


def _persisted_research_path(state_dir: Path, publication_date: str) -> Path:
    return Path(state_dir) / f"coverage-audit-merged-candidates-{publication_date}.json"


def _backup_path(marker_path: Path, kind: str) -> Path:
    return marker_path.with_name(f"{marker_path.stem}.{kind}.original.json")


def _load_stale_positive_snapshot(
    state_dir: Path, publication_date: str
) -> dict[str, Any] | None:
    """Read the same stale-positive condition as v6 without rewriting journal state."""
    try:
        journal = load_journal(Path(state_dir), publication_date)
    except CoverageSlotError:
        return None
    if not isinstance(journal, dict) or str(journal.get("state") or "") != "processed":
        return None
    saved = journal.get("processed_snapshot")
    if not isinstance(saved, dict):
        return None
    diagnostic = saved.get(_v6._v2._P3B_DIAGNOSTIC_KEY)
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
    if (
        int(diagnostic.get("binder_evidence_version", 0) or 0)
        == P3B_BINDER_EVIDENCE_VERSION
    ):
        return None
    return copy.deepcopy(saved)


def _signal_from_marker_or_snapshot(
    marker: dict[str, Any] | None,
    stale_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    marker_signal = str((marker or {}).get("stale_signal_id") or "").strip()
    if marker_signal:
        return {"signal_id": marker_signal}
    if isinstance(stale_snapshot, dict):
        return _v6._stale_processed_signal(stale_snapshot, None)
    return None


def _sanitize_candidate_containers(
    value: Any, signal: dict[str, Any] | None
) -> tuple[Any, int]:
    """Recursively revoke only exact stale P3b provenance from candidate arrays."""
    removed = 0
    if isinstance(value, list):
        output: list[Any] = []
        for item in value:
            sanitized, count = _sanitize_candidate_containers(item, signal)
            output.append(sanitized)
            removed += count
        return output, removed
    if not isinstance(value, dict):
        return copy.deepcopy(value), 0

    output: dict[str, Any] = {}
    for key, item in value.items():
        sanitized, count = _sanitize_candidate_containers(item, signal)
        output[key] = sanitized
        removed += count

    candidates = output.get("candidates")
    if isinstance(candidates, list):
        cleaned = _v6._without_stale_p3b_candidates(
            {"candidates": candidates}, signal
        ).get("candidates")
        if isinstance(cleaned, list):
            removed += max(0, len(candidates) - len(cleaned))
            output["candidates"] = cleaned
    return output, removed


def _revoked_candidates(
    stale_snapshot: dict[str, Any] | None,
    signal: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(stale_snapshot, dict):
        return []
    original = stale_snapshot.get("candidates")
    if not isinstance(original, list):
        return []
    cleaned = _v6._without_stale_p3b_candidates(stale_snapshot, signal).get(
        "candidates"
    )
    cleaned = cleaned if isinstance(cleaned, list) else []
    return [
        copy.deepcopy(item)
        for item in original
        if isinstance(item, dict) and item not in cleaned
    ]


def _candidate_fingerprints(candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in candidates:
        primary = item.get("primary_source")
        url = str(primary.get("url") or "").strip() if isinstance(primary, dict) else ""
        rows.append(
            {
                "id": str(item.get("id") or "").strip(),
                "title": str(item.get("title") or "").strip(),
                "url": url,
            }
        )
    return rows


def _object_mentions_revoked(value: Any, fingerprints: list[dict[str, str]]) -> bool:
    ids = {row["id"] for row in fingerprints if row.get("id")}
    titles = {row["title"] for row in fingerprints if row.get("title")}
    urls = {row["url"] for row in fingerprints if row.get("url")}

    if isinstance(value, list):
        return any(_object_mentions_revoked(item, fingerprints) for item in value)
    if not isinstance(value, dict):
        return False

    candidate_id = str(value.get("candidate_id") or value.get("id") or "").strip()
    if candidate_id and candidate_id in ids:
        return True
    title = str(value.get("title") or value.get("headline") or "").strip()
    if title and title in titles:
        return True
    for key in ("url", "source_url", "primary_url"):
        url = str(value.get(key) or "").strip()
        if url and url in urls:
            return True
    primary = value.get("primary_source")
    if isinstance(primary, dict):
        url = str(primary.get("url") or "").strip()
        if url and url in urls:
            return True
    sources = value.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict):
                url = str(source.get("url") or "").strip()
                if url and url in urls:
                    return True
    return any(_object_mentions_revoked(item, fingerprints) for item in value.values())


def _backup_once(source: Path, backup: Path) -> None:
    if not source.is_file() or backup.exists():
        return
    _atomic_write_bytes(backup, source.read_bytes())


def _load_marker(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = _read_json(path)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def recovery_preflight(
    *,
    publication_date: str,
    artifact_dir: Path,
    report_path: Path,
    state_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Quarantine stale-positive production reuse before historical main runs.

    The durable optional-slot journal is read-only here. A pending marker is
    written before mutation. Persisted merged research and the reusable Coverage
    report are sanitized with the same exact v6 provenance predicate because both
    are later recovery inputs, even when the current complete digest is clean.
    """
    state_dir = Path(state_dir if state_dir is not None else STATE_DIR)
    artifact_dir = Path(artifact_dir)
    report_path = Path(report_path)
    marker_path = _revocation_marker_path(state_dir, publication_date)
    persisted_research_path = _persisted_research_path(state_dir, publication_date)
    marker = _load_marker(marker_path)
    stale_snapshot = _load_stale_positive_snapshot(state_dir, publication_date)
    signal = _signal_from_marker_or_snapshot(marker, stale_snapshot)
    if signal is None:
        return None

    if isinstance(stale_snapshot, dict):
        revoked = _revoked_candidates(stale_snapshot, signal)
        fingerprints = _candidate_fingerprints(revoked)
    else:
        fingerprints = [
            {
                "id": str(row.get("id") or ""),
                "title": str(row.get("title") or ""),
                "url": str(row.get("url") or ""),
            }
            for row in (marker or {}).get("revoked_candidate_fingerprints") or []
            if isinstance(row, dict)
        ]

    candidates_path = artifact_dir / "candidates.json"
    stories_path = artifact_dir / "stories.json"

    sanitized_research: Any = None
    research_removed = 0
    if candidates_path.is_file():
        research = _read_json(candidates_path)
        sanitized_research, research_removed = _sanitize_candidate_containers(
            research, signal
        )

    sanitized_persisted_research: Any = None
    persisted_research_removed = 0
    if persisted_research_path.is_file():
        persisted_research = _read_json(persisted_research_path)
        sanitized_persisted_research, persisted_research_removed = (
            _sanitize_candidate_containers(persisted_research, signal)
        )

    sanitized_report: Any = None
    report_removed = 0
    if report_path.is_file():
        report = _read_json(report_path)
        sanitized_report, report_removed = _sanitize_candidate_containers(report, signal)

    stories: Any = None
    story_affected = False
    if stories_path.is_file():
        try:
            stories = _read_json(stories_path)
        except Exception:
            stories = None
        story_affected = bool(
            fingerprints and _object_mentions_revoked(stories, fingerprints)
        )

    marker_active = bool(
        isinstance(marker, dict) and marker.get("state") in {"pending", "blocked"}
    )
    # Markers written before this field existed are treated conservatively as
    # publication-invalidating. A recovery-input-only cleanup explicitly stores
    # False so a crash during report/merged-research sanitation does not destroy
    # an otherwise proven-clean complete digest on restart.
    publication_guard_active = bool(
        marker_active and (marker or {}).get("publication_snapshot_invalidated") is not False
    )
    publication_risk = bool(
        research_removed or story_affected or publication_guard_active
    )
    recovery_inputs_need_cleanup = bool(
        report_removed or persisted_research_removed
    )
    if not publication_risk and not recovery_inputs_need_cleanup:
        return None

    stale_signal_id = str((signal or {}).get("signal_id") or "").strip()
    marker_value: dict[str, Any] = copy.deepcopy(marker) if isinstance(marker, dict) else {}
    publication_snapshot_invalidated = bool(
        marker_value.get("publication_snapshot_invalidated") is True
        or publication_risk
    )
    marker_value.update(
        {
            "version": P3B_RECOVERY_PREFLIGHT_VERSION,
            "runtime_version": P3B_RUNTIME_VERSION,
            "publication_date": publication_date,
            "state": "pending",
            "reason": "stale_positive_p3b_candidate_revocation",
            "stale_signal_id": stale_signal_id or None,
            "binder_evidence_version_required": P3B_BINDER_EVIDENCE_VERSION,
            "revoked_candidate_fingerprints": fingerprints,
            "artifact_dir": str(artifact_dir),
            "report_path": str(report_path),
            "persisted_research_path": str(persisted_research_path),
            "optional_slot_journal_mutated": False,
            "publication_snapshot_invalidated": publication_snapshot_invalidated,
            "research_revocations": int(research_removed),
            "persisted_research_revocations": int(persisted_research_removed),
            "prior_report_revocations": int(report_removed),
            "stories_quarantined": bool(
                marker_value.get("stories_quarantined")
                or (
                    publication_snapshot_invalidated
                    and stories_path.is_file()
                )
            ),
        }
    )
    if candidates_path.is_file() and "original_candidates_sha256" not in marker_value:
        marker_value["original_candidates_sha256"] = _sha256_bytes(
            candidates_path.read_bytes()
        )
    if (
        persisted_research_path.is_file()
        and "original_persisted_research_sha256" not in marker_value
    ):
        marker_value["original_persisted_research_sha256"] = _sha256_bytes(
            persisted_research_path.read_bytes()
        )
    if report_path.is_file() and "original_report_sha256" not in marker_value:
        marker_value["original_report_sha256"] = _sha256_bytes(report_path.read_bytes())
    if stories_path.is_file() and "original_stories_sha256" not in marker_value:
        marker_value["original_stories_sha256"] = _sha256_bytes(stories_path.read_bytes())

    candidates_backup = _backup_path(marker_path, "candidates")
    persisted_research_backup = _backup_path(marker_path, "merged-research")
    report_backup = _backup_path(marker_path, "coverage-report")
    stories_backup = _backup_path(marker_path, "stories")

    if not publication_snapshot_invalidated:
        # Recovery-input-only sanitation is still two-phase: pending first, then
        # first forensic backups, then mutations, then completed. The explicit
        # non-invalidating marker scope lets a restart resume without needlessly
        # quarantining a clean complete digest.
        _atomic_write_json(marker_path, marker_value)
        _backup_once(persisted_research_path, persisted_research_backup)
        _backup_once(report_path, report_backup)
        if (
            persisted_research_path.is_file()
            and sanitized_persisted_research is not None
        ):
            _atomic_write_json(
                persisted_research_path, sanitized_persisted_research
            )
        if report_path.is_file() and sanitized_report is not None:
            _atomic_write_json(report_path, sanitized_report)
        marker_value["state"] = "completed"
        marker_value["reason"] = "stale_positive_p3b_recovery_inputs_sanitized"
        if persisted_research_path.is_file():
            marker_value["clean_persisted_research_sha256"] = _sha256_bytes(
                persisted_research_path.read_bytes()
            )
        if report_path.is_file():
            marker_value["clean_report_sha256"] = _sha256_bytes(
                report_path.read_bytes()
            )
        _atomic_write_json(marker_path, marker_value)
        return None

    # Crash ordering is intentional: pending invalidating marker first, then
    # first backups, then mutations. A restart therefore cannot accept the old
    # complete publication snapshot even if it crashed before stories unlink.
    _atomic_write_json(marker_path, marker_value)

    _backup_once(candidates_path, candidates_backup)
    _backup_once(persisted_research_path, persisted_research_backup)
    _backup_once(report_path, report_backup)
    _backup_once(stories_path, stories_backup)

    if candidates_path.is_file() and sanitized_research is not None:
        _atomic_write_json(candidates_path, sanitized_research)
    if (
        persisted_research_path.is_file()
        and sanitized_persisted_research is not None
    ):
        _atomic_write_json(persisted_research_path, sanitized_persisted_research)
    if report_path.is_file() and sanitized_report is not None:
        _atomic_write_json(report_path, sanitized_report)
    if stories_path.is_file():
        stories_path.unlink()

    context = copy.deepcopy(marker_value)
    context["marker_path"] = str(marker_path)
    context["candidate_backup_path"] = str(candidates_backup)
    context["persisted_research_backup_path"] = str(persisted_research_backup)
    context["report_backup_path"] = str(report_backup)
    context["stories_backup_path"] = str(stories_backup)
    return context


def _postflight(
    context: dict[str, Any] | None,
    *,
    child_code: int,
    artifact_dir: Path,
    report_path: Path,
) -> int:
    if not isinstance(context, dict):
        return int(child_code)
    marker_path = Path(str(context.get("marker_path") or ""))
    if child_code != 0:
        return int(child_code)

    signal_id = str(context.get("stale_signal_id") or "").strip()
    signal = {"signal_id": signal_id} if signal_id else None
    fingerprints = [
        row
        for row in context.get("revoked_candidate_fingerprints") or []
        if isinstance(row, dict)
    ]

    candidates_path = Path(artifact_dir) / "candidates.json"
    stories_path = Path(artifact_dir) / "stories.json"
    persisted_research_path = _persisted_research_path(
        Path(report_path).parent,
        str(context.get("publication_date") or ""),
    )
    failures: list[str] = []

    if not candidates_path.is_file():
        failures.append("rebuilt artifact is missing candidates.json")
    else:
        research = _read_json(candidates_path)
        _cleaned, removed = _sanitize_candidate_containers(research, signal)
        if removed:
            failures.append(
                "rebuilt candidates.json still contains stale P3b provenance"
            )

    if persisted_research_path.is_file():
        persisted_research = _read_json(persisted_research_path)
        _cleaned, removed = _sanitize_candidate_containers(
            persisted_research, signal
        )
        if removed:
            failures.append(
                "persisted merged research still contains stale P3b provenance"
            )

    if report_path.is_file():
        report = _read_json(report_path)
        _cleaned, removed = _sanitize_candidate_containers(report, signal)
        if removed:
            failures.append("coverage report still contains stale P3b provenance")

    if not stories_path.is_file():
        failures.append("clean editorial rebuild did not produce stories.json")
    else:
        stories = _read_json(stories_path)
        if fingerprints and _object_mentions_revoked(stories, fingerprints):
            failures.append(
                "rebuilt stories.json still references revoked P3b candidate"
            )

    marker = _load_marker(marker_path) or copy.deepcopy(context)
    if failures:
        marker["state"] = "blocked"
        marker["postflight_errors"] = failures
        _atomic_write_json(marker_path, marker)
        return 1

    marker["state"] = "completed"
    marker["postflight_errors"] = []
    marker["clean_candidates_sha256"] = _sha256_bytes(candidates_path.read_bytes())
    marker["clean_stories_sha256"] = _sha256_bytes(stories_path.read_bytes())
    if persisted_research_path.is_file():
        marker["clean_persisted_research_sha256"] = _sha256_bytes(
            persisted_research_path.read_bytes()
        )
    if report_path.is_file():
        marker["clean_report_sha256"] = _sha256_bytes(report_path.read_bytes())
    _atomic_write_json(marker_path, marker)
    return 0


def execute_audit_plan(*args: Any, **kwargs: Any) -> Any:
    _sync_p3b_public_hooks()
    return _v6.execute_audit_plan(*args, **kwargs)


def main() -> int:
    _sync_p3b_public_hooks()
    publication_date = str(_cli_arg("--publication-date") or "").strip()
    artifact_raw = _cli_arg("--artifact-dir")
    report_raw = _cli_arg("--report")
    if not publication_date or not artifact_raw or not report_raw:
        # Preserve historical argparse ownership for malformed CLI invocations.
        return int(_v6.main())

    artifact_dir = Path(artifact_raw)
    report_path = Path(report_raw)
    state_dir = Path(STATE_DIR)
    context = recovery_preflight(
        publication_date=publication_date,
        artifact_dir=artifact_dir,
        report_path=report_path,
        state_dir=state_dir,
    )
    child_code = int(_v6.main())
    return _postflight(
        context,
        child_code=child_code,
        artifact_dir=artifact_dir,
        report_path=report_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
