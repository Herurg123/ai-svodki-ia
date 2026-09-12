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
candidate_source_url = _v1.candidate_source_url
normalized_host = _v1.normalized_host
normalized_org = _v1.normalized_org


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
    return " ".join(_clean(candidate.get(key)) for key in ("title", "event_type") if _clean(candidate.get(key)))


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
    folded = text.casefold()
    for action in actions:
        if action == "replace":
            if require_current_lifecycle and _BENCHMARK_RE.search(text):
                return False, "benchmark_lifecycle_mismatch"
            if len(anchors) < 2 or not _directed_replace_matches(text, anchors[0], anchors[1]):
                return False, "replacement_direction_mismatch"
            continue
        terms = _LIFECYCLE_GROUPS.get(action, (action,))
        if not any(_has_term(folded, term) for term in terms):
            return False, "lifecycle_identity_mismatch"
    wants_preview = any(action == "preview" for action in actions)
    wants_ga = any(action == "ga" for action in actions)
    if wants_preview and _GA_RE.search(text):
        return False, "preview_ga_mismatch"
    if wants_ga and not _GA_RE.search(text):
        return False, "preview_ga_mismatch"
    if require_current_lifecycle and "benchmark" not in actions and _BENCHMARK_RE.search(text):
        if any(action in {"replace", "launch", "update", "preview", "ga"} for action in actions):
            return False, "benchmark_lifecycle_mismatch"
    return True, "exact_event_identity"


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
    return _clean(" ".join(parser.parts[:10]))


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
