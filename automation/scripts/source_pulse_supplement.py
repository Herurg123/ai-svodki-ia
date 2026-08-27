#!/usr/bin/env python3
"""Source Pulse v1.1: zero-paid supplemental Tier-A discovery before first editorial.

The collector remains a fixed-source HTTPS plane.  This wrapper repairs common
real-world HTML date shapes, turns only fresh Tier-A official Pulse-only leads
into conservative ``consider`` candidates, and writes a full diagnostic report.
It never calls OpenAI or Web Search.  Tier-B remains diagnostic-only.
"""
from __future__ import annotations

import copy
import html
import json
import re
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import source_freshness
import source_pulse
from source_pulse_shadow import build_fusion_diagnostics
from story_coverage import merge_candidates, read_json, write_json

SOURCE_PULSE_SUPPLEMENT_VERSION = 11
SOURCE_PULSE_REPORT_VERSION = 1
SOURCE_PULSE_REPORT_STRATEGY = "source_pulse_shadow"
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config" / "source-pulse-v1.json"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "preview" / "production-daily"

_AI_RE = re.compile(
    r"(?:\bAI\b|artificial intelligence|machine learning|\bLLM\b|large language model|"
    r"foundation model|multimodal|agentic|\bagent\b|\bGPU\b|data cent(?:er|re)|robot|"
    r"Qwen|DeepSeek|Cotype|GLM|нейросет|искусственн\w* интеллект|\bИИ\b|"
    r"машинн\w* обуч|大模型|人工智能|机器人|智算)",
    re.IGNORECASE,
)
_MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_DATE_PATTERNS = (
    re.compile(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b"),
    re.compile(r"\b(0?[1-9]|[12]\d|3[01])[.](0?[1-9]|1[0-2])[.](20\d{2})\b"),
    re.compile(r"\b(0?[1-9]|[12]\d|3[01])\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(20\d{2})(?:\s*г\.?)?\b", re.I),
    re.compile(r"\b(20\d{2})年(0?[1-9]|1[0-2])月(0?[1-9]|[12]\d|3[01])日\b"),
    re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(0?[1-9]|[12]\d|3[01]),\s*(20\d{2})\b", re.I),
)
_CONTAINER_MARKER_RE = re.compile(r"news|release|press|post|article|item|card|row|entry|result", re.I)
_BASE_PARSE_HTML = source_pulse.parse_html
_PARSE_STATS: dict[str, dict[str, int]] = {}

Collector = Callable[..., dict[str, Any]]
PageFetcher = Callable[[str], tuple[str, str, int]]


def _parse_visible_date(text: str) -> date | None:
    value = " ".join(html.unescape(text or "").split())
    if not value:
        return None
    for index, pattern in enumerate(_DATE_PATTERNS):
        match = pattern.search(value)
        if not match:
            continue
        try:
            if index == 0:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if index == 1:
                return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            if index == 2:
                return date(int(match.group(3)), _MONTHS_RU[match.group(2).casefold()], int(match.group(1)))
            if index == 3:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            parsed, _dt, _precision = source_pulse.parse_date(match.group(0))
            return parsed
        except (ValueError, KeyError):
            continue
    return None


class _BoundedIndexParser(HTMLParser):
    """Associate visible dates with links only inside bounded article-like containers."""

    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.frames: list[dict[str, Any]] = []
        self.blocks: list[dict[str, Any]] = []
        self.current_link: dict[str, Any] | None = None

    def _is_container(self, tag: str, attrs: dict[str, str | None]) -> bool:
        if tag in {"article", "li", "tr"}:
            return True
        if tag not in {"div", "section"}:
            return False
        marker = " ".join(str(attrs.get(key) or "") for key in ("class", "id", "role", "data-testid"))
        return bool(_CONTAINER_MARKER_RE.search(marker))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).casefold(): value for key, value in attrs if key}
        name = tag.casefold()
        if self._is_container(name, values):
            self.frames.append({"tag": name, "text": [], "links": []})
        if name == "a" and values.get("href"):
            self.current_link = {
                "href": urljoin(self.base, str(values["href"])),
                "text": [],
            }

    def handle_data(self, data: str) -> None:
        for frame in self.frames:
            if sum(len(x) for x in frame["text"]) < 12000:
                frame["text"].append(data)
        if self.current_link is not None:
            self.current_link["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if name == "a" and self.current_link is not None:
            link = {
                "href": self.current_link["href"],
                "text": " ".join("".join(self.current_link["text"]).split()),
            }
            for frame in self.frames:
                frame["links"].append(copy.deepcopy(link))
            self.current_link = None
        if name in {"article", "li", "tr", "div", "section"}:
            for index in range(len(self.frames) - 1, -1, -1):
                if self.frames[index]["tag"] == name:
                    frame = self.frames.pop(index)
                    self.blocks.append(frame)
                    break


def parse_html_index_v11(body: str, base: str) -> list[source_pulse.ParsedItem]:
    base_items = _BASE_PARSE_HTML(body, base)
    parser = _BoundedIndexParser(base)
    try:
        parser.feed(body)
        parser.close()
    except Exception:
        pass

    recovered: dict[tuple[str, str], source_pulse.ParsedItem] = {}
    for block in parser.blocks:
        published = _parse_visible_date(" ".join(block.get("text") or []))
        if published is None:
            continue
        for raw in block.get("links") or []:
            title = " ".join(str(raw.get("text") or "").split())
            url = str(raw.get("href") or "").strip()
            if len(title) < 8 or not url.startswith("https://"):
                continue
            key = (source_pulse.norm_url(url), title.casefold())
            recovered[key] = source_pulse.ParsedItem(
                title=title,
                url=url,
                published_date=published,
                published_at=None,
                time_precision="date",
                source_item_id=url,
            )

    combined: list[source_pulse.ParsedItem] = []
    seen: set[tuple[str, str]] = set()
    recovered_count = 0
    for item in base_items:
        key = (source_pulse.norm_url(item.url), item.title.casefold())
        replacement = recovered.get(key)
        if item.published_date is None and replacement is not None:
            combined.append(replacement)
            recovered_count += 1
        else:
            combined.append(item)
        seen.add(key)
    for key, item in recovered.items():
        if key not in seen:
            combined.append(item)
            recovered_count += 1
            seen.add(key)

    dated = sum(item.published_date is not None for item in combined)
    _PARSE_STATS[base] = {
        "parsed_items_before_v11": len(base_items),
        "parsed_items_after_v11": len(combined),
        "dated_items_after_v11": dated,
        "undated_items_after_v11": len(combined) - dated,
        "visible_dates_recovered": recovered_count,
    }
    return source_pulse.dedupe(combined)


def run_source_pulse_v11(**kwargs: Any) -> dict[str, Any]:
    """Run the existing hardened collector with only its HTML parser upgraded."""
    _PARSE_STATS.clear()
    original = source_pulse.parse_html
    source_pulse.parse_html = parse_html_index_v11
    try:
        snapshot = source_pulse.run_source_pulse(**kwargs)
    finally:
        source_pulse.parse_html = original
    snapshot = copy.deepcopy(snapshot)
    snapshot["collector_version"] = SOURCE_PULSE_SUPPLEMENT_VERSION
    for source in snapshot.get("sources") or []:
        if not isinstance(source, dict):
            continue
        selected = str(source.get("selected_url") or "")
        stats = _PARSE_STATS.get(selected)
        if stats is None:
            attempts = source.get("attempts") or []
            for attempt in attempts:
                if isinstance(attempt, dict) and str(attempt.get("status")) == "ok":
                    stats = _PARSE_STATS.get(str(attempt.get("url") or ""))
                    if stats is not None:
                        break
        if stats is not None:
            source["parser_v11"] = copy.deepcopy(stats)
    return snapshot


class _PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: list[str] = []
        self.in_p = False
        self.parts: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).casefold(): value for key, value in attrs if key}
        name = tag.casefold()
        if name == "meta":
            marker = str(values.get("name") or values.get("property") or "").casefold()
            content = str(values.get("content") or "").strip()
            if marker in {"description", "og:description", "twitter:description"} and content:
                self.meta.append(" ".join(content.split()))
        elif name == "p":
            self.in_p = True
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.in_p:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "p" and self.in_p:
            text = " ".join("".join(self.parts).split())
            if len(text) >= 40:
                self.paragraphs.append(text)
            self.in_p = False
            self.parts = []


