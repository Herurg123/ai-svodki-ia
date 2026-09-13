from __future__ import annotations

import copy
import html
import importlib.util
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_V1_PATH = Path(__file__).with_name("weak_source_exact_binding.py")
_V1_SPEC = importlib.util.spec_from_file_location(
    "weak_source_exact_binding_v1_for_hardened_v2",
    _V1_PATH,
)
assert _V1_SPEC and _V1_SPEC.loader
_v1 = importlib.util.module_from_spec(_V1_SPEC)
sys.modules[_V1_SPEC.name] = _v1
_V1_SPEC.loader.exec_module(_v1)

VERSION = 2
MODE = "weak_source_exact_authoritative_binding"

qualifying_signals = _v1.qualifying_signals
select_signal = _v1.select_signal
build_query = _v1.build_query
build_prompt = _v1.build_prompt


def candidate_source_url(candidate: dict[str, Any]) -> str:
    source = candidate.get("primary_source")
    if not isinstance(source, dict):
        return ""
    return _clean(source.get("url"))


def normalized_host(value: Any) -> str:
    return _v1._host(value)


def normalized_org(value: Any) -> str:
    return _v1._compact_identity(value)


_LIFECYCLE_GROUPS: dict[str, tuple[str, ...]] = {
    "replace": ("replace", "replaces", "replaced", "replacing", "replacement", "supersede", "supersedes", "superseded"),
    "preview": ("preview", "pre-release", "prerelease", "beta", "early access"),
    "ga": ("general availability", "generally available", "ga", "stable release"),
    "launch": ("launch", "launches", "launched", "release", "releases", "released"),
    "update": ("update", "updates", "updated", "upgrade", "upgrades", "upgraded"),
    "benchmark": ("benchmark", "benchmarks", "benchmarked", "evaluation", "eval", "score"),
}

_BENCHMARK_RE = re.compile(r"\b(?:benchmark|benchmarks|benchmarked|evaluation|eval|score|scores)\b", re.I)
_PREVIEW_RE = re.compile(r"\b(?:preview|pre[- ]?release|beta|early access)\b", re.I)
_GA_RE = re.compile(r"\b(?:general availability|generally available|stable release|GA)\b", re.I)
_CLAIM_SPLIT_RE = re.compile(r"\s*(?:\||(?<=[.!?;]))\s+")
_NEGATED_ACTION_PREFIX_RE = re.compile(
    r"(?:"
    r"\bnot\b|\bnever\b|\bno longer\b|"
    r"\bno\s+(?:plan|plans|intention|intent)\s+to\b|"
    r"\b(?:do|does|did|is|are|was|were|has|have|had|will|would|can|could|should)"
    r"(?:\s+not|n't)\b|"
    r"\byet\s+to\b|\bwithout\b|\brather\s+than\b|\binstead\s+of\b"
    r")(?:\W+\w+){0,3}\W*$",
    re.I,
)
_HISTORICAL_ACTION_PREFIX_RE = re.compile(
    r"(?:"
    r"\bpreviously\b|\bearlier\b|\bformerly\b|\bonce\b|"
    r"\blast\s+(?:year|month|week)\b|"
    r"\b(?:years?|months?|weeks?)\s+ago\b|"
    r"\bprior\s+to\b|\bhad\b"
    r")(?:\W+\w+){0,4}\W*$",
    re.I,
)
_HISTORICAL_ACTION_SUFFIX_RE = re.compile(
    r"^\W*(?:"
    r"last\s+(?:year|month|week)\b|"
    r"(?:years?|months?|weeks?)\s+ago\b|"
    r"previously\b|earlier\b|formerly\b"
    r")",
    re.I,
)
_CURRENT_ACTION_NEAR_RE = re.compile(
    r"\b(?:now|today|currently|newly|this\s+(?:week|month))\b",
    re.I,
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _anchors(signal: dict[str, Any]) -> list[str]:
    return [_clean(item) for item in signal.get("product_version_anchors") or [] if _clean(item)]


def _actions(signal: dict[str, Any]) -> list[str]:
    return [_clean(item).casefold() for item in signal.get("lifecycle_action_anchors") or [] if _clean(item)]


def _anchor_pattern(anchor: str) -> str:
    escaped = re.escape(anchor.casefold()).replace(r"\ ", r"\s+")
    suffixes = r"(?:pro|flash|mini|max|ultra|preview|beta|turbo|lite|plus)"
    return rf"(?<![\w.]){escaped}(?![\w.\-]|\s+(?:{suffixes})\b)"


def _contains_exact_anchor(text: str, anchor: str) -> bool:
    return bool(_clean(anchor) and re.search(_anchor_pattern(anchor), _clean(text).casefold(), re.I))


def _contains_org(text: str, organization: Any) -> bool:
    org = _clean(organization)
    if not org:
        return False
    return bool(re.search(rf"(?<![\w]){re.escape(org.casefold()).replace(r'\ ', r'\s+')}(?![\w])", _clean(text).casefold(), re.I))


def _term_matches(text: str, term: str) -> list[re.Match[str]]:
    pattern = re.escape(term.casefold()).replace(r"\ ", r"\s+")
    return list(re.finditer(rf"(?<![\w]){pattern}(?![\w])", text.casefold(), re.I))


def _has_term(text: str, term: str) -> bool:
    return bool(_term_matches(text, term))


def _directed_replace_span(text: str, old_anchor: str, new_anchor: str) -> tuple[int, int] | None:
    folded = _clean(text).casefold()
    old = _anchor_pattern(old_anchor)
    new = _anchor_pattern(new_anchor)
    relation = r"(?:replace|replaces|replaced|replacing|supersede|supersedes|superseded|superseding)"
    patterns = (
        rf"{relation}\s+{old}\s+(?:with|by)\s+{new}",
        rf"{new}\s+{relation}\s+{old}",
        rf"{old}\s+(?:is\s+|was\s+)?(?:replaced|superseded)\s+by\s+{new}",
    )
    for pattern in patterns:
        match = re.search(pattern, folded, re.I)
        if match:
            return match.span()
    return None


def _directed_replace_matches(text: str, old_anchor: str, new_anchor: str) -> bool:
    return _directed_replace_span(text, old_anchor, new_anchor) is not None


def _event_claims(text: str) -> list[str]:
    cleaned = _clean(text)
    if not cleaned:
        return []
    return [_clean(part) for part in _CLAIM_SPLIT_RE.split(cleaned) if _clean(part)]


def _action_mention_is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 72):start]
    return bool(_NEGATED_ACTION_PREFIX_RE.search(prefix))


