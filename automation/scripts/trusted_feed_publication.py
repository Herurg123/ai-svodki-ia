#!/usr/bin/env python3
"""Strict publication evidence contract for approved first-party feeds.

This module never fetches a feed or page. It validates evidence already collected
by Source Pulse against the production registry and provides a deterministic
same-host/exact-item identity proof for the later Source Freshness gate.
"""
from __future__ import annotations

import html
import json
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

VERSION = 1
EVIDENCE_KIND = "trusted_first_party_feed"
# P1 is intentionally narrow. The registry still has to describe the same source
# as Tier-A official rss_atom; this allowlist controls which date fields can ever
# become publication authority.
TRUSTED_SOURCE_FIELDS: dict[str, frozenset[str]] = {
    "openai_news_rss": frozenset({"rss_pubdate", "atom_published"}),
}
DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "source-pulse-v1.json"
)
_TRACKING_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source",
}


class TrustedFeedError(RuntimeError):
    """Saved feed publication evidence is malformed or violates the trust contract."""


@dataclass(frozen=True)
class TrustedFeedProof:
    source_id: str
    feed_url: str
    item_url: str
    published_at: datetime
    published_date: date
    feed_date_field: str


def canonical_url(value: Any) -> str | None:
    """Return a strict HTTPS URL identity suitable for feed/item equality checks."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urllib.parse.urlsplit(value.strip())
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        return None
    host = parsed.hostname.casefold().strip(".")
    path = parsed.path.rstrip("/") or "/"
    query = [
        (key, item)
        for key, item in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        if key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    return urllib.parse.urlunsplit(
        ("https", host, path, urllib.parse.urlencode(query), "")
    )


def _first_text(node: ET.Element, names: set[str]) -> str | None:
    for child in node.iter():
        if (
            child.tag.split("}")[-1].casefold() in names
            and child.text
            and child.text.strip()
        ):
            return child.text.strip()
    return None


def feed_publication_fields(body: str, base_url: str) -> dict[str, str]:
    """Classify which feed field supplied the date for each exact item URL.

    `updated` and generic `date` are deliberately recorded but never trusted by
    P1. This lets tests prove that an Atom update timestamp cannot masquerade as
    an original publication timestamp.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return {}
    result: dict[str, str] = {}
    for node in root.iter():
        if node.tag.split("}")[-1].casefold() not in {"item", "entry"}:
            continue
        raw_url = _first_text(node, {"link", "guid", "id"}) or ""
        if not raw_url:
            for child in node:
                if (
                    child.tag.split("}")[-1].casefold() == "link"
                    and child.attrib.get("href")
                ):
                    raw_url = child.attrib["href"]
                    break
        item_url = canonical_url(urllib.parse.urljoin(base_url, raw_url))
        if item_url is None:
            continue
        if _first_text(node, {"pubdate"}):
            result[item_url] = "rss_pubdate"
        elif _first_text(node, {"published"}):
            result[item_url] = "atom_published"
        elif _first_text(node, {"updated"}):
            result[item_url] = "atom_updated"
        elif _first_text(node, {"date"}):
            result[item_url] = "feed_date"
    return result


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrustedFeedError(f"trusted feed registry unavailable: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("sources"), list):
        raise TrustedFeedError("trusted feed registry is invalid")
    return value


def trusted_source_policy(
    registry: dict[str, Any], source_id: str
) -> dict[str, Any] | None:
    allowed_fields = TRUSTED_SOURCE_FIELDS.get(source_id)
    if not allowed_fields:
        return None
    for raw in registry.get("sources") or []:
        if not isinstance(raw, dict) or str(raw.get("id") or "") != source_id:
            continue
        if (
            raw.get("tier") != "A"
            or raw.get("role") != "official"
            or raw.get("adapter") != "rss_atom"
        ):
            return None
        feed_url = canonical_url(raw.get("url"))
        if feed_url is None:
            return None
        feed_host = urllib.parse.urlsplit(feed_url).hostname or ""
        allowed_hosts = {
            str(item).casefold().strip(".") for item in raw.get("allowed_hosts") or []
        }
        if feed_host not in allowed_hosts:
            return None
        return {
            "source_id": source_id,
            "feed_url": feed_url,
            "feed_host": feed_host,
            "accepted_feed_fields": allowed_fields,
        }
    return None


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def build_evidence(
    lead: dict[str, Any], registry: dict[str, Any]
) -> dict[str, Any] | None:
    """Build durable evidence only for an approved exact feed item."""
    source_id = str(lead.get("source_id") or "")
    policy = trusted_source_policy(registry, source_id)
    if policy is None:
        return None
    field = str(lead.get("publication_evidence_kind") or "")
    if field not in policy["accepted_feed_fields"]:
        return None
    item_url = canonical_url(lead.get("url"))
    if item_url is None:
        return None
    item_host = urllib.parse.urlsplit(item_url).hostname or ""
    if item_host != policy["feed_host"]:
        return None
    published_at = _aware(lead.get("published_at"))
    if published_at is None or str(lead.get("time_precision") or "") != "datetime":
        return None
    if str(lead.get("published_date") or "") != published_at.date().isoformat():
        return None
    if lead.get("cutoff_ambiguous") is True:
        return None
    source_item_id = canonical_url(lead.get("source_item_id"))
    if source_item_id is not None and source_item_id != item_url:
        return None
    return {
        "version": VERSION,
        "kind": EVIDENCE_KIND,
        "source_id": source_id,
        "feed_url": policy["feed_url"],
        "item_url": item_url,
        "published_at": published_at.isoformat(),
        "published_date": published_at.date().isoformat(),
        "time_precision": "datetime",
        "feed_date_field": field,
        "same_host_required": True,
        "exact_item_url_required": True,
    }


def validate_evidence(
    candidate: dict[str, Any], registry: dict[str, Any]
) -> TrustedFeedProof | None:
    """Re-validate saved evidence independently at Source Freshness time."""
    evidence = candidate.get("trusted_feed_publication_evidence")
    if (
        not isinstance(evidence, dict)
        or evidence.get("version") != VERSION
        or evidence.get("kind") != EVIDENCE_KIND
    ):
        return None
    source_id = str(evidence.get("source_id") or "")
    policy = trusted_source_policy(registry, source_id)
    if policy is None:
        return None
    if canonical_url(evidence.get("feed_url")) != policy["feed_url"]:
        return None
    field = str(evidence.get("feed_date_field") or "")
    if field not in policy["accepted_feed_fields"]:
        return None
    item_url = canonical_url(evidence.get("item_url"))
    primary = candidate.get("primary_source")
    candidate_url = (
        canonical_url(primary.get("url")) if isinstance(primary, dict) else None
    )
    if item_url is None or candidate_url != item_url:
        return None
    item_host = urllib.parse.urlsplit(item_url).hostname or ""
    if item_host != policy["feed_host"]:
        return None
    published_at = _aware(evidence.get("published_at"))
    if (
        published_at is None
        or evidence.get("published_date") != published_at.date().isoformat()
        or evidence.get("time_precision") != "datetime"
    ):
        return None
    return TrustedFeedProof(
        source_id=source_id,
        feed_url=policy["feed_url"],
        item_url=item_url,
        published_at=published_at,
        published_date=published_at.date(),
        feed_date_field=field,
    )


def proof_in_window(
    proof: TrustedFeedProof, *, start_at: datetime, end_at: datetime
) -> bool:
    return start_at <= proof.published_at <= end_at


def direct_evidence_conflicts(
    proof: TrustedFeedProof, direct_published_date: date
) -> bool:
    return direct_published_date != proof.published_date


def synthetic_html(proof: TrustedFeedProof, *, title: str = "") -> str:
    """Build a local-only metadata shim consumed by the existing deterministic parser."""
    timestamp = html.escape(proof.published_at.isoformat(), quote=True)
    title_text = html.escape(" ".join(str(title).split()), quote=True)
    description = (
        f'<meta name="description" content="OpenAI official artificial intelligence publication: {title_text}">'
        if title_text
        else ""
    )
    return (
        f'<meta property="article:published_time" content="{timestamp}">'
        + description
    )