def _source_summary_text(body: str) -> str:
    parser = _PageTextParser()
    try:
        parser.feed(body)
        parser.close()
    except Exception:
        pass
    candidates = [*parser.meta, *parser.paragraphs[:3]]
    for text in candidates:
        cleaned = " ".join(text.split())
        if len(cleaned) >= 50:
            return cleaned[:700]
    return ""


def _category(title: str, summary: str) -> str:
    text = f"{title} {summary}".casefold()
    if any(token in text for token in ("funding", "financing", "investment", "placement", "revenue", "earnings", "выруч", "инвест")):
        return "investment"
    if any(token in text for token in ("data center", "data centre", "gpu", "chip", "compute", "infrastructure", "дата-центр", "вычисл")):
        return "infrastructure"
    if any(token in text for token in ("agent", "агент")):
        return "agents"
    if any(token in text for token in ("model", "qwen", "deepseek", "glm", "cotype", "модел")):
        return "models"
    if any(token in text for token in ("robot", "робот")):
        return "robotics"
    return "other"


def _keywords(title: str) -> list[str]:
    tokens: list[str] = []
    for raw in source_pulse.TOK.findall(title):
        value = raw.strip(".,:;()[]{}").strip()
        if len(value) < 2 or value.casefold() in source_pulse.GENERIC:
            continue
        if value not in tokens:
            tokens.append(value)
        if len(tokens) >= 12:
            break
    return tokens or ["Source Pulse"]


