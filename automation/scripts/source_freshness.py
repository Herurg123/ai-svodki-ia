#!/usr/bin/env python3
"""Deterministically verify publication freshness from cited source pages.

This module never calls OpenAI or any paid API. It fetches only source URLs that
already exist in a trusted runtime research artifact, extracts publication time
from machine-readable page metadata, compares it with the saved editorial
window using Python timezone arithmetic, and fails closed for candidates whose
freshness cannot be independently proved.
"""
from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

SOURCE_FRESHNESS_VERSION = 1
MAX_RESPONSE_BYTES = 2_000_000
FETCH_TIMEOUT_SECONDS = 20
FETCH_ATTEMPTS = 2
USER_AGENT = "ai-svodki-source-freshness/1.0 (+https://rybalka.one/posts/)"

_HIGH_META_KEYS = {
    "article:published_time",
    "og:published_time",
    "datepublished",
    "parsely-pub-date",
    "dc.date.issued",
    "sailthru.date",
}
_LOW_META_KEYS = {
    "date",
    "pubdate",
    "publishdate",
    "publication_date",
    "publicationdate",
}
_ARTICLE_TYPES = {
    "article",
    "newsarticle",
    "report",
    "blogposting",
    "analysisnewsarticle",
}
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SourceFreshnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublicationEvidence:
    raw: str
    published_date: date
    published_at: datetime | None
    time_precision: str
    locator: str
    confidence_rank: int


class _PublicationMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[tuple[int, int, str, str]] = []
        self._order = 0
        self._ldjson = False
        self._ldjson_parts: list[str] = []
        self.ldjson_blocks: list[str] = []

    def _add(self, rank: int, locator: str, value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        self._order += 1
        self.values.append((rank, self._order, locator, value.strip()))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).casefold(): value for key, value in attrs if key}
        if tag.casefold() == "meta":
            key = str(
                values.get("property")
                or values.get("name")
                or values.get("itemprop")
                or ""
            ).strip().casefold()
            content = values.get("content")
            if key in _HIGH_META_KEYS:
                self._add(0, f"meta:{key}", content)
            elif key in _LOW_META_KEYS:
                self._add(3, f"meta:{key}", content)
        elif tag.casefold() == "time":
            raw = values.get("datetime")
            itemprop = str(values.get("itemprop") or "").casefold()
            marker = " ".join(
                str(values.get(key) or "") for key in ("class", "id", "data-testid")
            ).casefold()
            if itemprop == "datepublished":
                self._add(1, "time:itemprop=datePublished", raw)
            elif "publish" in marker or "article-date" in marker:
                self._add(2, "time:published-marker", raw)
        elif tag.casefold() == "script":
            script_type = str(values.get("type") or "").split(";", 1)[0].strip().casefold()
            if script_type == "application/ld+json":
                self._ldjson = True
                self._ldjson_parts = []

    def handle_data(self, data: str) -> None:
        if self._ldjson:
            self._ldjson_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._ldjson:
            self.ldjson_blocks.append("".join(self._ldjson_parts))
            self._ldjson = False
            self._ldjson_parts = []


def _jsonld_types(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value.casefold()}
    if isinstance(value, list):
        return {str(item).casefold() for item in value}
    return set()


