from __future__ import annotations

import importlib.util
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

_V3_PATH = Path(__file__).with_name("weak_source_exact_binding_v3.py")
_V3_SPEC = importlib.util.spec_from_file_location(
    "weak_source_exact_binding_v3_for_v4",
    _V3_PATH,
)
assert _V3_SPEC and _V3_SPEC.loader
_v3 = importlib.util.module_from_spec(_V3_SPEC)
sys.modules[_V3_SPEC.name] = _v3
_V3_SPEC.loader.exec_module(_v3)

for _name in dir(_v3):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_v3, _name)

# Durable request identity remains v2-compatible. This marker versions only the
# semantic proof stored in a processed positive snapshot. Version 2 invalidates
# positive v4/evidence-v1 snapshots produced before the fourth-review temporal
# and cross-claim contradiction hardening.
VERSION = _v3.VERSION
MODE = _v3.MODE
EVIDENCE_VERSION = 2

_VARIANT_PUNCT_RE = re.compile(
    r"^(?P<sep>/|\+|[\u2010\u2011\u2012\u2013\u2014\u2015\u2212])"
    r"\s*(?P<token>[A-Za-z0-9][A-Za-z0-9.+-]*)?"
)
# v3 intentionally treats unknown adjacent words as possible model/version
# continuations. These are ordinary predicate/linking words observed after an
# exact product anchor; they may preserve identity but can never create lifecycle
# proof by themselves. Keep the exception local to v4 rather than mutating the
# historical v2/v3 compatibility vocabulary.
_V4_ANCHOR_ALLOWED_FOLLOWING_WORDS = frozenset(
    {"remain", "remains", "remained", "remaining", "stay", "stays", "stayed", "still"}
)
_PASSIVE_ACTION_RE = re.compile(
    r"\b(?:is|are|was|were|has\s+been|have\s+been|had\s+been)\s+"
    r"(?:launched|released|updated|upgraded)\b",
    re.I,
)
_CONDITIONAL_PREFIX_RE = re.compile(r"^\s*(?:if|unless|whether)\b", re.I)
_UNCERTAIN_ASSERTION_RE = re.compile(
    r"\b(?:rumou?r|rumou?red|speculation|speculative|unconfirmed|hypothetical|"
    r"reportedly|allegedly|purportedly|supposedly|apparently)\b",
    re.I,
)
_UNCERTAIN_ACTION_PREFIX_RE = re.compile(
    r"\b(?:reportedly|allegedly|purportedly|supposedly|apparently)\b"
    r"(?:\W+\w+){0,2}\W*$",
    re.I,
)
_POST_ACTION_STATE_RE = re.compile(
    r"^\W*(?:(?:is|are|was|were|has\s+been|have\s+been|had\s+been)\s+)?(?:"
    r"cancelled|canceled|abandoned|scrapped|delayed|postponed|paused|halted|"
    r"planned|scheduled|proposed|considered|expected|denied|disputed"
    r")\b|"
    r"^\W*(?:may|might|could|would|should)\s+"
    r"(?:happen|occur|take\s+place|be(?:come)?|arrive|ship)\b|"
    r"^\W*(?:not\s+(?:happening|happened|occurring|occurred)|"
    r"(?:has|have|had)\s+not\s+(?:happened|occurred|taken\s+place))\b",
    re.I,
)
_HISTORICAL_RELATIVE_RE = re.compile(
    r"\b(?:last\s+(?:year|month|week)|(?:years?|months?|weeks?)\s+ago|"
    r"previously|formerly|earlier)\b",
    re.I,
)
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_PREVIEW_TERMS = ("preview", "pre-release", "prerelease", "beta", "early access")
_GA_TERMS = ("general availability", "generally available", "stable release", "ga")


def _anchor_followed_by_variant_suffix(text: str, match_end: int) -> bool:
    tail = text[match_end:]
    punct = _VARIANT_PUNCT_RE.match(tail)
    if punct is not None:
        sep = punct.group("sep")
        raw_token = punct.group("token") or ""
        if raw_token:
            if raw_token.casefold() in _v3._v2._ANCHOR_ALLOWED_FOLLOWING_WORDS:
                return False
            return True
        # Slash and plus are product/version continuation syntax even without a
        # following word. Unicode dashes alone can be ordinary prose punctuation.
        return sep in {"/", "+"}
    next_word = re.match(
        r"(?:\s+|\s*[\(\[]\s*)([A-Za-z0-9][A-Za-z0-9.+-]*)",
        tail,
    )
    if (
        next_word is not None
        and next_word.group(1).casefold() in _V4_ANCHOR_ALLOWED_FOLLOWING_WORDS
    ):
        return False
    return _v3._anchor_followed_by_variant_suffix(text, match_end)


