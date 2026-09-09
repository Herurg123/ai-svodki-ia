"""Small, dependency-free evidence identities for offline Source Value reports."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_url(value: Any) -> bool:
    if not nonempty(value) or value != value.strip() or any(c.isspace() for c in value):
        return False
    try:
        url = urlsplit(value)
        return url.scheme in {"http", "https"} and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        return False


def valid_day(value: Any) -> bool:
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def meaningful_identity(row: Any) -> bool:
    if not isinstance(row, dict) or not all(nonempty(row.get(k)) for k in ("organization", "topic", "event_type")):
        return False
    if not valid_day(row.get("published_date")) or "published_at" not in row:
        return False
    timestamp = row["published_at"]
    if timestamp is None:  # Existing date-only artifacts are an active contract.
        return True
    if not nonempty(timestamp):
        return False
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return parsed.utcoffset() is not None and parsed.date().isoformat() == row["published_date"]
    except ValueError:
        return False
