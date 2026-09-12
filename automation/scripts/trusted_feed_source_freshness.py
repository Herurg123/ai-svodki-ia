#!/usr/bin/env python3
"""Candidate-local bridge from saved trusted feed evidence to Source Freshness.

The ordinary direct page proof always runs first. Saved first-party feed evidence
is used only when the exact feed item URL cannot yield page publication metadata.
A different direct canonical URL or a contradictory direct publication date is a
fail-closed conflict, never a reason to prefer the feed.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import trusted_feed_publication as trusted_feed


class TrustedFeedSourceConflict(RuntimeError):
    pass


def verify_candidate_with_trusted_feed(
    candidate: dict[str, Any],
    *,
    start_at,
    end_at,
    fetcher,
    base_module,
    first_party_evidence: Callable[..., Any],
    registry_path: Path = trusted_feed.DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    """Run the preserved v1 proof with one strict candidate-local feed fallback."""
    registry = trusted_feed.load_registry(registry_path)
    proof = trusted_feed.validate_evidence(candidate, registry)
    if proof is None:
        return base_module.verify_candidate(
            candidate,
            start_at=start_at,
            end_at=end_at,
            fetcher=fetcher,
            evidence_resolver=lambda body, requested, final: first_party_evidence(
                body, requested, final, fetcher
            ),
        )

    feed_identity = proof.item_url
    title = " ".join(str(candidate.get("title") or "").split())
    fallback: dict[str, Any] | None = None
    conflict: dict[str, Any] | None = None

    def wrapped_fetch(url: str):
        nonlocal fallback, conflict
        identity = trusted_feed.canonical_url(url)
        if identity != feed_identity:
            return fetcher(url)
        try:
            body, final_url, http_status = fetcher(url)
        except Exception as exc:
            fallback = {
                "trigger": "direct_fetch_error",
                "error": f"{type(exc).__name__}: {exc}",
            }
            return trusted_feed.synthetic_html(proof, title=title), proof.item_url, 200

        final_identity = trusted_feed.canonical_url(final_url)
        if final_identity != feed_identity:
            conflict = {
                "reason": "trusted_feed_redirect_or_canonical_mismatch",
                "final_url": final_url,
            }
            raise TrustedFeedSourceConflict(
                "trusted feed item URL no longer matches direct-page canonical URL"
            )

        direct = base_module.extract_publication_evidence(body)
        if direct is not None:
            if trusted_feed.direct_evidence_conflicts(proof, direct.published_date):
                conflict = {
                    "reason": "trusted_feed_direct_publication_date_conflict",
                    "feed_published_date": proof.published_date.isoformat(),
                    "direct_published_date": direct.published_date.isoformat(),
                }
                raise TrustedFeedSourceConflict(
                    "direct page publication date contradicts trusted feed publication date"
                )
            return body, final_url, http_status

        fallback = {
            "trigger": "direct_page_has_no_publication_date",
            "http_status": http_status,
        }
        return (
            trusted_feed.synthetic_html(proof, title=title) + body,
            final_url,
            http_status,
        )

    record = base_module.verify_candidate(
        candidate,
        start_at=start_at,
        end_at=end_at,
        fetcher=wrapped_fetch,
        evidence_resolver=lambda body, requested, final: first_party_evidence(
            body, requested, final, fetcher
        ),
    )

    selected_source: dict[str, Any] | None = None
    for source in record.get("sources") or []:
        if not isinstance(source, dict):
            continue
        if trusted_feed.canonical_url(source.get("url")) == feed_identity:
            selected_source = source
            break

    if fallback is not None and selected_source is not None:
        selected_source["locator"] = (
            f"trusted_feed:{proof.source_id}:{proof.feed_date_field}"
        )
        selected_source["raw_date"] = proof.published_at.isoformat()
        selected_source["trusted_feed_publication_evidence"] = {
            **copy.deepcopy(fallback),
            "version": trusted_feed.VERSION,
            "source_id": proof.source_id,
            "feed_url": proof.feed_url,
            "item_url": proof.item_url,
            "feed_date_field": proof.feed_date_field,
            "published_at": proof.published_at.isoformat(),
            "feed_repolled": False,
        }
        candidate["source_freshness_evidence_kind"] = "trusted_first_party_feed"
        candidate["source_freshness_feed_source_id"] = proof.source_id
        candidate["source_freshness_feed_date_field"] = proof.feed_date_field
    elif conflict is not None:
        if selected_source is not None:
            selected_source["trusted_feed_conflict"] = copy.deepcopy(conflict)
        candidate["source_freshness_feed_conflict"] = copy.deepcopy(conflict)
        if record.get("status") == "excluded_unverified_freshness":
            candidate["freshness_reason"] = (
                "Source Freshness trusted-feed proof rejected fail-closed: "
                f"{conflict['reason']}."
            )

    record["trusted_feed_publication_evidence_used"] = fallback is not None
    record["trusted_feed_publication_conflict"] = copy.deepcopy(conflict)
    return record