def _exact_anchor_spans(text: str, anchor: str) -> list[tuple[int, int]]:
    anchor = _v3._v2._clean(anchor)
    cleaned = _v3._v2._clean(text)
    if not anchor or not cleaned:
        return []
    spans: list[tuple[int, int]] = []
    for match in re.finditer(_v3._v2._anchor_pattern(anchor), cleaned, re.I):
        if not _anchor_followed_by_variant_suffix(cleaned, match.end()):
            spans.append(match.span())
    return spans


def _contains_exact_anchor(text: str, anchor: str) -> bool:
    return bool(_exact_anchor_spans(text, anchor))


def _passive_attribution_reason(claim: str, signal: dict[str, Any]) -> str | None:
    actions = set(_v3._v2._actions(signal))
    if not actions.intersection({"launch", "update"}):
        return None
    organization = _v3._v2._clean(signal.get("organization"))
    if not organization:
        return "organization_event_attribution_mismatch"
    org_pattern = rf"(?<![\w]){re.escape(organization)}(?![\w])"
    for match in _PASSIVE_ACTION_RE.finditer(claim):
        tail = claim[match.end():]
        by_match = re.search(r"\bby\s+([^,.;|]+)", tail, re.I)
        if by_match is not None:
            agent = by_match.group(1).strip()
            if re.match(org_pattern, agent, re.I) is None:
                return "organization_event_attribution_mismatch"
            continue
        if re.search(rf"\bfor\s+{org_pattern}", tail, re.I):
            return "organization_event_attribution_mismatch"
    return None


def _historical_reason(claim: str) -> str | None:
    if _HISTORICAL_RELATIVE_RE.search(claim):
        return "historical_event_context"
    current_year = date.today().year
    for match in _YEAR_RE.finditer(claim):
        try:
            year = int(match.group(1))
        except ValueError:
            continue
        if year < current_year:
            return "historical_event_context"
    return None


def _signal_action_spans(claim: str, signal: dict[str, Any]) -> list[tuple[int, int]]:
    """Return lifecycle spans for every retained action, independent of word order.

    v3's prospective guard is intentionally prefix-oriented. v4 additionally
    needs the exact span so suffix state such as ``GA planned`` or ``launch may
    happen`` is evaluated for every lifecycle family rather than a hard-coded
    launch/update subset.
    """
    spans: list[tuple[int, int]] = []
    for action in _v3._v2._actions(signal):
        if action == "replace":
            roles, _reason = _v3._v2._replacement_roles(signal)
            if roles is None:
                continue
            old_anchor, new_anchor = roles
            spans.extend(_v3._directed_replace_spans(claim, old_anchor, new_anchor))
            continue
        terms = _v3._v2._LIFECYCLE_GROUPS.get(action, (action,))
        for term in terms:
            spans.extend(match.span() for match in _v3._v2._term_matches(claim, term))
    return sorted(set(spans))


def _action_context_reason(claim: str, signal: dict[str, Any]) -> str | None:
    for start, end in _signal_action_spans(claim, signal):
        prefix = claim[max(0, start - 96):start]
        suffix = claim[end:min(len(claim), end + 112)]
        if _UNCERTAIN_ACTION_PREFIX_RE.search(prefix):
            return "lifecycle_noncurrent"
        if _POST_ACTION_STATE_RE.search(suffix):
            return "lifecycle_noncurrent"
    return None


def _strict_claim_reason(claim: str, signal: dict[str, Any]) -> str | None:
    passive = _passive_attribution_reason(claim, signal)
    if passive:
        return passive
    if _CONDITIONAL_PREFIX_RE.search(claim):
        return "lifecycle_noncurrent"
    contextual = _action_context_reason(claim, signal)
    if contextual:
        return contextual
    if _UNCERTAIN_ASSERTION_RE.search(claim):
        return "lifecycle_noncurrent"
    historical = _historical_reason(claim)
    if historical:
        return historical

    actions = _v3._v2._actions(signal)
    if "ga" in actions:
        preview_span, _ = _v3._active_term_span(claim, _PREVIEW_TERMS)
        if preview_span is not None:
            return "preview_ga_mismatch"
    return None


