"""Offline-only event identity detection and hash-bound Oct 21 editorial correction.

Different prose can refer to the same event. A detection does NOT authorize
deletion, paraphrasing, a new provider call, or a retry of saved Editorial.
"""
from __future__ import annotations

import copy
import hashlib
import html
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
DATE = "2026-10-21"
RAW_SHA = "abd3462ebd7ff46c8db09a733e0bc2e3b432bc600c3bc151cd3b65daef997478"
ARTICLE_SHA = "c508c6f5b8d0c71beed991439386a06137d7a7b34e7f6d00828f2d5d27bbfd78"
DETAIL_SHA = "b8af33710578bf6b8c3bb16d206d3a029ab5d10bee881582b67cd58eacca2778"
PARAPHRASE_SHA = "3f27b416369e71513b3b1609d0a901c9fe4db07d0b040e8bd08f5f1234bc7978"
JOURNAL_IDENTITY = {
    "response_sha256": "e9ff7b2a69c6345a448ece17d1f0a560474b91909e89e08541434056202ad127",
    "request_sha256": "7a7406864201da05ea07ecec6b18b049d512cc0dd3a8f6fba3b3c3e9c33e7074",
    "post_freshness_candidate_pool_sha256": "47e1482c5c81f6aadaf3f180d7204bc910b0ff023e4a9e1148590c60342f6f9d",
    "archive_sha256": "87eae526295da7ee791619cacfb9d7f16c07425d5efe85eb3fdcfe327a35347d",
}
BEFORE = ["cand-001", "cand-002", "cand-003", "cand-004", "cand-005", "cand-006", "cand-013"]
AFTER = ["cand-001", "cand-003", "cand-004", "cand-005", "cand-006", "cand-013", "cand-002"]
MINIMAX_URL = "https://www.minimax.io/blog/minimax-m31f"


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


class Boundaries(HTMLParser):
    def __init__(self, value: str):
        super().__init__(convert_charrefs=True)
        self.lines = [0] + [m.end() for m in re.finditer("\n", value)]
        self.stack: list[str] = []
        self.starts: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if not self.stack and tag in {"h2", "h3"}:
            line, column = self.getpos()
            self.starts.append((self.lines[line - 1] + column, tag))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1] != tag:
            raise ValueError("HTML structure is not balanced")
        self.stack.pop()


class Block(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading = False
        self.heading_parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"h2", "h3"}:
            self.heading = True
        if tag == "a" and dict(attrs).get("href"):
            self.links.append(str(dict(attrs)["href"]).strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "h3"}:
            self.heading = False

    def handle_data(self, data: str) -> None:
        if self.heading:
            self.heading_parts.append(data)


def article_parts(value: str) -> tuple[str, list[dict[str, Any]]]:
    parser = Boundaries(value)
    parser.feed(value)
    parser.close()
    if parser.stack or not parser.starts:
        raise ValueError("HTML must have balanced top-level story headings")
    parts = []
    section = ""
    position = 0
    for index, (start, kind) in enumerate(parser.starts):
        end = parser.starts[index + 1][0] if index + 1 < len(parser.starts) else len(value)
        part_html = value[start:end]
        block = Block()
        block.feed(part_html)
        block.close()
        heading = re.sub(r"\s+", " ", html.unescape("".join(block.heading_parts))).strip()
        if kind == "h2":
            section = heading
        else:
            position += 1
        parts.append({"kind": kind, "html": part_html, "section": section, "headline": heading,
                      "position": position if kind == "h3" else None, "links": block.links})
    return value[:parser.starts[0][0]], parts


def candidate_urls(value: dict[str, Any]) -> set[str]:
    urls = set()
    for key in ("event_origin_url", "source_publication_url"):
        if isinstance(value.get(key), str) and value[key].strip():
            urls.add(value[key].strip())
    for source in [value.get("primary_source"), *(value.get("supporting_sources") or [])]:
        if isinstance(source, dict) and isinstance(source.get("url"), str) and source["url"].strip():
            urls.add(source["url"].strip())
    return urls


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"\w+", text.casefold()) if len(word) >= 3}