def _source_metadata(registry_contract: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for raw in registry_contract.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("id") or "")
        if not sid:
            continue
        result[sid] = {
            "publisher": str(raw.get("publisher") or sid.replace("_", " ").title()),
            "organization": str(raw.get("organization") or raw.get("publisher") or sid.replace("_", " ").title()),
        }
    return result


def _candidate_from_lead(
    lead: dict[str, Any], *, publisher: str, organization: str,
    evidence: source_freshness.PublicationEvidence, summary_text: str,
) -> dict[str, Any]:
    title = " ".join(str(lead.get("title") or "").split())
    url = str(lead.get("url") or "").strip()
    published_date = evidence.published_date.isoformat()
    freshness_note = (
        f"Source Pulse v1.1 + Source Freshness Proof: {evidence.locator}={evidence.raw}; "
        "официальный Tier-A URL проверен без OpenAI/Web Search."
    )
    fact_two = summary_text or f"Официальный источник датирует публикацию {published_date}."
    return {
        "title": title,
        "organization": organization,
        "published_date": published_date,
        "published_at": evidence.published_at.isoformat() if evidence.published_at is not None else None,
        "time_precision": evidence.time_precision,
        "topic": title,
        "event_type": "source_pulse_official_update",
        "keywords": _keywords(title),
        "geography": "russia" if lead.get("region") == "russia" else "world",
        "category": _category(title, summary_text),
        "source_type": "official",
        "primary_source": {"title": title, "publisher": publisher, "url": url},
        "supporting_sources": [],
        "event_summary": summary_text or title,
        "verified_facts": [title, fact_two],
        "significance": "Source Pulse supplemental lead; значимость не повышалась автоматически и должна быть решена штатным editorial.",
        "significance_score": 3,
        "limitations": "Детерминированный source-aware lead без модельного semantic enrichment; при слабой содержательности editorial должен его отклонить.",
        "archive_status": "none",
        "archive_reason": "Точный URL не найден в недавнем архиве Source Pulse на этапе discovery.",
        "recommendation": "consider",
        "verification_status": "verified",
        "verification_notes": freshness_note,
        "freshness_status": "new_event",
        "freshness_reason": freshness_note,
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
        "audit_direction": "source_pulse_v11",
    }