def _cross_claim_lifecycle_conflict_reason(
    claims: list[str], signal: dict[str, Any]
) -> str | None:
    """Reject mutually exclusive active lifecycle claims across the same surface.

    A clean GA sentence must not win simply because it appears before a second
    exact claim saying the same product is still in preview. Historical/negated
    background remains non-active through v3's span-state logic, preserving the
    existing current-assertion-plus-history positive contract.
    """
    actions = set(_v3._v2._actions(signal))
    if "ga" in actions:
        for claim in claims:
            preview_span, _ = _v3._active_term_span(claim, _PREVIEW_TERMS)
            if preview_span is not None:
                return "preview_ga_mismatch"
    if "preview" in actions:
        for claim in claims:
            ga_span, _ = _v3._active_term_span(claim, _GA_TERMS)
            if ga_span is not None:
                return "preview_ga_mismatch"
    return None


def exact_event_identity(surface: str, signal: dict[str, Any]) -> tuple[bool, str]:
    """Apply v3 identity plus stricter evidence-boundary/current-event guards."""
    base_ok, base_reason = _v3.exact_event_identity(surface, signal)
    if not base_ok:
        return base_ok, base_reason

    text = _v3._v2._clean(surface)
    anchors = _v3._v2._anchors(signal)
    candidate_claims = [
        claim
        for claim in _v3._v2._event_claims(text)
        if _v3._v2._contains_org(claim, signal.get("organization"))
        and all(_contains_exact_anchor(claim, anchor) for anchor in anchors)
    ]
    if not candidate_claims:
        return False, "version_identity_mismatch"

    reasons: list[str] = []
    positive = False
    for claim in candidate_claims:
        ok, reason = _v3._claim_lifecycle_matches(
            claim,
            signal,
            require_current_lifecycle=True,
        )
        if not ok:
            reasons.append(reason)
            continue
        strict_reason = _strict_claim_reason(claim, signal)
        if strict_reason is None:
            positive = True
            continue
        reasons.append(strict_reason)

    conflict = _cross_claim_lifecycle_conflict_reason(candidate_claims, signal)
    if conflict:
        return False, conflict
    if positive:
        # Exact same-identity claims that actively negate or make the retained
        # lifecycle prospective/uncertain are contradictory current evidence.
        # Historical background is deliberately not a veto: an authoritative
        # page may mention an older release while proving a new current event.
        for veto in ("lifecycle_negated", "lifecycle_noncurrent"):
            if veto in reasons:
                return False, veto
        return True, "exact_event_identity"

    for preferred in (
        "organization_event_attribution_mismatch",
        "lifecycle_negated",
        "lifecycle_noncurrent",
        "historical_event_context",
        "preview_ga_mismatch",
        "version_identity_mismatch",
    ):
        if preferred in reasons:
            return False, preferred
    return False, reasons[0] if reasons else "exact_event_claim_missing"


def candidate_exact_binding(
    candidate: dict[str, Any],
    signal: dict[str, Any],
    *,
    authoritative_domains: tuple[str, ...],
    authoritative_page_surface: str | None = None,
    authoritative_final_url: str | None = None,
) -> tuple[bool, str]:
    base_ok, base_reason = _v3.candidate_exact_binding(
        candidate,
        signal,
        authoritative_domains=authoritative_domains,
        authoritative_page_surface=authoritative_page_surface,
        authoritative_final_url=authoritative_final_url,
    )
    if not base_ok:
        return base_ok, base_reason

    card_ok, card_reason = exact_event_identity(
        _v3._v2._current_candidate_surface(candidate), signal
    )
    if not card_ok:
        return False, card_reason
    page_surface = _v3._v2._clean(authoritative_page_surface)
    page_ok, page_reason = exact_event_identity(page_surface, signal)
    if not page_ok:
        return False, f"authoritative_page_{page_reason}"
    return True, "exact_authoritative_page_binding"


def rejection_exact_terminal_binding(
    rejection: dict[str, Any],
    signal: dict[str, Any],
    *,
    authoritative_domains: tuple[str, ...],
) -> tuple[bool, str]:
    return _v3.rejection_exact_terminal_binding(
        rejection,
        signal,
        authoritative_domains=authoritative_domains,
    )