def _action_mention_is_historical(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 88):start]
    suffix = text[end:min(len(text), end + 64)]
    if _CURRENT_ACTION_NEAR_RE.search(prefix[-32:]) or _CURRENT_ACTION_NEAR_RE.search(suffix[:32]):
        return False
    return bool(
        _HISTORICAL_ACTION_PREFIX_RE.search(prefix)
        or _HISTORICAL_ACTION_SUFFIX_RE.search(suffix)
    )


def _active_term_span(text: str, terms: tuple[str, ...]) -> tuple[tuple[int, int] | None, str | None]:
    saw_negated = False
    saw_historical = False
    for term in terms:
        for match in _term_matches(text, term):
            start, end = match.span()
            if _action_mention_is_negated(text, start):
                saw_negated = True
                continue
            if _action_mention_is_historical(text, start, end):
                saw_historical = True
                continue
            return (start, end), None
    if saw_negated:
        return None, "lifecycle_negated"
    if saw_historical:
        return None, "historical_event_context"
    return None, "lifecycle_identity_mismatch"


def _current_candidate_surface(candidate: dict[str, Any]) -> str:
    parts = [_clean(candidate.get(key)) for key in ("title", "event_type") if _clean(candidate.get(key))]
    return " | ".join(parts)


def _claim_lifecycle_matches(
    claim: str,
    signal: dict[str, Any],
    *,
    require_current_lifecycle: bool,
) -> tuple[bool, str]:
    anchors = _anchors(signal)
    actions = _actions(signal)
    for action in actions:
        if action == "replace":
            if require_current_lifecycle and _BENCHMARK_RE.search(claim):
                return False, "benchmark_lifecycle_mismatch"
            if len(anchors) < 2:
                return False, "replacement_direction_mismatch"
            span = _directed_replace_span(claim, anchors[0], anchors[1])
            if span is None:
                return False, "replacement_direction_mismatch"
            if _action_mention_is_negated(claim, span[0]):
                return False, "lifecycle_negated"
            if _action_mention_is_historical(claim, span[0], span[1]):
                return False, "historical_event_context"
            continue
        terms = _LIFECYCLE_GROUPS.get(action, (action,))
        span, reason = _active_term_span(claim, terms)
        if span is None:
            return False, str(reason or "lifecycle_identity_mismatch")

    wants_preview = any(action == "preview" for action in actions)
    wants_ga = any(action == "ga" for action in actions)
    if wants_preview:
        ga_span, _ = _active_term_span(
            claim,
            ("general availability", "generally available", "stable release", "ga"),
        )
        if ga_span is not None:
            return False, "preview_ga_mismatch"
    if wants_ga:
        ga_span, ga_reason = _active_term_span(
            claim,
            ("general availability", "generally available", "stable release", "ga"),
        )
        if ga_span is None:
            return False, str(ga_reason or "preview_ga_mismatch")
    if require_current_lifecycle and "benchmark" not in actions:
        benchmark_span, _ = _active_term_span(
            claim,
            ("benchmark", "benchmarks", "benchmarked", "evaluation", "eval", "score", "scores"),
        )
        if benchmark_span is not None and any(
            action in {"replace", "launch", "update", "preview", "ga"}
            for action in actions
        ):
            return False, "benchmark_lifecycle_mismatch"
    return True, "exact_event_identity"


