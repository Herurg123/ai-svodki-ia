"""Conservative, offline joins between saved Pulse and final release artifacts."""
from __future__ import annotations

from typing import Any


def primary_url(candidate: dict[str, Any]) -> str | None:
    primary = candidate.get("primary_source")
    return primary.get("url") if isinstance(primary, dict) and isinstance(primary.get("url"), str) else None


def source_urls(candidate: dict[str, Any]) -> set[str]:
    values = [candidate.get("primary_source"), *(candidate.get("supporting_sources") or [])]
    return {v["url"] for v in values if isinstance(v, dict) and isinstance(v.get("url"), str)}


def story_matches(candidate: dict[str, Any], story: dict[str, Any]) -> bool:
    """An ID alone can be recycled by a later editorial run."""
    fields = ("organization", "topic", "event_type", "published_date", "published_at")
    return bool(
        candidate.get("id") == story.get("candidate_id")
        and all(k in candidate and k in story and candidate[k] == story[k] for k in fields)
        and source_urls(candidate).intersection(
            v["url"] for v in story.get("sources", [])
            if isinstance(v, dict) and isinstance(v.get("url"), str)
        )
    )


def editorial_evidence(
    candidates: list[dict[str, Any]], editorial: Any, stories: Any, publication_date: str
) -> tuple[set[str] | None, list[str]]:
    """Validate the complete ID partition and all selected story identities."""
    if not isinstance(editorial, dict) or not isinstance(stories, list):
        return None, ["editorial_or_stories_missing"]
    digest = editorial.get("digest")
    if editorial.get("status") != "ok" or not isinstance(digest, dict) or digest.get("date") != publication_date:
        return None, ["editorial_status_or_date_mismatch"]
    selected, excluded = editorial.get("selected_candidate_ids"), editorial.get("excluded_candidate_ids")
    ids = [c.get("id") for c in candidates]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        return None, ["candidate_ids_missing_or_duplicated"]
    if any(not isinstance(v, list) or any(not isinstance(i, str) for i in v) for v in (selected, excluded)):
        return None, ["editorial_partition_missing"]
    if (len(set(selected)) != len(selected) or len(set(excluded)) != len(excluded)
            or set(selected) & set(excluded) or set(selected) | set(excluded) != set(ids)):
        return None, ["editorial_partition_conflict"]
    story_ids = [s.get("candidate_id") if isinstance(s, dict) else None for s in stories]
    if any(not isinstance(i, str) for i in story_ids) or len(set(story_ids)) != len(story_ids) or set(story_ids) != set(selected):
        return None, ["selected_story_ids_conflict"]
    by_id = {c["id"]: c for c in candidates}
    if any(not story_matches(by_id[s["candidate_id"]], s) for s in stories):
        return None, ["selected_story_identity_conflict"]
    return set(selected), []


def add_trace(report: dict[str, Any], pulse: dict[str, Any], bundle: dict[str, Any]) -> None:
    """Attach diagnostics to a newly built report; never edit source artifacts."""
    research = bundle.get("candidates")
    date = report.get("publication_date")
    if not isinstance(research, dict) or research.get("publication_date") != date or not isinstance(research.get("candidates"), list):
        report["evidence_gaps"].append("candidate_artifact_missing_or_date_mismatch")
        return
    candidates = research["candidates"]
    if any(not isinstance(c, dict) for c in candidates):
        report["evidence_gaps"].append("candidate_rows_malformed")
        return
    selected, gaps = editorial_evidence(candidates, bundle.get("editorial"), bundle.get("stories"), date)
    report["evidence_gaps"].extend(gaps)
    promoted = (pulse.get("promotion") or {}).get("lead_dispositions") or []
    report["trace_scope"] = "Final saved candidate state and assembled stories; not FTP delivery or proof of publication."
    for row in report["sources"]:
        urls = row["confirmed_promoted_urls"]
        row["candidate_trace"] = []
        if urls is None or not row["promotion_evidence_complete"]:
            continue
        freshness, selection = [], []
        for url in urls:
            decisions = [d for d in promoted if isinstance(d, dict) and d.get("source_id") == row["source_id"] and d.get("url") == url and d.get("promotion_status") == "promoted"]
            matches = [c for c in candidates if primary_url(c) == url]
            candidate = matches[0] if len(matches) == 1 else None
            title = decisions[0].get("title") if len(decisions) == 1 else None
            proven = (candidate is not None and isinstance(title, str) and bool(title)
                      and candidate.get("title") == title
                      and str(candidate.get("audit_direction", "")).startswith("source_pulse_"))
            if not proven:
                row["candidate_trace"].append({"url": url, "status": "identity_unresolved"})
                report["evidence_gaps"].append(f"pulse_candidate_identity_unresolved:{row['source_id']}:{url}")
                freshness.append(None)
                selection.append(None)
                continue
            source_state = candidate.get("source_freshness_status")
            event_state = candidate.get("event_freshness_status")
            fresh = (False if event_state == "stale" else True if source_state == "fresh" and event_state in {"fresh", "unknown"} else None)
            chosen = candidate.get("id") in selected if selected is not None else None
            freshness.append(fresh)
            selection.append(chosen)
            row["candidate_trace"].append({
                "url": url, "candidate_id": candidate.get("id"), "status": "exact_candidate_matched",
                "source_freshness_status": source_state, "event_freshness_status": event_state,
                "recommendation": candidate.get("recommendation"),
                "verification_status": candidate.get("verification_status"),
                "freshness_reason": candidate.get("freshness_reason"),
                "editorial_selected": chosen,
            })
        row["post_freshness_survivors"] = sum(freshness) if all(v is not None for v in freshness) else None
        row["editorial_selected"] = sum(selection) if selected is not None and all(v is not None for v in selection) else None
        row["assembled_stories"] = row["editorial_selected"]
    report["unobserved_stages"] = ["publication"]
    if any(r["post_freshness_survivors"] is None for r in report["sources"]):
        report["unobserved_stages"].append("post_freshness")
    if any(r["editorial_selected"] is None for r in report["sources"]):
        report["unobserved_stages"].append("editorial_selection")
    report["evidence_gaps"] = sorted(set(report["evidence_gaps"]))
