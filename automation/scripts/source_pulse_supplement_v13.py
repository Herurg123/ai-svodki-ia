#!/usr/bin/env python3
"""Source Pulse v1.3: narrow Yandex publication-date repair over v1.2.

The generic Source Freshness parser intentionally remains machine-readable only.
This wrapper repairs the Yandex IR/company-news surface with two independent
first-party signals: the stable dated Yandex URL/id and a matching visible page
or index date. It adds no OpenAI or Web Search calls and preserves v1.2 for
rollback/replay compatibility.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import urllib.parse
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import source_freshness
import source_pulse
import source_pulse_supplement_v12 as v12
from story_coverage import read_json, write_json

SOURCE_PULSE_SUPPLEMENT_VERSION = 13
SOURCE_PULSE_REPORT_VERSION = v12.SOURCE_PULSE_REPORT_VERSION
SOURCE_PULSE_REPORT_STRATEGY = v12.SOURCE_PULSE_REPORT_STRATEGY
DEFAULT_OUTPUT_ROOT = v12.DEFAULT_OUTPUT_ROOT
DEFAULT_REGISTRY_PATH = v12.DEFAULT_REGISTRY_PATH
_V12_PARSE_HTML_INDEX = v12.parse_html_index_v12

_YANDEX_ID_RE = re.compile(r"^(?P<d>\d{2})-(?P<m>\d{2})-(?P<y>20\d{2})(?:-\d+)?$")
_YANDEX_NEWS_PATH_RE = re.compile(
    r"^/company/news/(?P<d>\d{2})-(?P<m>\d{2})-(?P<y>20\d{2})(?:-\d+)?/?$",
    re.I,
)
_RU_MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
_YANDEX_INDEX_STATS: dict[str, dict[str, int]] = {}


def _valid_date(day: str, month: str, year: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def yandex_url_date(url: str) -> date | None:
    """Return the first-party calendar date encoded by an approved Yandex URL."""
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold().strip(".")
    if host == "ir.yandex.ru" and parsed.path.rstrip("/") == "/press-releases":
        values = urllib.parse.parse_qs(parsed.query, keep_blank_values=False).get("id") or []
        if len(values) != 1:
            return None
        match = _YANDEX_ID_RE.fullmatch(values[0])
        return _valid_date(match["d"], match["m"], match["y"]) if match else None
    if host == "yandex.ru" or host.endswith(".yandex.ru"):
        match = _YANDEX_NEWS_PATH_RE.fullmatch(parsed.path)
        return _valid_date(match["d"], match["m"], match["y"]) if match else None
    return None


def _visible_forms(value: date) -> tuple[re.Pattern[str], ...]:
    month = _RU_MONTHS_GENITIVE[value.month - 1]
    return (
        re.compile(rf"(?<!\d){value.day}\s+{month}\s+{value.year}(?:\s*г\.?)?(?!\d)", re.I),
        re.compile(rf"(?<!\d)0?{value.day}[./-]0?{value.month}[./-]{value.year}(?!\d)"),
        re.compile(rf"(?<!\d){value.year}-0?{value.month}-0?{value.day}(?!\d)"),
    )


def visible_yandex_date_matches(body_or_text: str, expected: date, *, html: bool = True) -> bool:
    """Corroborate the URL date only near the beginning of a Yandex page/item."""
    text = v12._text(body_or_text) if html else " ".join(str(body_or_text).split())
    # Bound the scan to the article/index neighborhood. Generic full-body date
    # scraping is deliberately forbidden because related links contain dates too.
    prefix = text[:12000]
    return any(pattern.search(prefix) for pattern in _visible_forms(expected))


def extract_yandex_publication_evidence(
    body: str, final_url: str, *, requested_url: str | None = None
) -> source_freshness.PublicationEvidence | None:
    """Use Yandex URL date only when the visible first-party page agrees."""
    url = final_url
    expected = yandex_url_date(url)
    if expected is None and requested_url:
        url = requested_url
        expected = yandex_url_date(url)
    if expected is None or not visible_yandex_date_matches(body, expected):
        return None
    raw = f"{expected.day} {_RU_MONTHS_GENITIVE[expected.month - 1]} {expected.year}"
    return source_freshness.PublicationEvidence(
        raw=raw,
        published_date=expected,
        published_at=None,
        time_precision="date",
        locator="yandex:url+visible-date",
        confidence_rank=25,
    )


def _item_with_date(item: source_pulse.ParsedItem, expected: date) -> source_pulse.ParsedItem:
    return replace(
        item,
        published_date=expected,
        published_at=None,
        time_precision="date",
    )


def _item_without_date(item: source_pulse.ParsedItem) -> source_pulse.ParsedItem:
    return replace(item, published_date=None, published_at=None, time_precision="unknown")


def _sequential_date_map(body: str, base: str) -> dict[str, set[date]]:
    result: dict[str, set[date]] = {}
    for item in v12._sequential_items(body, base):
        if item.published_date is None:
            continue
        result.setdefault(source_pulse.norm_url(item.url), set()).add(item.published_date)
    return result


def parse_html_index_v13(body: str, base: str) -> list[source_pulse.ParsedItem]:
    """Repair only corroborated Yandex dates and collapse duplicate Yandex URLs."""
    parent_parser = v12.parse_html_index_v12
    if parent_parser is parse_html_index_v13:
        parent_parser = _V12_PARSE_HTML_INDEX
    original = parent_parser(body, base)
    if (urllib.parse.urlsplit(base).hostname or "").casefold() not in {"ir.yandex.ru", "yandex.ru"}:
        return original

    sequential = _sequential_date_map(body, base)
    repaired: list[source_pulse.ParsedItem] = []
    seen_yandex_urls: set[str] = set()
    corrected = conflicts_nulled = duplicates_collapsed = 0

    for item in original:
        expected = yandex_url_date(item.url)
        if expected is None:
            repaired.append(item)
            continue
        normalized = source_pulse.norm_url(item.url)
        if normalized in seen_yandex_urls:
            duplicates_collapsed += 1
            continue
        seen_yandex_urls.add(normalized)

        title_confirms = visible_yandex_date_matches(item.title, expected, html=False)
        neighbor_confirms = expected in sequential.get(normalized, set())
        existing_confirms = item.published_date == expected
        corroborated = title_confirms or neighbor_confirms or existing_confirms

        if corroborated:
            if item.published_date != expected or item.published_at is not None:
                corrected += 1
            repaired.append(_item_with_date(item, expected))
        elif item.published_date is not None and item.published_date != expected:
            # A non-null parser date is not allowed to overrule a conflicting
            # Yandex article id without a second confirming signal.
            conflicts_nulled += 1
            repaired.append(_item_without_date(item))
        else:
            repaired.append(item)

    _YANDEX_INDEX_STATS[base] = {
        "yandex_dates_corrected_v13": corrected,
        "yandex_conflicts_nulled_v13": conflicts_nulled,
        "yandex_duplicate_urls_collapsed_v13": duplicates_collapsed,
    }
    return source_pulse.dedupe(repaired)


def _snapshot_hash(snapshot: dict[str, Any]) -> str:
    source_health = []
    for row in snapshot.get("sources") or []:
        if not isinstance(row, dict):
            continue
        source_health.append({
            "source_id": row.get("source_id"),
            "status": row.get("status"),
            "selected_url": row.get("selected_url"),
            "parsed_items": row.get("parsed_items"),
            "window_items": row.get("window_items"),
            "accepted_leads": row.get("accepted_leads"),
            "attempts": [
                {"url": a.get("url"), "status": a.get("status"), "http_status": a.get("http_status")}
                for a in row.get("attempts") or [] if isinstance(a, dict)
            ],
        })
    canonical = json.dumps(
        {
            "version": snapshot.get("version"),
            "window": snapshot.get("window"),
            "sources": source_health,
            "leads": snapshot.get("leads") or [],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def repair_saved_yandex_snapshot(
    snapshot: dict[str, Any], *, start_at: datetime, end_at: datetime
) -> tuple[dict[str, Any], dict[str, int]]:
    """Normalize a saved v1.2 snapshot without repolling mutable sources."""
    fixed = copy.deepcopy(snapshot)
    kept: list[dict[str, Any]] = []
    corrected = filtered_outside = ambiguous = 0
    yandex_kept = 0

    for raw in fixed.get("leads") or []:
        if not isinstance(raw, dict):
            continue
        row = copy.deepcopy(raw)
        expected = yandex_url_date(str(row.get("url") or ""))
        if expected is None:
            kept.append(row)
            continue
        title_confirms = visible_yandex_date_matches(str(row.get("title") or ""), expected, html=False)
        if not title_confirms and str(row.get("published_date") or "") != expected.isoformat():
            ambiguous += 1
            continue
        if str(row.get("published_date") or "") != expected.isoformat():
            corrected += 1
        item = source_pulse.ParsedItem(
            str(row.get("title") or ""),
            str(row.get("url") or ""),
            expected,
            None,
            "date",
            str(row.get("source_item_id") or row.get("url") or ""),
        )
        inside, cutoff_ambiguous = source_pulse.within(item, start_at, end_at)
        if not inside:
            filtered_outside += 1
            continue
        row["published_date"] = expected.isoformat()
        row["published_at"] = None
        row["time_precision"] = "date"
        row["cutoff_ambiguous"] = cutoff_ambiguous
        row["event_fingerprint"] = source_pulse.event_fingerprint(row["title"], expected)
        row["exact_fingerprint"] = source_pulse.exact_fp(row["title"], row["url"], expected)
        kept.append(row)
        yandex_kept += 1

    fixed["leads"] = kept
    for source in fixed.get("sources") or []:
        if isinstance(source, dict) and source.get("source_id") == "yandex_ir":
            source["window_items"] = yandex_kept
            source["accepted_leads"] = yandex_kept
            source["yandex_saved_snapshot_repaired_v13"] = corrected
            source["yandex_saved_snapshot_filtered_v13"] = filtered_outside

    summary = fixed.get("summary") if isinstance(fixed.get("summary"), dict) else {}
    summary["lead_count"] = len(kept)
    summary["eligible_new_lead_count"] = sum(
        not bool(row.get("cutoff_ambiguous")) and not bool(row.get("archive_url_duplicate"))
        for row in kept
    )
    summary["tier_a_leads"] = sum(row.get("tier") == "A" for row in kept)
    summary["tier_b_leads"] = sum(row.get("tier") == "B" for row in kept)
    summary["cutoff_ambiguous_leads"] = sum(bool(row.get("cutoff_ambiguous")) for row in kept)
    summary["archive_url_duplicates"] = sum(bool(row.get("archive_url_duplicate")) for row in kept)
    fixed["summary"] = summary
    fixed["snapshot_hash"] = _snapshot_hash(fixed)
    stats = {
        "saved_snapshot_dates_corrected": corrected,
        "saved_snapshot_rows_filtered_outside_window": filtered_outside,
        "saved_snapshot_rows_ambiguous": ambiguous,
    }
    return fixed, stats


def run_source_pulse_v13(**kwargs: Any) -> dict[str, Any]:
    """Fresh v1.3 collector: same transport, v1.3 Yandex index parser."""
    _YANDEX_INDEX_STATS.clear()
    original = v12.parse_html_index_v12
    v12.parse_html_index_v12 = parse_html_index_v13
    try:
        snapshot = v12.run_source_pulse_v12(**kwargs)
    finally:
        v12.parse_html_index_v12 = original
    snapshot = copy.deepcopy(snapshot)
    for source in snapshot.get("sources") or []:
        if not isinstance(source, dict):
            continue
        selected = str(source.get("selected_url") or "")
        stats = _YANDEX_INDEX_STATS.get(selected)
        if stats:
            source.update(stats)
    snapshot["collector_version"] = SOURCE_PULSE_SUPPLEMENT_VERSION
    return snapshot


Collector = Callable[..., dict[str, Any]]
PageFetcher = Callable[[str], tuple[str, str, int]]


def run_source_pulse_supplement(
    *, research_path: Path, archive_path: Path, publication_date: str,
    output_root: Path = DEFAULT_OUTPUT_ROOT, registry_path: Path = DEFAULT_REGISTRY_PATH,
    maximum_candidates: int = 20, collector_fn: Collector = run_source_pulse_v13,
    page_fetcher: PageFetcher = source_freshness.fetch_source_html,
) -> dict[str, Any]:
    research = read_json(research_path)
    window = research.get("search_window") if isinstance(research, dict) else None
    if not isinstance(window, dict):
        raise RuntimeError("Source Pulse v1.3 requires research search_window")
    start_at = datetime.fromisoformat(str(window.get("start_at") or "").replace("Z", "+00:00"))
    end_at = datetime.fromisoformat(str(window.get("end_at") or "").replace("Z", "+00:00"))
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at < start_at:
        raise RuntimeError("Source Pulse v1.3 requires a valid aware search_window")

    fallback_by_url: dict[str, dict[str, Any]] = {}
    saved_stats = {
        "saved_snapshot_dates_corrected": 0,
        "saved_snapshot_rows_filtered_outside_window": 0,
        "saved_snapshot_rows_ambiguous": 0,
    }

    def wrapped_page_fetcher(url: str) -> tuple[str, str, int]:
        body, final_url, status = page_fetcher(url)
        if source_freshness.extract_publication_evidence(body) is not None:
            return body, final_url, status
        fallback = extract_yandex_publication_evidence(body, final_url, requested_url=url)
        if fallback is None:
            return body, final_url, status
        marker = f'<meta name="datePublished" content="{fallback.published_date.isoformat()}">'
        detail = {
            "locator": fallback.locator,
            "raw": fallback.raw,
            "published_date": fallback.published_date.isoformat(),
        }
        fallback_by_url[source_pulse.norm_url(url)] = detail
        fallback_by_url[source_pulse.norm_url(final_url)] = detail
        return marker + body, final_url, status

    original_prior = v12.v11._prior_report

    def repaired_prior(root: Path, day: str) -> dict[str, Any] | None:
        nonlocal saved_stats
        prior = original_prior(root, day)
        if prior is None:
            return None
        fixed = copy.deepcopy(prior)
        fixed_snapshot, saved_stats = repair_saved_yandex_snapshot(
            fixed["snapshot"], start_at=start_at, end_at=end_at
        )
        fixed["snapshot"] = fixed_snapshot
        return fixed

    v12.v11._prior_report = repaired_prior
    try:
        report = v12.run_source_pulse_supplement(
            research_path=research_path,
            archive_path=archive_path,
            publication_date=publication_date,
            output_root=output_root,
            registry_path=registry_path,
            maximum_candidates=maximum_candidates,
            collector_fn=collector_fn,
            page_fetcher=wrapped_page_fetcher,
        )
    finally:
        v12.v11._prior_report = original_prior

    result = copy.deepcopy(report)
    result["supplement_version"] = SOURCE_PULSE_SUPPLEMENT_VERSION
    result["yandex_date_repair"] = {
        "version": 1,
        "strategy": "dated_yandex_url_plus_matching_visible_date",
        "generic_source_freshness_parser_changed": False,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "direct_page_fallback_count": len({id(v): v for v in fallback_by_url.values()}),
        **saved_stats,
    }
    for record in (result.get("promotion") or {}).get("lead_dispositions") or []:
        if not isinstance(record, dict):
            continue
        detail = fallback_by_url.get(source_pulse.norm_url(str(record.get("url") or "")))
        if detail is None:
            detail = fallback_by_url.get(source_pulse.norm_url(str(record.get("final_url") or "")))
        if detail is not None:
            record["evidence_locator"] = detail["locator"]
            record["evidence_raw"] = detail["raw"]
            record["yandex_date_repair"] = True
    write_json(output_root / f"source-pulse-{publication_date}.json", result)
    return result


def compact_supplement_report(report: dict[str, Any]) -> dict[str, Any]:
    compact = v12.compact_supplement_report(report)
    compact = copy.deepcopy(compact)
    compact["version"] = SOURCE_PULSE_SUPPLEMENT_VERSION
    compact["yandex_date_repair"] = copy.deepcopy(report.get("yandex_date_repair") or {})
    return compact
