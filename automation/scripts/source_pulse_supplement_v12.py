#!/usr/bin/env python3
"""Source Pulse v1.2 regional repair without additional paid retrieval calls.

This module keeps the v1.1 safety contract but adds source-aware visible-date
recovery, bounded host-specific response caps, honest source-health diagnostics,
and Tier-A trusted-news promotion.  It never calls OpenAI or Web Search.
"""
from __future__ import annotations

import copy
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any, Callable

import source_freshness
import source_pulse
import source_pulse_supplement as v11
from source_pulse_shadow import build_fusion_diagnostics
from story_coverage import merge_candidates, read_json, write_json

SOURCE_PULSE_SUPPLEMENT_VERSION = 12
SOURCE_PULSE_REPORT_VERSION = v11.SOURCE_PULSE_REPORT_VERSION
SOURCE_PULSE_REPORT_STRATEGY = v11.SOURCE_PULSE_REPORT_STRATEGY
DEFAULT_OUTPUT_ROOT = v11.DEFAULT_OUTPUT_ROOT
DEFAULT_REGISTRY_PATH = v11.DEFAULT_REGISTRY_PATH

# Default remains exactly the v1 collector cap.  Larger caps are narrowly scoped
# to known first-party/news indexes that exceeded 1.5 MB in production.
_HOST_MAX_BYTES = {
    "ir.yandex.ru": 4_000_000,
    "yandex.ru": 3_000_000,
    "community.alibabacloud.com": 3_000_000,
    "tass.ru": 3_000_000,
}
_SOURCE_AWARE_HOSTS = {
    "ir.yandex.ru",
    "yandex.ru",
    "cnews.ru",
    "alibabagroup.com",
    "community.alibabacloud.com",
    "alibabacloud.com",
    "api-docs.deepseek.com",
    "mws.ru",
    "vk.company.ru",
    "tass.ru",
}
_RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_DATE_PATTERNS = (
    re.compile(r"\b(?P<d>\d{1,2})\s+(?P<m>января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(?P<y>20\d{2})(?:\s*г\.?)?", re.I),
    re.compile(r"\b(?P<d>\d{1,2})[./-](?P<m>\d{1,2})[./-](?P<y>20\d{2})\b"),
    re.compile(r"\b(?P<mname>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<d>\d{1,2}),\s*(?P<y>20\d{2})\b", re.I),
    re.compile(r"\b(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日\b"),
)
_EN_MONTHS = {name.casefold(): index for index, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), start=1
)}
_RELATIVE_RU = re.compile(r"\b(?P<rel>сегодня|вчера)(?:\s+(?P<h>\d{1,2}):(?P<minute>\d{2}))?\b", re.I)
_ANCHOR_RE = re.compile(r"<a\b[^>]*?href\s*=\s*[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<body>.*?)</a\s*>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(?:script|style)\b.*?</(?:script|style)\s*>", re.I | re.S)

_PARSER_REFERENCE_DATE: date | None = None
_PARSER_STATS: dict[str, dict[str, int]] = {}