def detect_event_repetitions(article_html: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Grounded event detection, regardless of differing HTML or paragraphs.

    Shared source URLs are NOT enough when several candidates use one URL.
    Separate candidates with near-identical event metadata create only a
    possible_same_event *blocker*, not an automatic merger or deletion.
    """
    _, pieces = article_parts(article_html)
    all_candidates = {str(c["id"]): c for c in candidates if isinstance(c, dict) and c.get("id")}
    owners: dict[str, set[str]] = defaultdict(set)
    for cid, item in all_candidates.items():
        for url in candidate_urls(item):
            owners[url].add(cid)
    assigned: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for piece in pieces:
        if piece["kind"] != "h3":
            continue
        links_owners = {cid for url in piece["links"] for cid in owners.get(url, set())}
        if len(links_owners) == 1:
            assigned[next(iter(links_owners))].append(piece)
    issues: list[dict[str, Any]] = []
    for cid, blocks in assigned.items():
        if len(blocks) > 1:
            issues.append({"classification": "same_candidate_event", "candidate_id": cid,
                           "positions": [item["position"] for item in blocks],
                           "evidence": "same_event_candidate_in_multiple_html_blocks",
                           "auto_removed": False})
    ids = list(assigned)
    for i, left_id in enumerate(ids):
        for right_id in ids[i + 1:]:
            left, right = all_candidates[left_id], all_candidates[right_id]
            organization = str(left.get("organization", "")).casefold().strip()
            event = str(left.get("event_type", "")).casefold().strip()
            if (not organization or organization != str(right.get("organization", "")).casefold().strip()
                    or not event or event != str(right.get("event_type", "")).casefold().strip()):
                continue
            def overlap(a: str, b: str) -> float:
                x, y = _tokens(a), _tokens(b)
                return len(x & y) / max(1, len(x | y))
            heads = [re.sub(r"\s+", " ", x[0]["headline"].casefold())
                     for x in (assigned[left_id], assigned[right_id])]
            if (overlap(str(left.get("title", "")), str(right.get("title", ""))) >= .88
                    and overlap(str(left.get("event_summary", "")), str(right.get("event_summary", ""))) >= .83
                    and SequenceMatcher(None, heads[0], heads[1]).ratio() >= .86):
                issues.append({"classification": "possible_same_event",
                               "candidate_ids": [left_id, right_id],
                               "positions": [assigned[left_id][0]["position"], assigned[right_id][0]["position"]],
                               "evidence": "independent_candidate_event_metadata_similarity",
                               "auto_removed": False})
    return issues


def save_editorial_attempt(root: Path, publication_date: str, response_id: str,
                           output_text: str, model: str) -> Path:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication_date):
        raise ValueError("invalid publication date")
    identity = re.sub(r"[^\w.-]", "_", str(response_id or ""))[:100]
    if not identity or identity in {".", ".."}:
        raise ValueError("invalid provider response identity")
    folder = root / "editorial-attempts" / publication_date
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / (identity + ".json")
    if destination.is_file():
        if destination.read_text(encoding="utf-8") != output_text:
            raise ValueError("same response_id has different provider output")
        return destination
    temp = destination.with_suffix(".tmp")
    temp.write_text(output_text, encoding="utf-8")
    temp.replace(destination)
    metadata = {"publication_date": publication_date, "response_id": response_id,
                "model": model, "output_sha256": sha(output_text), "provider_calls": 0}
    (folder / (identity + ".meta.json")).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def reconcile_exact_approved_incident(editorial: dict[str, Any],
                                       candidates: list[dict[str, Any]], *,
                                       publication_date: str, raw_path: Path,
                                       journal_path: Path | None = None
                                       ) -> tuple[dict[str, Any], dict[str, Any]]:
    audit: dict[str, Any] = {"status": "not_applicable", "rule": "oct21-minimax-exact-response-v1"}
    if publication_date != DATE:
        return editorial, audit
    article_html = editorial.get("digest", {}).get("article_html")
    if not isinstance(article_html, str):
        raise ValueError("incident article_html missing")
    if sha(article_html) != ARTICLE_SHA:
        return editorial, audit
    if not raw_path.is_file() or sha(raw_path.read_bytes()) != RAW_SHA:
        raise ValueError("incident provider raw hash mismatch")
    if journal_path is None or not journal_path.is_file():
        raise ValueError("incident protected journal missing")
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    if journal.get("state") not in {"response_saved", "validated"}:
        raise ValueError("incident journal has unsafe state")
    for key, value in JOURNAL_IDENTITY.items():
        if journal.get(key) != value:
            raise ValueError("incident journal identity drift: " + key)
    if editorial.get("selected_candidate_ids") != BEFORE:
        raise ValueError("incident selected partition drift")
    by_id = {str(item.get("id")): item for item in candidates}
    if "cand-002" not in by_id or MINIMAX_URL not in candidate_urls(by_id["cand-002"]):
        raise ValueError("incident candidate/source binding missing")
    prefix, blocks = article_parts(article_html)
    stories = [block for block in blocks if block["kind"] == "h3"]
    if (len(stories) != 8 or stories[1]["section"] != "Мировые лидеры ИИ"
            or stories[7]["section"] != "Китайские лидеры ИИ"):
        raise ValueError("incident section topology drift")
    if sha(stories[1]["html"]) != DETAIL_SHA or sha(stories[7]["html"]) != PARAPHRASE_SHA:
        raise ValueError("incident approved block fingerprint mismatch")
    matches = detect_event_repetitions(article_html, [by_id["cand-002"]])
    if len(matches) != 1 or matches[0]["positions"] != [2, 8]:
        raise ValueError("incident candidate-level semantic event mismatch")
    repaired = copy.deepcopy(editorial)
    repaired["digest"]["article_html"] = prefix + "".join(
        stories[1]["html"] if item is stories[7] else item["html"]
        for item in blocks if item is not stories[1]
    )
    repaired["selected_candidate_ids"] = list(AFTER)
    audit.update({
        "status": "applied",
        "input_html_sha256": sha(article_html),
        "raw_file_sha256": RAW_SHA,
        "output_html_sha256": sha(repaired["digest"]["article_html"]),
        "selected_ids_before": list(BEFORE),
        "selected_ids_after": list(AFTER),
        "operations": [
            {"type": "remove_world_placement", "block_sha256": DETAIL_SHA},
            {"type": "replace_china_paraphrase_with_approved_detail", "block_sha256": PARAPHRASE_SHA},
        ],
        "unchanged_provider_raw": True,
        "provider_calls": 0,
    })
    return repaired, audit