def _collect_jsonld_dates(value: Any, output: list[tuple[int, int, str, str]], order: list[int], depth: int = 0) -> None:
    if isinstance(value, dict):
        published = value.get("datePublished")
        if isinstance(published, str) and published.strip():
            types = _jsonld_types(value.get("@type"))
            article_typed = bool(types & _ARTICLE_TYPES)
            order[0] += 1
            output.append(
                (
                    1 if article_typed else 2,
                    order[0],
                    f"jsonld:datePublished:depth={depth}",
                    published.strip(),
                )
            )
        for child in value.values():
            _collect_jsonld_dates(child, output, order, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _collect_jsonld_dates(child, output, order, depth + 1)


def _parse_publication_value(raw: str) -> tuple[date, datetime | None, str] | None:
    value = " ".join(str(raw).strip().split())
    if not value:
        return None
    if _DATE_ONLY_RE.fullmatch(value):
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            return None
        return parsed_date, None, "date"

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is not None:
            return parsed.date(), parsed, "datetime"
        return parsed.date(), None, "date"

    try:
        parsed_rfc = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        parsed_rfc = None
    if parsed_rfc is not None:
        if parsed_rfc.tzinfo is not None:
            return parsed_rfc.date(), parsed_rfc, "datetime"
        return parsed_rfc.date(), None, "date"

    for pattern in ("%B %d, %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            parsed_date = datetime.strptime(value, pattern).date()
        except ValueError:
            continue
        return parsed_date, None, "date"
    return None


def extract_publication_evidence(html: str) -> PublicationEvidence | None:
    parser = _PublicationMetadataParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        # Malformed publisher HTML must not turn into a guessed timestamp.
        pass

    values = list(parser.values)
    order = [max((item[1] for item in values), default=0)]
    for block in parser.ldjson_blocks:
        try:
            payload = json.loads(block)
        except (json.JSONDecodeError, TypeError):
            continue
        _collect_jsonld_dates(payload, values, order)

    for rank, _order, locator, raw in sorted(values, key=lambda item: (item[0], item[1])):
        parsed = _parse_publication_value(raw)
        if parsed is None:
            continue
        published_date, published_at, precision = parsed
        return PublicationEvidence(
            raw=raw,
            published_date=published_date,
            published_at=published_at,
            time_precision=precision,
            locator=locator,
            confidence_rank=rank,
        )
    return None


def _parse_aware(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SourceFreshnessError(f"{field} отсутствует")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceFreshnessError(f"{field} имеет некорректный timestamp") from exc
    if parsed.tzinfo is None:
        raise SourceFreshnessError(f"{field} должен содержать timezone")
    return parsed


def evidence_in_window(
    evidence: PublicationEvidence, *, start_at: datetime, end_at: datetime
) -> bool:
    if evidence.published_at is not None:
        return start_at <= evidence.published_at <= end_at
    published = evidence.published_date
    if not (start_at.date() <= published <= end_at.date()):
        return False
    # Date-only evidence on the exact cutoff day cannot prove the source existed
    # before the saved cutoff timestamp. This mirrors the recovery safety rule.
    if published == end_at.date():
        return False
    return True


def _safe_public_url(url: Any) -> str:
    if not isinstance(url, str) or not url.strip():
        raise SourceFreshnessError("source URL отсутствует")
    value = url.strip()
    parsed = urlsplit(value)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise SourceFreshnessError("source URL должен быть публичным HTTPS URL")
    host = parsed.hostname.casefold().strip(".")
    if host == "localhost" or host.endswith(".local"):
        raise SourceFreshnessError("локальные source URL запрещены")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise SourceFreshnessError("непубличные IP source URL запрещены")
    return value


FetchResult = tuple[str, str, int]
Fetcher = Callable[[str], FetchResult]


def fetch_source_html(url: str) -> FetchResult:
    safe_url = _safe_public_url(url)
    last_error: Exception | None = None
    for attempt in range(FETCH_ATTEMPTS):
        request = urllib.request.Request(
            safe_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                "Accept-Language": "en-US,en;q=0.8",
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                status = int(getattr(response, "status", 200) or 200)
                final_url = _safe_public_url(response.geturl())
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raw = raw[:MAX_RESPONSE_BYTES]
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace"), final_url, status
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, SourceFreshnessError) as exc:
            last_error = exc
            if attempt + 1 < FETCH_ATTEMPTS:
                time.sleep(0.25)
    raise SourceFreshnessError(
        f"source fetch failed: {type(last_error).__name__}: {last_error}"
    )


def _source_rows(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in [candidate.get("primary_source"), *(candidate.get("supporting_sources") or [])]:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append(copy.deepcopy(raw))
    return rows


def _apply_evidence(candidate: dict[str, Any], evidence: PublicationEvidence) -> None:
    candidate["published_date"] = evidence.published_date.isoformat()
    candidate["published_at"] = (
        evidence.published_at.isoformat() if evidence.published_at is not None else None
    )
    candidate["time_precision"] = evidence.time_precision


def _promote_source(candidate: dict[str, Any], source: dict[str, Any]) -> None:
    current = candidate.get("primary_source")
    source_url = str(source.get("url") or "")
    current_url = str(current.get("url") or "") if isinstance(current, dict) else ""
    if source_url == current_url:
        return
    supporting: list[dict[str, Any]] = []
    if isinstance(current, dict) and current_url and current_url != source_url:
        supporting.append(copy.deepcopy(current))
    for raw in candidate.get("supporting_sources") or []:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "")
        if url and url != source_url and url not in {str(item.get("url") or "") for item in supporting}:
            supporting.append(copy.deepcopy(raw))
    candidate["primary_source"] = copy.deepcopy(source)
    candidate["supporting_sources"] = supporting[:2]


def verify_candidate(
    candidate: dict[str, Any], *, start_at: datetime, end_at: datetime, fetcher: Fetcher
) -> dict[str, Any]:
    title = str(candidate.get("title") or "Кандидат без заголовка")
    original_recommendation = str(candidate.get("recommendation") or "")
    record: dict[str, Any] = {
        "title": title,
        "candidate_id": candidate.get("id", candidate.get("candidate_id")),
        "original_recommendation": original_recommendation,
        "status": "skipped",
        "sources": [],
    }
    if original_recommendation not in {"include", "consider"}:
        record["reason"] = "candidate_not_eligible_before_freshness_gate"
        return record

    source_rows = _source_rows(candidate)
    fresh_matches: list[tuple[dict[str, Any], PublicationEvidence, str]] = []
    dated_matches: list[tuple[dict[str, Any], PublicationEvidence, str]] = []
    for source in source_rows:
        source_url = str(source.get("url") or "")
        source_record: dict[str, Any] = {
            "publisher": source.get("publisher"),
            "url": source_url,
            "status": "error",
        }
        try:
            html, final_url, http_status = fetcher(source_url)
            evidence = extract_publication_evidence(html)
        except Exception as exc:
            source_record["error"] = f"{type(exc).__name__}: {exc}"
        else:
            source_record["final_url"] = final_url
            source_record["http_status"] = http_status
            if evidence is None:
                source_record["status"] = "no_publication_date"
            else:
                in_window = evidence_in_window(
                    evidence, start_at=start_at, end_at=end_at
                )
                source_record.update(
                    {
                        "status": "fresh" if in_window else "outside_window",
                        "published_date": evidence.published_date.isoformat(),
                        "published_at": (
                            evidence.published_at.isoformat()
                            if evidence.published_at is not None
                            else None
                        ),
                        "time_precision": evidence.time_precision,
                        "locator": evidence.locator,
                        "raw_date": evidence.raw,
                    }
                )
                dated_matches.append((source, evidence, final_url))
                if in_window:
                    fresh_matches.append((source, evidence, final_url))
        record["sources"].append(source_record)

    if fresh_matches:
        source, evidence, _final_url = fresh_matches[0]
        _promote_source(candidate, source)
        _apply_evidence(candidate, evidence)
        proof = (
            f"Source Freshness Proof v{SOURCE_FRESHNESS_VERSION}: "
            f"{evidence.locator}={evidence.raw}; timestamp проверен Python против effective window."
        )
        previous = str(candidate.get("freshness_reason") or "").strip()
        candidate["freshness_reason"] = f"{proof} {previous}".strip()
        record["status"] = "verified_fresh"
        record["selected_source_url"] = str(source.get("url") or "")
        record["published_date"] = candidate.get("published_date")
        record["published_at"] = candidate.get("published_at")
        return record

    candidate["recommendation"] = "exclude"
    if dated_matches:
        source, evidence, _final_url = dated_matches[0]
        _apply_evidence(candidate, evidence)
        candidate["freshness_status"] = "old_reprint"
        candidate["freshness_reason"] = (
            f"Source Freshness Proof v{SOURCE_FRESHNESS_VERSION}: подтверждённая "
            f"дата основного/цитируемого источника {evidence.raw} находится вне effective window."
        )
        record["status"] = "excluded_outside_window"
        record["selected_source_url"] = str(source.get("url") or "")
        record["published_date"] = candidate.get("published_date")
        record["published_at"] = candidate.get("published_at")
        return record

    candidate["verification_status"] = "unconfirmed"
    candidate["freshness_reason"] = (
        f"Source Freshness Proof v{SOURCE_FRESHNESS_VERSION}: ни один уже цитируемый "
        "source URL не отдал независимо проверяемую дату публикации; публикация fail-closed."
    )
    record["status"] = "excluded_unverified_freshness"
    return record


def verify_research_payload(
    research: dict[str, Any], *, fetcher: Fetcher = fetch_source_html
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(research, dict) or not isinstance(research.get("candidates"), list):
        raise SourceFreshnessError("research artifact должен содержать candidates[]")
    window = research.get("search_window")
    if not isinstance(window, dict):
        raise SourceFreshnessError("research artifact не содержит search_window")
    start_at = _parse_aware(window.get("start_at"), "search_window.start_at")
    end_at = _parse_aware(window.get("end_at"), "search_window.end_at")
    if end_at < start_at:
        raise SourceFreshnessError("search_window.end_at раньше start_at")

    result = copy.deepcopy(research)
    records: list[dict[str, Any]] = []
    eligible_before = 0
    for candidate in result["candidates"]:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("recommendation") in {"include", "consider"}:
            eligible_before += 1
        records.append(
            verify_candidate(
                candidate, start_at=start_at, end_at=end_at, fetcher=fetcher
            )
        )
    eligible_after = sum(
        1
        for candidate in result["candidates"]
        if isinstance(candidate, dict)
        and candidate.get("recommendation") in {"include", "consider"}
    )
    summary = {
        "version": SOURCE_FRESHNESS_VERSION,
        "status": "complete",
        "search_window": copy.deepcopy(window),
        "candidate_count": len([item for item in result["candidates"] if isinstance(item, dict)]),
        "eligible_before": eligible_before,
        "eligible_after": eligible_after,
        "verified_fresh": sum(item.get("status") == "verified_fresh" for item in records),
        "excluded_outside_window": sum(item.get("status") == "excluded_outside_window" for item in records),
        "excluded_unverified_freshness": sum(item.get("status") == "excluded_unverified_freshness" for item in records),
        "paid_api_calls": 0,
        "candidates": records,
    }
    return result, summary


def _stage_name(path: Path) -> str:
    name = path.name
    if name.startswith("primary-recall-research-"):
        return "primary"
    if "hybrid" in name:
        return "hybrid"
    if name.startswith(".coverage-audit-"):
        return "coverage"
    return "trusted_runtime"


def verify_research_file(
    research_path: Path,
    *,
    publication_date: str,
    report_path: Path,
    fetcher: Fetcher = fetch_source_html,
) -> dict[str, Any]:
    try:
        research = json.loads(research_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceFreshnessError(f"не удалось прочитать research artifact: {exc}") from exc
    verified, run = verify_research_payload(research, fetcher=fetcher)
    research_path.write_text(
        json.dumps(verified, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report: dict[str, Any] = {
        "version": SOURCE_FRESHNESS_VERSION,
        "publication_date": publication_date,
        "status": "complete",
        "runs": [],
        "paid_api_calls": 0,
    }
    if report_path.is_file():
        try:
            prior = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior = None
        if (
            isinstance(prior, dict)
            and prior.get("version") == SOURCE_FRESHNESS_VERSION
            and prior.get("publication_date") == publication_date
            and isinstance(prior.get("runs"), list)
        ):
            report = prior
    run["stage"] = _stage_name(research_path)
    run["research_path"] = str(research_path)
    report["runs"].append(run)
    report["paid_api_calls"] = 0
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify source publication freshness without paid APIs")
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        run = verify_research_file(
            args.research,
            publication_date=args.publication_date,
            report_path=args.report,
        )
    except Exception as exc:
        print(f"Source freshness verification failed: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
