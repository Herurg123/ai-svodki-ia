from __future__ import annotations

import contextlib
import contextvars
import copy
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


VERSION = 1
JOURNAL_PREFIX = "coverage-optional-slot-"
RESPONSE_SUFFIX = ".response.json"
_RESULT_SNAPSHOT_KEY = "result_snapshot"
_PROCESSED_SNAPSHOT_KEY = "processed_snapshot"


class CoverageSlotError(RuntimeError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_bytes(path, _canonical_bytes(value) + b"\n")


def journal_path(state_dir: Path, publication_date: str) -> Path:
    return Path(state_dir) / f"{JOURNAL_PREFIX}{publication_date}.json"


def response_path(state_dir: Path, publication_date: str) -> Path:
    return Path(state_dir) / f"{JOURNAL_PREFIX}{publication_date}{RESPONSE_SUFFIX}"


def load_journal(state_dir: Path, publication_date: str) -> dict[str, Any] | None:
    path = journal_path(state_dir, publication_date)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageSlotError(f"invalid Coverage optional-slot journal: {exc}") from exc
    if not isinstance(value, dict):
        raise CoverageSlotError("Coverage optional-slot journal must be an object")
    if int(value.get("version", 0) or 0) != VERSION:
        raise CoverageSlotError("unsupported Coverage optional-slot journal version")
    if value.get("publication_date") != publication_date:
        raise CoverageSlotError("Coverage optional-slot journal publication date mismatch")
    return value


def journal_state(state_dir: Path, publication_date: str) -> str | None:
    value = load_journal(state_dir, publication_date)
    return str(value.get("state")) if value is not None and value.get("state") else None


def _identity_payload(
    *,
    publication_date: str,
    owner: str,
    search_window: dict[str, Any],
    request_contract: dict[str, Any],
    bundle_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "publication_date": publication_date,
        "owner": owner,
        "search_window_sha256": sha256_value(search_window),
        "request_contract_sha256": sha256_value(request_contract),
        "bundle_identity_sha256": sha256_value(bundle_identity or {}),
    }


def _assert_identity(journal: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, value in expected.items():
        if journal.get(key) != value:
            raise CoverageSlotError(
                f"Coverage optional-slot identity mismatch for {key}: "
                f"saved={journal.get(key)!r} current={value!r}"
            )


@dataclass
class CoverageSlotReservation:
    state_dir: Path
    publication_date: str
    identity: dict[str, Any]

    @property
    def journal(self) -> dict[str, Any]:
        value = load_journal(self.state_dir, self.publication_date)
        if value is None:
            raise CoverageSlotError("Coverage optional-slot reservation disappeared")
        _assert_identity(value, self.identity)
        return value

    @property
    def state(self) -> str:
        return str(self.journal.get("state") or "")

    def _write(self, value: dict[str, Any]) -> None:
        _assert_identity(value, self.identity)
        _atomic_write_json(journal_path(self.state_dir, self.publication_date), value)

    def mark_request_started(self) -> None:
        value = self.journal
        state = value.get("state")
        if state == "request_started":
            raise CoverageSlotError("Coverage optional-slot request already started")
        if state in {"response_saved", "processed"}:
            raise CoverageSlotError(
                f"Coverage optional-slot transport already consumed: state={state}"
            )
        if state != "reserved":
            raise CoverageSlotError(
                f"Coverage optional-slot cannot start request from state={state!r}"
            )
        value["state"] = "request_started"
        value["wire_attempt_admitted"] = True
        value["slot_consumed_or_ambiguous"] = True
        self._write(value)

    def save_raw_response(self, raw_response: Any) -> None:
        value = self.journal
        if value.get("state") != "request_started":
            raise CoverageSlotError(
                "Coverage optional-slot response can be saved only after request_started"
            )
        raw_bytes = _canonical_bytes(raw_response) + b"\n"
        path = response_path(self.state_dir, self.publication_date)
        _atomic_write_bytes(path, raw_bytes)
        value["response_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
        value["state"] = "response_saved"
        value["slot_consumed_or_ambiguous"] = True
        self._write(value)

    def save_result_snapshot(self, snapshot: dict[str, Any]) -> None:
        value = self.journal
        if value.get("state") not in {"response_saved", "processed"}:
            raise CoverageSlotError(
                "Coverage optional-slot result snapshot requires saved response"
            )
        value[_RESULT_SNAPSHOT_KEY] = copy.deepcopy(snapshot)
        self._write(value)

    def mark_processed(self, processed_snapshot: dict[str, Any] | None = None) -> None:
        value = self.journal
        if value.get("state") not in {"response_saved", "processed"}:
            raise CoverageSlotError(
                "Coverage optional-slot cannot be processed before response_saved"
            )
        value["state"] = "processed"
        value["slot_consumed_or_ambiguous"] = True
        if processed_snapshot is not None:
            value[_PROCESSED_SNAPSHOT_KEY] = copy.deepcopy(processed_snapshot)
        self._write(value)

    def result_snapshot(self) -> dict[str, Any] | None:
        value = self.journal.get(_RESULT_SNAPSHOT_KEY)
        return copy.deepcopy(value) if isinstance(value, dict) else None

    def processed_snapshot(self) -> dict[str, Any] | None:
        value = self.journal.get(_PROCESSED_SNAPSHOT_KEY)
        return copy.deepcopy(value) if isinstance(value, dict) else None


def prepare_slot(
    *,
    state_dir: Path,
    publication_date: str,
    owner: str,
    search_window: dict[str, Any],
    request_contract: dict[str, Any],
    bundle_identity: dict[str, Any] | None = None,
) -> CoverageSlotReservation:
    if not publication_date:
        raise CoverageSlotError("Coverage optional-slot requires publication_date")
    if not owner:
        raise CoverageSlotError("Coverage optional-slot requires owner")
    identity = _identity_payload(
        publication_date=publication_date,
        owner=owner,
        search_window=search_window,
        request_contract=request_contract,
        bundle_identity=bundle_identity,
    )
    existing = load_journal(state_dir, publication_date)
    if existing is None:
        value = {
            "version": VERSION,
            **identity,
            "state": "reserved",
            "slot_consumed_or_ambiguous": False,
            "wire_attempt_admitted": False,
            "request_contract": {
                "owner": owner,
                "request_contract_sha256": identity["request_contract_sha256"],
            },
        }
        # Reservation durability is a prerequisite for transport admission.
        _atomic_write_json(journal_path(state_dir, publication_date), value)
    else:
        _assert_identity(existing, identity)
    return CoverageSlotReservation(Path(state_dir), publication_date, identity)


_ACTIVE_SLOT: contextvars.ContextVar[CoverageSlotReservation | None] = contextvars.ContextVar(
    "coverage_optional_slot", default=None
)


@contextlib.contextmanager
def activate_slot(reservation: CoverageSlotReservation) -> Iterator[CoverageSlotReservation]:
    token = _ACTIVE_SLOT.set(reservation)
    try:
        yield reservation
    finally:
        _ACTIVE_SLOT.reset(token)


def active_slot() -> CoverageSlotReservation | None:
    return _ACTIVE_SLOT.get()


def slot_is_consumed_or_ambiguous(
    state_dir: Path, publication_date: str
) -> bool:
    value = load_journal(state_dir, publication_date)
    return bool(
        isinstance(value, dict)
        and (
            value.get("slot_consumed_or_ambiguous") is True
            or value.get("state") in {"request_started", "response_saved", "processed"}
        )
    )


def restore_state_from_bundle(
    *,
    bundle_root: Path,
    target_state_dir: Path,
    publication_date: str,
) -> dict[str, Any]:
    source_dir = Path(bundle_root) / "production-daily"
    source_journal = journal_path(source_dir, publication_date)
    if not source_journal.is_file():
        return {
            "status": "not_present",
            "publication_date": publication_date,
            "copied": [],
        }
    try:
        journal = json.loads(source_journal.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageSlotError(f"invalid bundled Coverage optional-slot journal: {exc}") from exc
    if not isinstance(journal, dict) or journal.get("publication_date") != publication_date:
        raise CoverageSlotError("bundled Coverage optional-slot identity mismatch")
    if int(journal.get("version", 0) or 0) != VERSION:
        raise CoverageSlotError("unsupported bundled Coverage optional-slot journal version")

    target_state_dir = Path(target_state_dir)
    target_state_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    target_journal = journal_path(target_state_dir, publication_date)
    shutil.copy2(source_journal, target_journal)
    copied.append(str(target_journal))

    expected_response_sha = journal.get("response_sha256")
    source_response = response_path(source_dir, publication_date)
    if expected_response_sha:
        if not source_response.is_file():
            raise CoverageSlotError(
                "bundled Coverage optional-slot journal references missing response"
            )
        response_bytes = source_response.read_bytes()
        if hashlib.sha256(response_bytes).hexdigest() != expected_response_sha:
            raise CoverageSlotError("bundled Coverage optional-slot response hash mismatch")
        target_response = response_path(target_state_dir, publication_date)
        shutil.copy2(source_response, target_response)
        copied.append(str(target_response))
    elif source_response.exists():
        raise CoverageSlotError(
            "bundled Coverage optional-slot response exists without journal hash"
        )

    # Re-read through the normal validator after copying.
    load_journal(target_state_dir, publication_date)
    return {
        "status": "restored",
        "publication_date": publication_date,
        "state": journal.get("state"),
        "owner": journal.get("owner"),
        "copied": copied,
    }
