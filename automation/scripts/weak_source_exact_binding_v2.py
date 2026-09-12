from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

import weak_source_exact_binding as _v1

VERSION = 2
MODE = _v1.MODE
TERMINAL_NEGATIVE_REASON_CODES = _v1.TERMINAL_NEGATIVE_REASON_CODES
qualifying_signals = _v1.qualifying_signals
select_signal = _v1.select_signal
build_query = _v1.build_query
build_prompt = _v1.build_prompt

_WORD_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_VARIANT_SUFFIXES = (
    "flash", "pro", "max", "mini", "lite", "turbo", "plus", "preview",
)
_ACTION_TERMS: dict[str, tuple[str, ...]] = {
    "release": ("release", "released", "releases", "launch", "launched", "launches"),
    "launch": ("launch", "launched", "launches"),
    "introduce": ("introduce", "introduced", "introduces"),
    "unveil": ("unveil", "unveiled", "unveils"),
    "update": ("update", "updated", "updates"),
    "upgrade": ("upgrade", "upgraded", "upgrades"),
    "ship": ("ship", "shipped", "ships"),
    "rollout": ("rollout", "roll out", "rolled out", "rolls out"),
    "preview": ("preview", "previewed", "previews", "pre-release", "prerelease"),
    "general_availability": ("general availability", "generally available", "ga release", "ga launch"),
    "retire": ("retire", "retired", "retires", "discontinue", "discontinued", "discontinues"),
}
_BENCHMARK_RE = re.compile(r"\b(?:benchmark|benchmarks|benchmarked|evaluation|evals?|performance tests?)\b", re.I)
_PREVIEW_RE = re.compile(r"\b(?:preview|pre-release|prerelease)\b", re.I)
_GA_RE = re.compile(r"\b(?:general availability|generally available|ga release|ga launch)\b", re.I)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _compact_identity(value: Any) -> str:
    return "".join(item.casefold() for item in _WORD_RE.findall(_clean(value)))


def _host(value: Any) -> str:
    try:
        host = (urlsplit(_clean(value)).hostname or "").casefold().strip(".")
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _host_allowed(host: str, domains: tuple[str, ...]) -> bool:
    return bool(host and any(host == domain or host.endswith("." + domain) for domain in domains))


def _anchor_pattern(anchor: str) -> str:
    raw = _clean(anchor).casefold()
    escaped = re.escape(raw)
    escaped = escaped.replace(r"\ ", r"\s+")
    suffixes = "|".join(re.escape(item) for item in _VARIANT_SUFFIXES)
    return rf"(?<![\w.]){escaped}(?![\w.\-]|\s+(?:{suffixes})\b)"


def _contains_exact_anchor(text: str, anchor: str) -> bool:
    return bool(_clean(anchor) and re.search(_anchor_pattern(anchor), _clean(text).casefold(), re.I))


def _contains_org(text: str, organization: Any) -> bool:
    org = _clean(organization)
    if not org:
        return False
    return bool(re.search(rf"(?<![\w]){re.escape(org.casefold()).replace(r'\ ', r'\s+')}(?![\w])", _clean(text).casefold(), re.I))


def _has_term(text: str, term: str) -> bool:
    pattern = re.escape(term.casefold()).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![\w]){pattern}(?![\w])", text.casefold(), re.I))


def _directed_replace_matches(text: str, old_anchor: str, new_anchor: str) -> bool:
    folded = _clean(text).casefold()
    old = _anchor_pattern(old_anchor)
    new = _anchor_pattern(new_anchor)
    relation = r"(?:replace|replaces|replaced|replacing|supersede|supersedes|superseded|superseding)"
    patterns = (
        rf"{relation}\s+{old}\s+(?:with|by)\s+{new}",
        rf"{new}\s+{relation}\s+{old}",
        rf"{old}\s+(?:is\s+|was\s+)?(?:replaced|superseded)\s+by\s+{new}",
    )
    return any(re.search(pattern, folded, re.I) for pattern in patterns)


def _current_candidate_surface(candidate: dict[str, Any]) -> str:
    # Deliberately exclude verified_facts/keywords/event history. Historical mentions
    # cannot prove the lifecycle action of the current card.
    return " ".join(
        _clean(candidate.get(key))
        for key in ("title", "event_type")
        if _clean(candidate.get(key))
    )


def _lifecycle_matches(text: str, signal: dict[str, Any]) -> tuple[bool, str]:
    actions = [_clean(item) for item in signal.get("lifecycle_action_anchors") or [] if _clean(item)]
    versions = [_clean(item) for item in signal.get("product_version_anchors") or [] if _clean(item)]
    if not actions:
        return False, "lifecycle_identity_missing"
    for action in actions:
        if action == "replace":
            if len(versions) != 2 or not _directed_replace_matches(text, versions[0], versions[1]):
                return False, "directed_replacement_mismatch"
            continue
        terms = _ACTION_TERMS.get(action, (action.replace("_", " "),))
        if not any(_has_term(text, term) for term in terms):
            return False, "lifecycle_identity_mismatch"
        if action == "preview" and _GA_RE.search(text):
            return False, "preview_ga_mismatch"
        if action == "general_availability" and _PREVIEW_RE.search(text):
            return False, "preview_ga_mismatch"
        if action not in {"benchmark", "evaluation"} and _BENCHMARK_RE.search(text) and not any(
            _has_term(text, term) for term in terms
        ):
            return False, "benchmark_lifecycle_mismatch"
    return True, "exact_lifecycle"