def _host(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").casefold().strip(".")


def _max_bytes(url: str) -> int:
    host = _host(url)
    for allowed, value in _HOST_MAX_BYTES.items():
        if host == allowed or host.endswith("." + allowed):
            return value
    return source_pulse.MAX_BYTES


def fetch_source_v12(url: str, hosts: tuple[str, ...]) -> source_pulse.FetchOutcome:
    """Bounded HTTPS fetch with narrow per-host caps; anti-bot remains a gap."""
    safe = source_pulse.safe_url(url, hosts)
    host = _host(safe)
    try:
        source_pulse.ensure_public_dns(host)
    except source_pulse.SourcePulseError as exc:
        return source_pulse.FetchOutcome(safe, None, "error", None, None, str(exc), 0)
    opener = urllib.request.build_opener(source_pulse.SafeRedirect(hosts))
    started = time.monotonic()
    last: Exception | None = None
    cap = _max_bytes(safe)
    for index in range(source_pulse.ATTEMPTS):
        request = urllib.request.Request(
            safe,
            headers={
                "User-Agent": source_pulse.UA,
                "Accept": "application/rss+xml,application/atom+xml,text/html,*/*;q=0.1",
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with opener.open(request, timeout=source_pulse.TIMEOUT) as response:
                final_url = source_pulse.safe_url(response.geturl(), hosts)
                raw = response.read(cap + 1)
                if len(raw) > cap:
                    raise source_pulse.SourcePulseError(
                        f"response exceeds bounded host cap ({cap} bytes)"
                    )
                body = raw.decode(
                    response.headers.get_content_charset() or "utf-8", errors="replace"
                )
                return source_pulse.FetchOutcome(
                    safe,
                    final_url,
                    "ok",
                    int(getattr(response, "status", 200) or 200),
                    body,
                    None,
                    int((time.monotonic() - started) * 1000),
                )
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
            source_pulse.SourcePulseError,
        ) as exc:
            last = exc
            if index + 1 < source_pulse.ATTEMPTS:
                time.sleep(0.2)
    return source_pulse.FetchOutcome(
        safe,
        None,
        "error",
        getattr(last, "code", None),
        None,
        f"{type(last).__name__}: {last}",
        int((time.monotonic() - started) * 1000),
    )


def _text(raw: str) -> str:
    cleaned = _SCRIPT_STYLE_RE.sub(" ", raw)
    cleaned = _TAG_RE.sub(" ", cleaned)
    return " ".join(unescape(cleaned).split())


def _parse_visible_date(raw: str) -> tuple[date | None, datetime | None, str]:
    text = " ".join(unescape(raw).replace("\xa0", " ").split())
    match = _RELATIVE_RU.search(text)
    if match and _PARSER_REFERENCE_DATE is not None:
        day = _PARSER_REFERENCE_DATE - (timedelta(days=1) if match.group("rel").casefold() == "вчера" else timedelta())
        if match.group("h") is not None:
            # Exact timezone is intentionally not invented.  Date precision keeps
            # Source Freshness as the later publication authority.
            return day, None, "date"
        return day, None, "date"
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        groups = match.groupdict()
        try:
            year = int(groups["y"])
            day = int(groups["d"])
            if groups.get("mname"):
                month = _EN_MONTHS[groups["mname"].casefold()]
            elif groups.get("m") and not groups["m"].isdigit():
                month = _RU_MONTHS[groups["m"].casefold()]
            else:
                month = int(groups["m"])
            return date(year, month, day), None, "date"
        except (KeyError, TypeError, ValueError):
            continue
    return None, None, "unknown"


def _sequential_items(body: str, base: str) -> list[source_pulse.ParsedItem]:
    """Recover a date only from a small neighborhood around one headline link."""
    if _host(base) not in _SOURCE_AWARE_HOSTS:
        return []
    items: list[source_pulse.ParsedItem] = []
    for match in _ANCHOR_RE.finditer(body):
        title = _text(match.group("body"))
        if len(title) < 8:
            continue
        url = urllib.parse.urljoin(base, unescape(match.group("href")).strip())
        if not url.startswith("https://"):
            continue
        before = body[max(0, match.start() - 320):match.start()]
        after = body[match.end():min(len(body), match.end() + 420)]
        d_after, dt_after, precision_after = _parse_visible_date(_text(after))
        d_before, dt_before, precision_before = _parse_visible_date(_text(before))
        if d_after is not None:
            d, dt, precision = d_after, dt_after, precision_after
        else:
            d, dt, precision = d_before, dt_before, precision_before
        if d is None:
            continue
        items.append(source_pulse.ParsedItem(title, url, d, dt, precision, url))
    return source_pulse.dedupe(items)


def parse_html_index_v12(body: str, base: str) -> list[source_pulse.ParsedItem]:
    original = v11.parse_html_index_v11(body, base)
    recovered = _sequential_items(body, base)
    return source_pulse.dedupe([*original, *recovered])


def _parse_body_v12(
    src: source_pulse.SourceDefinition, body: str, base: str
) -> list[source_pulse.ParsedItem]:
    prefix = body.lstrip()[:200].casefold()
    xml = prefix.startswith("<?xml") or prefix.startswith("<rss") or prefix.startswith("<feed")
    if xml or (src.adapter == "rss_atom" and "<html" not in prefix and "<!doctype html" not in prefix):
        parsed = source_pulse.parse_rss(body, base)
        _PARSER_STATS[src.id] = {
            "parsed_items_before_v12": len(parsed),
            "parsed_items_after_v12": len(parsed),
            "dated_items_after_v12": sum(item.published_date is not None for item in parsed),
            "undated_items_after_v12": sum(item.published_date is None for item in parsed),
            "visible_dates_recovered": 0,
        }
        return parsed
    before = v11.parse_html_index_v11(body, base)
    after = parse_html_index_v12(body, base)
    before_dated = sum(item.published_date is not None for item in before)
    after_dated = sum(item.published_date is not None for item in after)
    _PARSER_STATS[src.id] = {
        "parsed_items_before_v12": len(before),
        "parsed_items_after_v12": len(after),
        "dated_items_after_v12": after_dated,
        "undated_items_after_v12": max(0, len(after) - after_dated),
        "visible_dates_recovered": max(0, after_dated - before_dated),
    }
    return after


def run_source_pulse_v12(**kwargs: Any) -> dict[str, Any]:
    global _PARSER_REFERENCE_DATE
    end_at = kwargs.get("end_at")
    _PARSER_REFERENCE_DATE = end_at.date() if isinstance(end_at, datetime) else None
    _PARSER_STATS.clear()
    original_parse_body = source_pulse.parse_body
    try:
        source_pulse.parse_body = _parse_body_v12
        snapshot = source_pulse.run_source_pulse(
            registry=kwargs["registry"],
            start_at=kwargs["start_at"],
            end_at=kwargs["end_at"],
            archive=kwargs.get("archive"),
            fetcher=kwargs.get("fetcher", fetch_source_v12),
            fetched_at=kwargs.get("fetched_at"),
        )
    finally:
        source_pulse.parse_body = original_parse_body
        _PARSER_REFERENCE_DATE = None
    snapshot = copy.deepcopy(snapshot)
    by_id = {str(row.get("source_id") or ""): row for row in snapshot.get("sources") or [] if isinstance(row, dict)}
    for source_id, stats in _PARSER_STATS.items():
        if source_id in by_id:
            by_id[source_id].update(stats)
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    degraded: list[str] = []
    for row in snapshot.get("sources") or []:
        if not isinstance(row, dict):
            continue
        if row.get("status") != "ok":
            degraded.append(str(row.get("source_id") or "unknown"))
            continue
        parsed = int(row.get("parsed_items_after_v12", row.get("parsed_items", 0)) or 0)
        dated = int(row.get("dated_items_after_v12", row.get("window_items", 0)) or 0)
        if parsed > 0 and dated == 0:
            degraded.append(str(row.get("source_id") or "unknown"))
    summary["degraded_source_ids"] = sorted(set(degraded))
    summary["source_health_status"] = "complete_with_gaps" if degraded else "complete"
    snapshot["summary"] = summary
    return snapshot


def _source_metadata(registry_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in registry_contract.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        source_id = str(raw.get("id") or "")
        if not source_id:
            continue
        result[source_id] = {
            "publisher": str(raw.get("publisher") or source_id.replace("_", " ").title()),
            "organization": str(raw.get("organization") or raw.get("publisher") or source_id.replace("_", " ").title()),
            "role": str(raw.get("role") or "lead_only"),
            "allowed_hosts": tuple(str(item) for item in raw.get("allowed_hosts") or []),
        }
    return result


def _candidate_from_lead(
    lead: dict[str, Any], *, publisher: str, organization: str, role: str,
    evidence: source_freshness.PublicationEvidence, summary_text: str,
) -> dict[str, Any]:
    candidate = v11._candidate_from_lead(
        lead,
        publisher=publisher,
        organization=organization,
        evidence=evidence,
        summary_text=summary_text,
    )
    candidate = copy.deepcopy(candidate)
    candidate["audit_direction"] = "source_pulse_v12"
    if role == "trusted_news":
        candidate["source_type"] = "news_agency"
        candidate["event_type"] = "source_pulse_trusted_news_update"
        candidate["verification_notes"] = candidate["verification_notes"].replace(
            "официальный Tier-A URL", "Tier-A trusted-news URL"
        ).replace("v1.1", "v1.2")
        candidate["freshness_reason"] = candidate["verification_notes"]
    else:
        candidate["verification_notes"] = candidate["verification_notes"].replace("v1.1", "v1.2")
        candidate["freshness_reason"] = candidate["verification_notes"]
    return candidate


def _final_host_allowed(final_url: str, allowed_hosts: tuple[str, ...]) -> bool:
    try:
        source_pulse.safe_url(final_url, allowed_hosts)
        return True
    except Exception:
        return False


def _report_status(snapshot: dict[str, Any]) -> str:
    summary = snapshot.get("summary") if isinstance(snapshot, dict) else None
    if not isinstance(summary, dict):
        return "complete_with_gaps"
    return "complete" if summary.get("source_health_status") == "complete" else "complete_with_gaps"


Collector = Callable[..., dict[str, Any]]
PageFetcher = Callable[[str], tuple[str, str, int]]


def run_source_pulse_supplement(
    *, research_path: Path, archive_path: Path, publication_date: str,
    output_root: Path = DEFAULT_OUTPUT_ROOT, registry_path: Path = DEFAULT_REGISTRY_PATH,
    maximum_candidates: int = 20, collector_fn: Collector = run_source_pulse_v12,
    page_fetcher: PageFetcher = source_freshness.fetch_source_html,
) -> dict[str, Any]:
    research = read_json(research_path)
    archive = read_json(archive_path)
    registry_contract = read_json(registry_path)
    if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
        raise RuntimeError("Source Pulse supplement: research artifact invalid")
    if not isinstance(archive, dict):
        raise RuntimeError("Source Pulse supplement: archive invalid")
    if registry_contract.get("production_integration") is not True:
        raise RuntimeError("Source Pulse supplement requires production_integration=true")
    if registry_contract.get("supplemental_candidate_influence") is not True:
        raise RuntimeError("Source Pulse supplement requires supplemental_candidate_influence=true")
    if registry_contract.get("repoll_on_recovery") is not False:
        raise RuntimeError("Source Pulse supplement requires repoll_on_recovery=false")

    window = research.get("search_window")
    if not isinstance(window, dict):
        raise RuntimeError("Source Pulse supplement: missing search_window")
    start_at = datetime.fromisoformat(str(window.get("start_at") or "").replace("Z", "+00:00"))
    end_at = datetime.fromisoformat(str(window.get("end_at") or "").replace("Z", "+00:00"))
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at < start_at:
        raise RuntimeError("Source Pulse supplement: invalid aware search window")

    output_root.mkdir(parents=True, exist_ok=True)
    prior = v11._prior_report(output_root, publication_date)
    reused_snapshot = prior is not None
    if prior is not None:
        snapshot = copy.deepcopy(prior["snapshot"])
    else:
        registry = source_pulse.load_registry(registry_path)
        snapshot = collector_fn(registry=registry, start_at=start_at, end_at=end_at, archive=archive)
    snapshot = copy.deepcopy(snapshot)
    snapshot["mode"] = "production_shadow"
    snapshot["production_integration"] = True
    snapshot["candidate_influence"] = False
    snapshot["repoll_on_recovery"] = False

    fusion = build_fusion_diagnostics(snapshot, research)
    metadata = _source_metadata(registry_contract)
    additions: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for row in fusion.get("pulse_leads") or []:
        if not isinstance(row, dict):
            continue
        record = {
            "source_id": row.get("source_id"),
            "title": row.get("title"),
            "url": row.get("url"),
            "tier": row.get("tier"),
            "region": row.get("region"),
            "role": row.get("role"),
            "fusion_disposition": row.get("disposition"),
            "promotion_status": "not_eligible",
            "reason": None,
        }
        if row.get("disposition") != "pulse_only":
            record["reason"] = f"fusion_{row.get('disposition')}"
            dispositions.append(record)
            continue
        role = str(row.get("role") or "")
        if row.get("tier") != "A" or role not in {"official", "trusted_news"}:
            record["reason"] = "tier_b_or_untrusted_lead_only"
            dispositions.append(record)
            continue
        title = str(row.get("title") or "")
        url = str(row.get("url") or "")
        try:
            body, final_url, http_status = page_fetcher(url)
            evidence = source_freshness.extract_publication_evidence(body)
        except Exception as exc:
            record["promotion_status"] = "rejected"
            record["reason"] = "source_fetch_error"
            record["error"] = f"{type(exc).__name__}: {exc}"
            dispositions.append(record)
            continue
        record["final_url"] = final_url
        record["http_status"] = http_status
        info = metadata.get(str(row.get("source_id") or ""), {})
        if role == "trusted_news" and not _final_host_allowed(
            final_url, tuple(info.get("allowed_hosts") or ())
        ):
            record["promotion_status"] = "rejected"
            record["reason"] = "trusted_news_redirect_outside_source_allowlist"
            dispositions.append(record)
            continue
        if evidence is None:
            record["promotion_status"] = "rejected"
            record["reason"] = "source_freshness_no_publication_date"
            dispositions.append(record)
            continue
        if not source_freshness.evidence_in_window(evidence, start_at=start_at, end_at=end_at):
            record["promotion_status"] = "rejected"
            record["reason"] = "source_freshness_outside_window"
            record["evidence_date"] = evidence.published_date.isoformat()
            dispositions.append(record)
            continue
        summary_text = v11._source_summary_text(body)
        if not v11._AI_RE.search(f"{title} {summary_text}"):
            record["promotion_status"] = "rejected"
            record["reason"] = "deterministic_ai_relevance_gate"
            dispositions.append(record)
            continue
        candidate = _candidate_from_lead(
            row,
            publisher=str(info.get("publisher") or row.get("source_id") or "Source Pulse"),
            organization=str(info.get("organization") or info.get("publisher") or row.get("source_id") or "Source Pulse"),
            role=role,
            evidence=evidence,
            summary_text=summary_text,
        )
        additions.append(candidate)
        record["promotion_status"] = "proposed"
        record["reason"] = f"tier_a_{role}_fresh_ai_relevant"
        record["evidence_locator"] = evidence.locator
        record["evidence_raw"] = evidence.raw
        dispositions.append(record)

    merged, accepted, rejected = merge_candidates(
        research, additions, maximum_candidates=maximum_candidates
    )
    accepted_urls = {
        str((item.get("primary_source") or {}).get("url") or "")
        for item in accepted if isinstance(item, dict)
    }
    for record in dispositions:
        if record.get("promotion_status") != "proposed":
            continue
        if str(record.get("url") or "") in accepted_urls:
            record["promotion_status"] = "promoted"
        else:
            record["promotion_status"] = "rejected"
            record["reason"] = "merge_validation_or_candidate_cap"
    if accepted:
        write_json(research_path, merged)

    final_research = merged if accepted else research
    final_fusion = build_fusion_diagnostics(snapshot, final_research)
    report = {
        "version": SOURCE_PULSE_REPORT_VERSION,
        "strategy": SOURCE_PULSE_REPORT_STRATEGY,
        "supplement_version": SOURCE_PULSE_SUPPLEMENT_VERSION,
        "publication_date": publication_date,
        "status": _report_status(snapshot),
        "state": "completed_supplemental",
        "candidate_influence": False,
        "supplemental_candidate_influence": True,
        "supplemental_policy": "tier_a_official_or_trusted_news_pulse_only_consider_after_deterministic_page_and_freshness_gate",
        "repoll_on_recovery": False,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "reused_snapshot": reused_snapshot,
        "snapshot": snapshot,
        "fusion": fusion,
        "fusion_pre_hybrid": fusion,
        "promotion": {
            "proposed_count": len(additions),
            "promoted_count": len(accepted),
            "rejected_by_merge_count": len(rejected),
            "candidate_count_before": len(research.get("candidates") or []),
            "candidate_count_after": len(final_research.get("candidates") or []),
            "accepted_candidate_urls": sorted(accepted_urls),
            "merge_rejections": copy.deepcopy(rejected),
            "lead_dispositions": dispositions,
        },
        "fusion_after_promotion": final_fusion,
        "error": None,
    }
    write_json(output_root / f"source-pulse-{publication_date}.json", report)
    return report


def compact_supplement_report(report: dict[str, Any]) -> dict[str, Any]:
    promotion = report.get("promotion") if isinstance(report, dict) else None
    snapshot = report.get("snapshot") if isinstance(report, dict) else None
    summary = snapshot.get("summary") if isinstance(snapshot, dict) else None
    return {
        "version": report.get("supplement_version") if isinstance(report, dict) else None,
        "status": report.get("status") if isinstance(report, dict) else None,
        "supplemental_candidate_influence": True,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "promoted_count": promotion.get("promoted_count") if isinstance(promotion, dict) else 0,
        "degraded_source_ids": summary.get("degraded_source_ids") if isinstance(summary, dict) else [],
        "reused_snapshot": report.get("reused_snapshot") if isinstance(report, dict) else False,
        "error": report.get("error") if isinstance(report, dict) else None,
    }
