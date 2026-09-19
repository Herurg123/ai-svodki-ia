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
_RESULT_SNAPSHOT_SHA256_KEY = "result_snapshot_sha256"
_RESULT_SNAPSHOT_PROVENANCE_KEY = "result_snapshot_provenance"
_PROCESSED_SNAPSHOT_KEY = "processed_snapshot"
_PROCESSED_SNAPSHOT_SHA256_KEY = "processed_snapshot_sha256"
_PROCESSED_SNAPSHOT_PROVENANCE_KEY = "processed_snapshot_provenance"


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


def load_raw_response(state_dir: Path, publication_date: str) -> Any:
    journal = load_journal(state_dir, publication_date)
    if journal is None:
        raise CoverageSlotError("Coverage optional-slot journal is missing")
    expected = str(journal.get("response_sha256") or "").strip()
    if not expected:
        raise CoverageSlotError("Coverage optional-slot journal has no saved response hash")
    path = response_path(state_dir, publication_date)
    if not path.is_file():
        raise CoverageSlotError("Coverage optional-slot saved response is missing")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise CoverageSlotError("Coverage optional-slot saved response hash mismatch")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoverageSlotError(f"invalid Coverage optional-slot saved response: {exc}") from exc


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


def _validated_snapshot_provenance(
    journal: dict[str, Any],
    *,
    snapshot_key: str,
    snapshot_sha256_key: str,
    provenance_key: str,
    label: str,
) -> dict[str, Any] | None:
    snapshot = journal.get(snapshot_key)
    if not isinstance(snapshot, dict):
        return None
    saved_hash = str(journal.get(snapshot_sha256_key) or "").strip()
    provenance = journal.get(provenance_key)
    lineage_declared = bool(saved_hash or provenance is not None)
    if not lineage_declared:
        # Historical v1 journals predate durable result lineage. Their bytes are
        # still readable for fail-closed migration/sanitation, but the snapshot
        # is not proven reusable by the current runtime.
        return None
    if not saved_hash or not isinstance(provenance, dict):
        raise CoverageSlotError(
            f"Coverage optional-slot {label} provenance is incomplete"
        )
    actual_hash = sha256_value(snapshot)
    if saved_hash != actual_hash:
        raise CoverageSlotError(
            f"Coverage optional-slot {label} hash mismatch"
        )
    if str(provenance.get("request_contract_sha256") or "") != str(
        journal.get("request_contract_sha256") or ""
    ):
        raise CoverageSlotError(
            f"Coverage optional-slot {label} request provenance mismatch"
        )
    if str(provenance.get("response_sha256") or "") != str(
        journal.get("response_sha256") or ""
    ):
        raise CoverageSlotError(
            f"Coverage optional-slot {label} response provenance mismatch"
        )
    if str(provenance.get("snapshot_sha256") or "") != saved_hash:
        raise CoverageSlotError(
            f"Coverage optional-slot {label} snapshot provenance mismatch"
        )
    return copy.deepcopy(snapshot)


def validated_result_snapshot(journal: dict[str, Any]) -> dict[str, Any] | None:
    return _validated_snapshot_provenance(
        journal,
        snapshot_key=_RESULT_SNAPSHOT_KEY,
        snapshot_sha256_key=_RESULT_SNAPSHOT_SHA256_KEY,
        provenance_key=_RESULT_SNAPSHOT_PROVENANCE_KEY,
        label="result snapshot",
    )


def validated_processed_snapshot(journal: dict[str, Any]) -> dict[str, Any] | None:
    snapshot = _validated_snapshot_provenance(
        journal,
        snapshot_key=_PROCESSED_SNAPSHOT_KEY,
        snapshot_sha256_key=_PROCESSED_SNAPSHOT_SHA256_KEY,
        provenance_key=_PROCESSED_SNAPSHOT_PROVENANCE_KEY,
        label="processed snapshot",
    )
    if snapshot is None:
        return None
    provenance = journal.get(_PROCESSED_SNAPSHOT_PROVENANCE_KEY)
    result_hash = str((provenance or {}).get("result_snapshot_sha256") or "").strip()
    if result_hash:
        if str(journal.get(_RESULT_SNAPSHOT_SHA256_KEY) or "") != result_hash:
            raise CoverageSlotError(
                "Coverage optional-slot processed snapshot result provenance mismatch"
            )
        if validated_result_snapshot(journal) is None:
            raise CoverageSlotError(
                "Coverage optional-slot processed snapshot references unproven result snapshot"
            )
    return snapshot


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
        response_sha256 = str(value.get("response_sha256") or "").strip()
        if not response_sha256:
            raise CoverageSlotError(
                "Coverage optional-slot result snapshot requires saved response provenance"
            )
        saved = copy.deepcopy(snapshot)
        snapshot_sha256 = sha256_value(saved)
        value[_RESULT_SNAPSHOT_KEY] = saved
        value[_RESULT_SNAPSHOT_SHA256_KEY] = snapshot_sha256
        value[_RESULT_SNAPSHOT_PROVENANCE_KEY] = {
            "request_contract_sha256": value.get("request_contract_sha256"),
            "response_sha256": response_sha256,
            "snapshot_sha256": snapshot_sha256,
        }
        self._write(value)

    def mark_processed(self, processed_snapshot: dict[str, Any] | None = None) -> None:
        value = self.journal
        if value.get("state") not in {"response_saved", "processed"}:
            raise CoverageSlotError(
                "Coverage optional-slot cannot be processed before response_saved"
            )
        response_sha256 = str(value.get("response_sha256") or "").strip()
        if not response_sha256:
            raise CoverageSlotError(
                "Coverage optional-slot processed snapshot requires saved response provenance"
            )
        value["state"] = "processed"
        value["slot_consumed_or_ambiguous"] = True
        if processed_snapshot is not None:
            saved = copy.deepcopy(processed_snapshot)
            snapshot_sha256 = sha256_value(saved)
            value[_PROCESSED_SNAPSHOT_KEY] = saved
            value[_PROCESSED_SNAPSHOT_SHA256_KEY] = snapshot_sha256
            result_hash = str(value.get(_RESULT_SNAPSHOT_SHA256_KEY) or "").strip()
            if result_hash:
                # If result lineage is declared it must already be internally
                # consistent before it can be linked into processed provenance.
                validated_result_snapshot(value)
            value[_PROCESSED_SNAPSHOT_PROVENANCE_KEY] = {
                "request_contract_sha256": value.get("request_contract_sha256"),
                "response_sha256": response_sha256,
                "result_snapshot_sha256": result_hash or None,
                "snapshot_sha256": snapshot_sha256,
            }
        self._write(value)

    def result_snapshot(self) -> dict[str, Any] | None:
        value = self.journal.get(_RESULT_SNAPSHOT_KEY)
        return copy.deepcopy(value) if isinstance(value, dict) else None

    def processed_snapshot(self) -> dict[str, Any] | None:
        value = self.journal.get(_PROCESSED_SNAPSHOT_KEY)
        return copy.deepcopy(value) if isinstance(value, dict) else None

    def validated_result_snapshot(self) -> dict[str, Any] | None:
        return validated_result_snapshot(self.journal)

    def validated_processed_snapshot(self) -> dict[str, Any] | None:
        return validated_processed_snapshot(self.journal)

    def raw_response(self) -> Any:
        return load_raw_response(self.state_dir, self.publication_date)


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


