from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any, Iterator

import coverage_slot_guard as _guard

try:
    import fcntl
except ImportError:  # pragma: no cover - production/CI are POSIX; fail closed below.
    fcntl = None  # type: ignore[assignment]


_LOCK_SUFFIX = ".handoff.lock"
_LOCKED_MARKER = "_coverage_slot_handoff_locked"


@contextlib.contextmanager
def _exclusive_slot_lock(state_dir: Path, publication_date: str) -> Iterator[None]:
    """Serialize ownership transfer with request admission for one daily slot."""
    if fcntl is None:
        raise _guard.CoverageSlotError(
            "atomic Coverage optional-slot handoff requires POSIX file locking"
        )
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _guard.journal_path(state_dir, publication_date).with_name(
        _guard.journal_path(state_dir, publication_date).name + _LOCK_SUFFIX
    )
    with lock_path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _locked_mark_request_started(self: _guard.CoverageSlotReservation) -> None:
    """Preserve the guard transition while making it mutually exclusive with handoff."""
    with _exclusive_slot_lock(self.state_dir, self.publication_date):
        value = _guard.load_journal(self.state_dir, self.publication_date)
        if value is None:
            raise _guard.CoverageSlotError("Coverage optional-slot reservation disappeared")
        _guard._assert_identity(value, self.identity)
        state = value.get("state")
        if state == "request_started":
            raise _guard.CoverageSlotError("Coverage optional-slot request already started")
        if state in {"response_saved", "processed"}:
            raise _guard.CoverageSlotError(
                f"Coverage optional-slot transport already consumed: state={state}"
            )
        if state != "reserved":
            raise _guard.CoverageSlotError(
                f"Coverage optional-slot cannot start request from state={state!r}"
            )
        value["state"] = "request_started"
        value["wire_attempt_admitted"] = True
        value["slot_consumed_or_ambiguous"] = True
        self._write(value)


_locked_mark_request_started.__dict__[_LOCKED_MARKER] = True


def install_locked_slot_transitions() -> None:
    """Install the shared lock on request admission once per interpreter."""
    current = _guard.CoverageSlotReservation.mark_request_started
    if getattr(current, _LOCKED_MARKER, False):
        return
    _guard.CoverageSlotReservation.mark_request_started = _locked_mark_request_started


def transfer_reserved_slot(
    *,
    state_dir: Path,
    publication_date: str,
    expected_journal: dict[str, Any],
    target_owner: str,
    target_search_window: dict[str, Any],
    target_request_contract: dict[str, Any],
    target_bundle_identity: dict[str, Any] | None,
) -> _guard.CoverageSlotReservation | None:
    """Atomically replace one proven unstarted reservation with another owner.

    The journal is never unlinked. A crash leaves either the original P3b
    reservation or the complete target legacy reservation. Request admission and
    this transfer use the same file lock, so a request_started transition cannot
    be overwritten after the compare step.
    """
    state_dir = Path(state_dir)
    with _exclusive_slot_lock(state_dir, publication_date):
        current = _guard.load_journal(state_dir, publication_date)
        if not isinstance(current, dict):
            return None
        if _guard.sha256_value(current) != _guard.sha256_value(expected_journal):
            return None
        if str(current.get("state") or "") != "reserved":
            return None
        if current.get("wire_attempt_admitted") is True:
            return None
        if current.get("slot_consumed_or_ambiguous") is True:
            return None
        if str(current.get("response_sha256") or "").strip():
            return None
        if current.get("result_snapshot") is not None or current.get("processed_snapshot") is not None:
            return None
        if _guard.response_path(state_dir, publication_date).exists():
            return None

        # P3a normally derives the bundle date from a ContextVar while executing.
        # The ownership transfer happens just before that execution context is
        # installed, so bind the transferred reservation to the explicit daily
        # slot date here. Otherwise a correct transfer can hash an empty date and
        # then fail identity validation when the durable resolver sees the real
        # publication date a moment later.
        normalized_bundle_identity = (
            dict(target_bundle_identity)
            if isinstance(target_bundle_identity, dict)
            else target_bundle_identity
        )
        if isinstance(normalized_bundle_identity, dict):
            normalized_bundle_identity["publication_date"] = publication_date

        identity = _guard._identity_payload(
            publication_date=publication_date,
            owner=target_owner,
            search_window=target_search_window,
            request_contract=target_request_contract,
            bundle_identity=normalized_bundle_identity,
        )
        replacement = {
            "version": _guard.VERSION,
            **identity,
            "state": "reserved",
            "slot_consumed_or_ambiguous": False,
            "wire_attempt_admitted": False,
            "request_contract": {
                "owner": target_owner,
                "request_contract_sha256": identity["request_contract_sha256"],
            },
        }
        _guard._atomic_write_json(
            _guard.journal_path(state_dir, publication_date), replacement
        )
        return _guard.CoverageSlotReservation(
            state_dir=state_dir,
            publication_date=publication_date,
            identity=identity,
        )