def _identity_surface_matches(text: str, signal: dict[str, Any], *, require_current_lifecycle: bool) -> tuple[bool, str]:
    text = _clean(text)
    if not text:
        return False, "event_surface_missing"
    if not _contains_org(text, signal.get("organization")):
        return False, "organization_identity_mismatch"
    anchors = _anchors(signal)
    if not anchors:
        return False, "version_identity_missing"
    for anchor in anchors:
        if not _contains_exact_anchor(text, anchor):
            return False, "version_identity_mismatch"
    actions = _actions(signal)
    if not actions:
        return False, "lifecycle_identity_missing"

    candidate_claims = [
        claim for claim in _event_claims(text)
        if all(_contains_exact_anchor(claim, anchor) for anchor in anchors)
    ]
    if not candidate_claims:
        return False, "exact_event_claim_missing"

    reasons: list[str] = []
    for claim in candidate_claims:
        ok, reason = _claim_lifecycle_matches(
            claim,
            signal,
            require_current_lifecycle=require_current_lifecycle,
        )
        if ok:
            return True, reason
        reasons.append(reason)

    for preferred in (
        "lifecycle_negated",
        "historical_event_context",
        "benchmark_lifecycle_mismatch",
        "preview_ga_mismatch",
        "replacement_direction_mismatch",
        "lifecycle_identity_mismatch",
    ):
        if preferred in reasons:
            return False, preferred
    return False, reasons[0] if reasons else "exact_event_claim_missing"


def exact_event_identity(surface: str, signal: dict[str, Any]) -> tuple[bool, str]:
    """Strict zero-paid identity proof used by archive/dedupe and page binding."""
    return _identity_surface_matches(surface, signal, require_current_lifecycle=True)


class _EventSurfaceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._paragraphs = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.casefold()
        attrs_map = {str(k).casefold(): str(v or "") for k, v in attrs}
        if lower == "meta":
            key = (attrs_map.get("property") or attrs_map.get("name") or "").casefold()
            if key in {"og:title", "twitter:title"}:
                value = html.unescape(attrs_map.get("content", "")).strip()
                if value:
                    self.parts.append(value)
        if lower in {"title", "h1", "h2"} or (lower == "p" and self._paragraphs < 3):
            self._capture = lower
            self._buffer = []
            if lower == "p":
                self._paragraphs += 1

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == tag.casefold():
            value = _clean(" ".join(self._buffer))
            if value:
                self.parts.append(value)
            self._capture = None
            self._buffer = []


def extract_authoritative_event_surface(html_text: str) -> str:
    parser = _EventSurfaceParser()
    try:
        parser.feed(str(html_text or ""))
    except Exception:
        return ""
    return _clean(" | ".join(parser.parts[:10]))


def candidate_exact_binding(candidate: dict[str, Any], signal: dict[str, Any], *, authoritative_domains: tuple[str, ...], authoritative_page_surface: str | None = None, authoritative_final_url: str | None = None) -> tuple[bool, str]:
    if candidate.get("recommendation") not in {"include", "consider"}:
        return False, "candidate_not_eligible"
    if candidate.get("verification_status") != "verified":
        return False, "candidate_not_verified"
    if candidate.get("freshness_status") not in {"new_event", "material_update"}:
        return False, "candidate_not_fresh_event"
    if normalized_org(candidate.get("organization")) != normalized_org(signal.get("organization")):
        return False, "organization_identity_mismatch"
    url = candidate_source_url(candidate)
    host = normalized_host(url)
    weak_host = normalized_host(((signal.get("source_provenance") or {}).get("url")))
    if not host or not _v1._host_allowed(host, authoritative_domains):
        return False, "primary_source_not_authoritative"
    if weak_host and host == weak_host:
        return False, "weak_source_cannot_self_authorize"
    final_url = _clean(authoritative_final_url) or url
    final_host = normalized_host(final_url)
    if not final_host or not _v1._host_allowed(final_host, authoritative_domains):
        return False, "authoritative_page_redirected_outside_allowlist"
    if weak_host and final_host == weak_host:
        return False, "weak_source_cannot_self_authorize"
    card_ok, card_reason = exact_event_identity(_current_candidate_surface(candidate), signal)
    if not card_ok:
        return False, card_reason
    page_surface = _clean(authoritative_page_surface)
    if not page_surface:
        return False, "authoritative_page_identity_unverified"
    page_ok, page_reason = exact_event_identity(page_surface, signal)
    if not page_ok:
        return False, f"authoritative_page_{page_reason}"
    return True, "exact_authoritative_page_binding"


def rejection_exact_terminal_binding(rejection: dict[str, Any], signal: dict[str, Any], *, authoritative_domains: tuple[str, ...]) -> tuple[bool, str]:
    del rejection, signal, authoritative_domains
    return False, "terminal_negative_requires_independent_proof"
