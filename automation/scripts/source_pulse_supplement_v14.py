#!/usr/bin/env python3
"""Source Pulse v1.4: trusted first-party feed publication fallback over v1.3.

P1 keeps v1.3/Yandex behavior intact and adds one narrow fallback for explicitly
approved Tier-A official RSS/Atom sources. The feed is collected by the existing
Source Pulse request; this layer never repolls it and adds zero OpenAI/Web Search
calls. Direct page metadata remains authoritative. A redirect/identity mismatch
or a contradictory direct publication date fails closed.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import source_freshness
import source_pulse
import source_pulse_supplement_v13 as v13
import trusted_feed_publication as trusted_feed
from story_coverage import read_json, write_json

SOURCE_PULSE_SUPPLEMENT_VERSION = 14
SOURCE_PULSE_REPORT_VERSION = v13.SOURCE_PULSE_REPORT_VERSION
SOURCE_PULSE_REPORT_STRATEGY = v13.SOURCE_PULSE_REPORT_STRATEGY
DEFAULT_OUTPUT_ROOT = v13.DEFAULT_OUTPUT_ROOT
DEFAULT_REGISTRY_PATH = v13.DEFAULT_REGISTRY_PATH

Collector = Callable[..., dict[str, Any]]
PageFetcher = Callable[[str], tuple[str, str, int]]


class TrustedFeedPageConflict(RuntimeError):
    """Direct page behavior contradicts the saved trusted-feed identity/date."""


def _window(research: dict[str, Any]) -> tuple[datetime, datetime]:
    raw = research.get("search_window") if isinstance(research, dict) else None
    if not isinstance(raw, dict):
        raise RuntimeError("Source Pulse v1.4 requires research search_window")
    start_at = datetime.fromisoformat(str(raw.get("start_at") or "").replace("Z", "+00:00"))
    end_at = datetime.fromisoformat(str(raw.get("end_at") or "").replace("Z", "+00:00"))
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at < start_at:
        raise RuntimeError("Source Pulse v1.4 requires a valid aware search_window")
    return start_at, end_at


def _annotate_feed_fields(
    snapshot: dict[str, Any], field_by_url: dict[str, str]
) -> dict[str, Any]:
    fixed = copy.deepcopy(snapshot)
    changed = False
    for row in fixed.get("leads") or []:
        if not isinstance(row, dict):
            continue
        identity = trusted_feed.canonical_url(row.get("url"))
        kind = field_by_url.get(identity or "")
        if kind:
            row["publication_evidence_kind"] = kind
            changed = True
    fixed["collector_version"] = SOURCE_PULSE_SUPPLEMENT_VERSION
    if changed:
        # v1.3 already owns the canonical snapshot hash routine used by recovery.
        fixed["snapshot_hash"] = v13._snapshot_hash(fixed)
    return fixed


def run_source_pulse_supplement(
    *,
    research_path: Path,
    archive_path: Path,
    publication_date: str,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    maximum_candidates: int = 20,
    collector_fn: Collector = v13.run_source_pulse_v13,
    page_fetcher: PageFetcher = source_freshness.fetch_source_html,
) -> dict[str, Any]:
    research = read_json(research_path)
    start_at, end_at = _window(research)
    registry_contract = read_json(registry_path)
    if not isinstance(registry_contract, dict):
        raise RuntimeError("Source Pulse v1.4 registry invalid")

    evidence_by_url: dict[str, dict[str, Any]] = {}
    proof_by_url: dict[str, trusted_feed.TrustedFeedProof] = {}
    title_by_url: dict[str, str] = {}
    field_by_url: dict[str, str] = {}
    fallbacks: dict[str, dict[str, Any]] = {}
    conflicts: dict[str, dict[str, Any]] = {}

    def capture_snapshot(snapshot: dict[str, Any]) -> None:
        for raw in snapshot.get("leads") or []:
            if not isinstance(raw, dict):
                continue
            evidence = trusted_feed.build_evidence(raw, registry_contract)
            if evidence is None:
                continue
            identity = trusted_feed.canonical_url(raw.get("url"))
            if identity is None:
                continue
            stub = {
                "primary_source": {"url": identity},
                "trusted_feed_publication_evidence": evidence,
            }
            proof = trusted_feed.validate_evidence(stub, registry_contract)
            if proof is None:
                continue
            evidence_by_url[identity] = evidence
            proof_by_url[identity] = proof
            title_by_url[identity] = " ".join(str(raw.get("title") or "").split())

    def capturing_collector(**kwargs: Any) -> dict[str, Any]:
        original_parse_rss = source_pulse.parse_rss

        def capture_parse_rss(body: str, base: str):
            rows = original_parse_rss(body, base)
            field_by_url.update(trusted_feed.feed_publication_fields(body, base))
            return rows

        source_pulse.parse_rss = capture_parse_rss
        try:
            snapshot = collector_fn(**kwargs)
        finally:
            source_pulse.parse_rss = original_parse_rss
        snapshot = _annotate_feed_fields(snapshot, field_by_url)
        capture_snapshot(snapshot)
        return snapshot

    def feed_aware_page_fetcher(url: str) -> tuple[str, str, int]:
        identity = trusted_feed.canonical_url(url)
        proof = proof_by_url.get(identity or "")
        title = title_by_url.get(identity or "", "")
        try:
            body, final_url, http_status = page_fetcher(url)
        except Exception as exc:
            if proof is None or not trusted_feed.proof_in_window(
                proof, start_at=start_at, end_at=end_at
            ):
                raise
            fallbacks[proof.item_url] = {
                "trigger": "direct_fetch_error",
                "error": f"{type(exc).__name__}: {exc}",
            }
            return trusted_feed.synthetic_html(proof, title=title), proof.item_url, 200

        if proof is None:
            return body, final_url, http_status
        final_identity = trusted_feed.canonical_url(final_url)
        if final_identity != proof.item_url:
            conflicts[proof.item_url] = {
                "reason": "trusted_feed_redirect_or_canonical_mismatch",
                "final_url": final_url,
            }
            raise TrustedFeedPageConflict(
                "trusted feed item URL no longer matches direct-page canonical URL"
            )

        direct = source_freshness.extract_publication_evidence(body)
        if direct is not None:
            if trusted_feed.direct_evidence_conflicts(proof, direct.published_date):
                conflicts[proof.item_url] = {
                    "reason": "trusted_feed_direct_publication_date_conflict",
                    "feed_published_date": proof.published_date.isoformat(),
                    "direct_published_date": direct.published_date.isoformat(),
                }
                raise TrustedFeedPageConflict(
                    "direct page publication date contradicts trusted feed publication date"
                )
            return body, final_url, http_status

        if not trusted_feed.proof_in_window(proof, start_at=start_at, end_at=end_at):
            return body, final_url, http_status
        fallbacks[proof.item_url] = {
            "trigger": "direct_page_has_no_publication_date",
            "http_status": http_status,
        }
        return (
            trusted_feed.synthetic_html(proof, title=title) + body,
            final_url,
            http_status,
        )

    original_prior = v13.v12.v11._prior_report

    def capturing_prior(root: Path, day: str) -> dict[str, Any] | None:
        prior = original_prior(root, day)
        if prior is not None and isinstance(prior.get("snapshot"), dict):
            capture_snapshot(prior["snapshot"])
        return prior

    v13.v12.v11._prior_report = capturing_prior
    try:
        report = v13.run_source_pulse_supplement(
            research_path=research_path,
            archive_path=archive_path,
            publication_date=publication_date,
            output_root=output_root,
            registry_path=registry_path,
            maximum_candidates=maximum_candidates,
            collector_fn=capturing_collector,
            page_fetcher=feed_aware_page_fetcher,
        )
    finally:
        v13.v12.v11._prior_report = original_prior

    result = copy.deepcopy(report)
    result["supplement_version"] = SOURCE_PULSE_SUPPLEMENT_VERSION
    snapshot = result.get("snapshot")
    if isinstance(snapshot, dict):
        snapshot = _annotate_feed_fields(snapshot, field_by_url)
        result["snapshot"] = snapshot
        capture_snapshot(snapshot)

    accepted_urls = {
        trusted_feed.canonical_url(value)
        for value in (result.get("promotion") or {}).get("accepted_candidate_urls") or []
    }
    accepted_urls.discard(None)
    research_after = read_json(research_path)
    annotated_candidates = 0
    if isinstance(research_after, dict) and isinstance(research_after.get("candidates"), list):
        changed = False
        for candidate in research_after["candidates"]:
            if not isinstance(candidate, dict):
                continue
            primary = candidate.get("primary_source")
            url = trusted_feed.canonical_url(
                primary.get("url") if isinstance(primary, dict) else None
            )
            evidence = evidence_by_url.get(url or "")
            if url not in accepted_urls or evidence is None:
                continue
            candidate["trusted_feed_publication_evidence"] = copy.deepcopy(evidence)
            note = (
                "Trusted first-party feed publication evidence v1: "
                f"source={evidence['source_id']}; field={evidence['feed_date_field']}; "
                f"published_at={evidence['published_at']}; exact same-host item URL."
            )
            previous = str(candidate.get("verification_notes") or "").strip()
            if note not in previous:
                candidate["verification_notes"] = f"{note} {previous}".strip()
                candidate["freshness_reason"] = candidate["verification_notes"]
            annotated_candidates += 1
            changed = True
        if changed:
            write_json(research_path, research_after)

    for record in (result.get("promotion") or {}).get("lead_dispositions") or []:
        if not isinstance(record, dict):
            continue
        identity = trusted_feed.canonical_url(record.get("url"))
        if identity in conflicts:
            record["reason"] = conflicts[identity]["reason"]
            record["trusted_feed_publication_evidence"] = copy.deepcopy(conflicts[identity])
            continue
        if identity in fallbacks:
            detail = copy.deepcopy(fallbacks[identity])
            evidence = evidence_by_url.get(identity or "")
            if evidence is not None:
                detail.update(
                    {
                        "source_id": evidence["source_id"],
                        "feed_date_field": evidence["feed_date_field"],
                        "published_at": evidence["published_at"],
                    }
                )
                record["evidence_locator"] = (
                    f"trusted_feed:{evidence['source_id']}:{evidence['feed_date_field']}"
                )
                record["evidence_raw"] = evidence["published_at"]
            record["trusted_feed_publication_evidence"] = detail
            if record.get("promotion_status") in {"proposed", "promoted"}:
                record["reason"] = "tier_a_official_trusted_feed_fallback_fresh_ai_relevant"

    result["trusted_feed_publication_evidence"] = {
        "version": trusted_feed.VERSION,
        "strategy": "same_host_exact_item_saved_feed_publication_fallback",
        "trusted_source_ids": sorted(trusted_feed.TRUSTED_SOURCE_FIELDS),
        "saved_proof_count": len(proof_by_url),
        "fallback_count": len(fallbacks),
        "direct_fetch_error_fallback_count": sum(
            row.get("trigger") == "direct_fetch_error" for row in fallbacks.values()
        ),
        "undated_page_fallback_count": sum(
            row.get("trigger") == "direct_page_has_no_publication_date"
            for row in fallbacks.values()
        ),
        "conflict_rejection_count": len(conflicts),
        "annotated_candidate_count": annotated_candidates,
        "feed_repolled_for_fallback": False,
        "paid_api_calls": 0,
        "web_search_operations": 0,
    }
    result["supplemental_policy"] = (
        "tier_a_official_or_trusted_news_pulse_only_consider_after_deterministic_"
        "page_freshness_or_strict_saved_first_party_feed_proof"
    )
    write_json(output_root / f"source-pulse-{publication_date}.json", result)
    return result


def compact_supplement_report(report: dict[str, Any]) -> dict[str, Any]:
    compact = v13.compact_supplement_report(report)
    compact = copy.deepcopy(compact)
    compact["version"] = SOURCE_PULSE_SUPPLEMENT_VERSION
    compact["trusted_feed_publication_evidence"] = copy.deepcopy(
        report.get("trusted_feed_publication_evidence") or {}
    )
    return compact