def slot_is_consumed_or_ambiguous(state_dir: Path, publication_date: str) -> bool:
    value = load_journal(state_dir, publication_date)
    return bool(
        isinstance(value, dict)
        and (
            value.get("slot_consumed_or_ambiguous") is True
            or value.get("state") in {"request_started", "response_saved", "processed"}
        )
    )


def _validated_bundle_state(
    source_dir: Path, publication_date: str
) -> tuple[dict[str, Any], bytes, bytes | None]:
    source_journal = journal_path(source_dir, publication_date)
    if not source_journal.is_file():
        raise FileNotFoundError(source_journal)
    try:
        journal_bytes = source_journal.read_bytes()
        journal = json.loads(journal_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoverageSlotError(f"invalid bundled Coverage optional-slot journal: {exc}") from exc
    if not isinstance(journal, dict) or journal.get("publication_date") != publication_date:
        raise CoverageSlotError("bundled Coverage optional-slot identity mismatch")
    if int(journal.get("version", 0) or 0) != VERSION:
        raise CoverageSlotError("unsupported bundled Coverage optional-slot journal version")

    expected_response_sha = str(journal.get("response_sha256") or "").strip()
    source_response = response_path(source_dir, publication_date)
    response_bytes: bytes | None = None
    if expected_response_sha:
        if not source_response.is_file():
            raise CoverageSlotError(
                "bundled Coverage optional-slot journal references missing response"
            )
        response_bytes = source_response.read_bytes()
        if hashlib.sha256(response_bytes).hexdigest() != expected_response_sha:
            raise CoverageSlotError("bundled Coverage optional-slot response hash mismatch")
    elif source_response.exists():
        raise CoverageSlotError(
            "bundled Coverage optional-slot response exists without journal hash"
        )
    # New lineage fields are self-authenticating within the selected bundle.
    # Historical journals without them remain readable for fail-closed legacy
    # handling, but partial/mismatched provenance is rejected here.
    validated_result_snapshot(journal)
    validated_processed_snapshot(journal)
    return journal, journal_bytes, response_bytes


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

    journal, journal_bytes, response_bytes = _validated_bundle_state(
        source_dir, publication_date
    )
    target_state_dir = Path(target_state_dir)
    target_state_dir.mkdir(parents=True, exist_ok=True)
    target_journal = journal_path(target_state_dir, publication_date)
    target_response = response_path(target_state_dir, publication_date)

    if target_journal.exists():
        existing = target_journal.read_bytes()
        if existing != journal_bytes:
            raise CoverageSlotError(
                "existing Coverage optional-slot journal differs from selected bundle; overwrite forbidden"
            )
    if response_bytes is not None and target_response.exists():
        if target_response.read_bytes() != response_bytes:
            raise CoverageSlotError(
                "existing Coverage optional-slot response differs from selected bundle; overwrite forbidden"
            )
    if response_bytes is None and target_response.exists():
        raise CoverageSlotError(
            "existing Coverage optional-slot response has no matching selected-bundle response"
        )

    copied: list[str] = []
    if not target_journal.exists():
        shutil.copy2(source_journal, target_journal)
        copied.append(str(target_journal))
    if response_bytes is not None and not target_response.exists():
        shutil.copy2(response_path(source_dir, publication_date), target_response)
        copied.append(str(target_response))

    load_journal(target_state_dir, publication_date)
    if journal.get("response_sha256"):
        load_raw_response(target_state_dir, publication_date)
    return {
        "status": "restored" if copied else "already_present",
        "publication_date": publication_date,
        "state": journal.get("state"),
        "owner": journal.get("owner"),
        "copied": copied,
    }