def _prior_report(output_root: Path, publication_date: str) -> dict[str, Any] | None:
    path = output_root / f"source-pulse-{publication_date}.json"
    if not path.is_file():
        return None
    try:
        value = read_json(path)
    except Exception:
        return None
    if (
        isinstance(value, dict)
        and value.get("version") == SOURCE_PULSE_REPORT_VERSION
        and value.get("strategy") == SOURCE_PULSE_REPORT_STRATEGY
        and value.get("publication_date") == publication_date
        and isinstance(value.get("snapshot"), dict)
    ):
        return value
    return None


def run_source_pulse_supplement(
    *, research_path: Path, archive_path: Path, publication_date: str,
    output_root: Path = DEFAULT_OUTPUT_ROOT, registry_path: Path = DEFAULT_REGISTRY_PATH,
    maximum_candidates: int = 20, collector_fn: Collector = run_source_pulse_v11,
    page_fetcher: PageFetcher = source_freshness.fetch_source_html,
) -> dict[str, Any]:
    """Supplement trusted Primary research without any paid search/model call."""
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
    prior = _prior_report(output_root, publication_date)
    reused_snapshot = prior is not None
    if prior is not None:
        snapshot = copy.deepcopy(prior["snapshot"])
    else:
        registry = source_pulse.load_registry(registry_path)
        snapshot = collector_fn(
            registry=registry,
            start_at=start_at,
            end_at=end_at,
            archive=archive,
        )
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
            "fusion_disposition": row.get("disposition"),
            "promotion_status": "not_eligible",
            "reason": None,
        }
        if row.get("disposition") != "pulse_only":
            record["reason"] = f"fusion_{row.get('disposition')}"
            dispositions.append(record)
            continue
        if row.get("tier") != "A" or row.get("role") != "official":
            record["reason"] = "tier_b_or_nonofficial_lead_only"
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
        summary_text = _source_summary_text(body)
        if not _AI_RE.search(f"{title} {summary_text}"):
            record["promotion_status"] = "rejected"
            record["reason"] = "deterministic_ai_relevance_gate"
            dispositions.append(record)
            continue
        info = metadata.get(str(row.get("source_id") or ""), {})
        candidate = _candidate_from_lead(
            row,
            publisher=info.get("publisher") or str(row.get("source_id") or "Official source"),
            organization=info.get("organization") or info.get("publisher") or str(row.get("source_id") or "Official source"),
            evidence=evidence,
            summary_text=summary_text,
        )
        additions.append(candidate)
        record["promotion_status"] = "proposed"
        record["reason"] = "tier_a_official_fresh_ai_relevant"
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

    final_fusion = build_fusion_diagnostics(snapshot, merged if accepted else research)
    report = {
        "version": SOURCE_PULSE_REPORT_VERSION,
        "strategy": SOURCE_PULSE_REPORT_STRATEGY,
        "supplement_version": SOURCE_PULSE_SUPPLEMENT_VERSION,
        "publication_date": publication_date,
        "status": "complete" if snapshot.get("summary") is not None else "complete_with_gaps",
        "state": "completed_supplemental",
        "candidate_influence": False,
        "supplemental_candidate_influence": True,
        "supplemental_policy": "tier_a_official_pulse_only_consider_after_deterministic_page_and_freshness_gate",
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
            "candidate_count_after": len((merged if accepted else research).get("candidates") or []),
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
    return {
        "version": report.get("supplement_version") if isinstance(report, dict) else None,
        "status": report.get("status") if isinstance(report, dict) else None,
        "paid_api_calls": 0,
        "web_search_operations": 0,
        "reused_snapshot": bool(report.get("reused_snapshot")) if isinstance(report, dict) else False,
        "source_summary": copy.deepcopy(snapshot.get("summary")) if isinstance(snapshot, dict) else None,
        "promoted_count": int(promotion.get("promoted_count", 0) or 0) if isinstance(promotion, dict) else 0,
        "candidate_count_before": promotion.get("candidate_count_before") if isinstance(promotion, dict) else None,
        "candidate_count_after": promotion.get("candidate_count_after") if isinstance(promotion, dict) else None,
    }