def exact_event_identity(text: str, signal: dict[str, Any]) -> tuple[bool, str]:
    if not _contains_org(text, signal.get("organization")):
        return False, "organization_mismatch"
    versions = [_clean(item) for item in signal.get("product_version_anchors") or [] if _clean(item)]
    if not versions or not all(_contains_exact_anchor(text, anchor) for anchor in versions):
        return False, "version_identity_mismatch"
    return _lifecycle_matches(text, signal)


class _EventSurfaceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.heading_depth = 0
        self.paragraph_depth = 0
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.paragraphs: list[str] = []
        self.meta_parts: list[str] = []
        self._paragraph_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        values = {str(k).casefold(): v for k, v in attrs if k}
        if tag == "title":
            self.in_title = True
        elif tag in {"h1", "h2"}:
            self.heading_depth += 1
        elif tag == "p" and len(self.paragraphs) < 3:
            self.paragraph_depth += 1
            self._paragraph_parts = []
        elif tag == "meta":
            key = str(values.get("property") or values.get("name") or "").casefold()
            if key in {"og:title", "twitter:title", "description", "og:description", "twitter:description"}:
                value = _clean(values.get("content"))
                if value:
                    self.meta_parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "title":
            self.in_title = False
        elif tag in {"h1", "h2"} and self.heading_depth:
            self.heading_depth -= 1
        elif tag == "p" and self.paragraph_depth:
            value = _clean(" ".join(self._paragraph_parts))
            if value and len(self.paragraphs) < 3:
                self.paragraphs.append(value)
            self.paragraph_depth -= 1
            self._paragraph_parts = []

    def handle_data(self, data: str) -> None:
        value = _clean(data)
        if not value:
            return
        if self.in_title:
            self.title_parts.append(value)
        if self.heading_depth:
            self.heading_parts.append(value)
        if self.paragraph_depth and len(self.paragraphs) < 3:
            self._paragraph_parts.append(value)


def extract_authoritative_event_surface(html: str) -> str:
    parser = _EventSurfaceParser()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:
        pass
    # Bound the proof surface to page title/metadata/headings and the opening lead.
    # Deep historical body references are intentionally excluded.
    parts = [*parser.title_parts, *parser.meta_parts, *parser.heading_parts, *parser.paragraphs]
    return _clean(" ".join(parts))[:6000]


def candidate_exact_binding(
    candidate: Any,
    signal: dict[str, Any],
    *,
    authoritative_domains: tuple[str, ...],
    authoritative_page_surface: str | None = None,
    authoritative_final_url: str | None = None,
) -> tuple[bool, str]:
    if not isinstance(candidate, dict):
        return False, "candidate_not_object"
    if candidate.get("recommendation") not in {"include", "consider"}:
        return False, "recommendation_not_eligible"
    if candidate.get("verification_status") != "verified":
        return False, "candidate_not_verified"
    if candidate.get("freshness_status") not in {"new_event", "material_update"}:
        return False, "candidate_not_fresh_event"
    if _compact_identity(candidate.get("organization")) != _compact_identity(signal.get("organization")):
        return False, "organization_mismatch"

    source = candidate.get("primary_source")
    if not isinstance(source, dict):
        return False, "primary_source_missing"
    source_host = _host(source.get("url"))
    final_host = _host(authoritative_final_url or source.get("url"))
    weak_host = _host((signal.get("source_provenance") or {}).get("url"))
    if not _host_allowed(source_host, authoritative_domains) or not _host_allowed(final_host, authoritative_domains):
        return False, "primary_source_not_authoritative"
    if source_host == weak_host or final_host == weak_host:
        return False, "weak_source_cannot_self_authorize"

    card_ok, card_reason = exact_event_identity(_current_candidate_surface(candidate), signal)
    if not card_ok:
        return False, card_reason
    if not _clean(authoritative_page_surface):
        return False, "authoritative_page_proof_missing"
    page_ok, page_reason = exact_event_identity(_clean(authoritative_page_surface), signal)
    if not page_ok:
        return False, f"authoritative_page_{page_reason}"
    return True, "exact_authoritative_page_binding"


def rejection_exact_terminal_binding(
    rejection: Any,
    signal: dict[str, Any],
    *,
    authoritative_domains: tuple[str, ...],
    **_kwargs: Any,
) -> tuple[bool, str]:
    # Model-supplied negative labels are never independent proof. A future
    # terminal closure must be backed by deterministic archive/freshness evidence.
    if not isinstance(rejection, dict):
        return False, "rejection_not_object"
    return False, "terminal_negative_requires_independent_proof"
