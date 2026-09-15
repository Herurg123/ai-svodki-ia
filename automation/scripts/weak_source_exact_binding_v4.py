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
# semantic proof stored in a processed positive snapshot. Version 6 invalidates
# positive evidence-v5 snapshots produced before lifecycle-local historical
# classification and Unicode-wrapper attribution were hardened, while preserving
# the same durable request contract and the v4 compatibility/import surface.
VERSION = _v3.VERSION
MODE = _v3.MODE
EVIDENCE_VERSION = 6

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
_PASSIVE_AGENT_RE = re.compile(r"\bby\s+([^.;|]+)", re.I)
_TRAILING_REPLACEMENT_AGENT_RE = re.compile(
    r"^\s*(?:(?:[,:\-\u2013\u2014]\s*)|"
    r"(?:[\(\[\{<«‹（［｛\"'“”‘’]\s*))*\bby\s+([^.;|]+)",
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
_HISTORICAL_FULL_DATE_RE = re.compile(
    r"\b(?:on\s+)?(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?"
    r"(?:,\s*|\s+)((?:19|20)\d{2})\b",
    re.I,
)
_HISTORICAL_ACTION_YEAR_RELATION_RE = re.compile(
    r"\b(?:in|during|back\s+in|since)\s+((?:19|20)\d{2})\b",
    re.I,
)
_HISTORICAL_ACTION_RELATIVE_RE = re.compile(
    r"\b(?:last\s+(?:year|month|week)|"
    r"(?:\d+\s+)?(?:years?|months?|weeks?)\s+ago|"
    r"previously|earlier|formerly)\b",
    re.I,
)
_HISTORICAL_DATE_BACKGROUND_BRIDGE_RE = re.compile(
    r"\b(?:due\s+to|because(?:\s+of)?|owing\s+to|incident|cause|reason|"
    r"after|before|following|with|while|whereas|although|though|amid|despite|but|"
    r"separate|dispute|agreement|context|background|dating\s+to|unresolved)\b",
    re.I,
)
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


def _claim_match_surface(text: str) -> str:
    """Remove only terminal sentence punctuation before exact lifecycle matching.

    The inherited anchor pattern deliberately rejects a dot immediately after an
    anchor because it can introduce a version continuation. Once claim splitting
    has already established the sentence boundary, however, a terminal period is
    punctuation rather than a model suffix. Keeping this normalization local to
    the complete claim preserves rejection of true continuations such as `.1`.
    """
    return re.sub(r"[.!?;]+$", "", _v3._v2._clean(text)).rstrip()


def _exact_anchor_spans(text: str, anchor: str) -> list[tuple[int, int]]:
    anchor = _v3._v2._clean(anchor)
    cleaned = _claim_match_surface(text)
    if not anchor or not cleaned:
        return []
    spans: list[tuple[int, int]] = []
    for match in re.finditer(_v3._v2._anchor_pattern(anchor), cleaned, re.I):
        if not _anchor_followed_by_variant_suffix(cleaned, match.end()):
            spans.append(match.span())
    return spans


def _contains_exact_anchor(text: str, anchor: str) -> bool:
    return bool(_exact_anchor_spans(text, anchor))


def _agent_matches_signal_organization(agent: str, organization: str) -> bool:
    cleaned_agent = _v3._v2._clean(agent).strip(
        "()[]{}<>«»‹›（）［］｛｝ \t\r\n\"'“”‘’"
    )
    return bool(
        cleaned_agent
        and _v3.normalized_org(cleaned_agent) == _v3.normalized_org(organization)
    )


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


def _historical_bridge_blocks_binding(bridge: str) -> bool:
    return bool(
        _HISTORICAL_DATE_BACKGROUND_BRIDGE_RE.search(bridge)
        or _v3._v2._CURRENT_ACTION_NEAR_RE.search(bridge)
        or _POST_ACTION_STATE_RE.search(bridge)
    )


def _action_span_has_historical_prefix_marker(
    claim: str,
    span: tuple[int, int],
) -> bool:
    """Bind a past year/relative marker before the action only across a clean bridge."""
    start, _end = span
    prefix = claim[max(0, start - 180):start]
    current_year = date.today().year

    for match in reversed(list(_HISTORICAL_ACTION_YEAR_RELATION_RE.finditer(prefix))):
        try:
            year = int(match.group(1))
        except ValueError:
            continue
        if year >= current_year:
            continue
        if _historical_bridge_blocks_binding(prefix[match.end():]):
            continue
        return True

    for match in reversed(list(_HISTORICAL_ACTION_RELATIVE_RE.finditer(prefix))):
        if _historical_bridge_blocks_binding(prefix[match.end():]):
            continue
        return True
    return False


def _action_span_has_historical_suffix_marker(
    claim: str,
    span: tuple[int, int],
) -> bool:
    """Recognize old-event suffixes without treating every old year as the action date."""
    _start, end = span
    suffix = claim[end:min(len(claim), end + 180)]
    current_year = date.today().year

    for match in _HISTORICAL_ACTION_YEAR_RELATION_RE.finditer(suffix):
        try:
            year = int(match.group(1))
        except ValueError:
            continue
        if year >= current_year:
            continue
        if _historical_bridge_blocks_binding(suffix[:match.start()]):
            continue
        return True

    for match in _HISTORICAL_ACTION_RELATIVE_RE.finditer(suffix):
        if _historical_bridge_blocks_binding(suffix[:match.start()]):
            continue
        return True
    return False


def _action_span_has_past_full_date(
    claim: str,
    span: tuple[int, int],
) -> bool:
    """Bind an explicit past full date to the lifecycle span, not the whole claim."""
    start, end = span
    local_start = max(0, start - 140)
    local_end = min(len(claim), end + 180)
    local = claim[local_start:local_end]
    action_start = start - local_start
    action_end = end - local_start
    current_year = date.today().year

    for match in _HISTORICAL_FULL_DATE_RE.finditer(local):
        try:
            year = int(match.group(1))
        except ValueError:
            continue
        if year >= current_year:
            continue
        if match.start() >= action_end:
            bridge = local[action_end:match.start()]
        elif match.end() <= action_start:
            bridge = local[match.end():action_start]
        else:
            bridge = ""
        if _historical_bridge_blocks_binding(bridge):
            continue
        return True
    return False


def _action_span_is_historical(
    claim: str,
    span: tuple[int, int],
) -> bool:
    """Return history only when an old marker binds this exact relation span."""
    start, _end = span
    prefix = claim[max(0, start - 120):start]
    if _v3._v2._HISTORICAL_ACTION_PREFIX_RE.search(prefix):
        return True
    if _action_span_has_historical_prefix_marker(claim, span):
        return True
    if _action_span_has_historical_suffix_marker(claim, span):
        return True
    return _action_span_has_past_full_date(claim, span)


def _post_action_state_span(
    claim: str,
    span: tuple[int, int],
) -> tuple[int, int] | None:
    _start, end = span
    suffix = claim[end:min(len(claim), end + 112)]
    match = _POST_ACTION_STATE_RE.search(suffix)
    if match is None:
        return None
    return end + match.start(), end + match.end()


def _action_relation_is_historical(
    claim: str,
    span: tuple[int, int],
) -> bool:
    if _action_span_is_historical(claim, span):
        return True
    state_span = _post_action_state_span(claim, span)
    return bool(state_span and _action_span_is_historical(claim, state_span))


def _span_state_v4(text: str, span: tuple[int, int]) -> str | None:
    """Relation-local replacement for v3's broad any-year historical state."""
    start, _end = span
    historical = _action_relation_is_historical(text, span)
    if _v3._v2._action_mention_is_negated(text, start):
        return "historical_event_context" if historical else "lifecycle_negated"
    if _v3._action_mention_is_noncurrent(text, start):
        return "historical_event_context" if historical else "lifecycle_noncurrent"
    if historical:
        return "historical_event_context"
    return None


# The inherited matcher resolves _span_state through its own module globals at
# call time. Patch only the private v3 compatibility instance loaded for v4 so
# current runtime uses relation-local historical semantics without mutating the
# historical source file or its public import surface.
_v3._span_state = _span_state_v4


def _passive_attribution_reason(claim: str, signal: dict[str, Any]) -> str | None:
    actions = set(_v3._v2._actions(signal))
    organization = _v3._v2._clean(signal.get("organization"))
    if not organization:
        return "organization_event_attribution_mismatch"

    if actions.intersection({"launch", "update"}):
        for match in _PASSIVE_ACTION_RE.finditer(claim):
            relation_historical = _action_relation_is_historical(claim, match.span())
            tail = claim[match.end():]
            by_match = _PASSIVE_AGENT_RE.search(tail)
            if by_match is not None:
                # Keep the complete agent surface through commas. Truncating at
                # the first comma turns a multi-agent list such as
                # ``DeepSeek, OpenAI and Anthropic`` into a false exact match.
                agent = by_match.group(1).strip()
                if not _agent_matches_signal_organization(agent, organization):
                    if relation_historical:
                        continue
                    return "organization_event_attribution_mismatch"
                continue
            org_pattern = rf"(?<![\w]){re.escape(organization)}(?![\w])"
            if re.search(rf"\bfor\s+{org_pattern}", tail, re.I):
                if relation_historical:
                    continue
                return "organization_event_attribution_mismatch"

    if "replace" in actions:
        roles, _reason = _v3._v2._replacement_roles(signal)
        if roles is not None:
            old_anchor, new_anchor = roles
            for start, end in _v3._directed_replace_spans(
                claim, old_anchor, new_anchor
            ):
                # The passive replacement grammar already contains the internal
                # relation ``old was replaced by new``. Only attribution that
                # begins *after the complete directed replacement span* can be a
                # separate event agent. A bounded sequence of punctuation and
                # opening wrappers may precede ``by``; the complete agent surface
                # is retained through commas for exact identity comparison.
                trailing = _TRAILING_REPLACEMENT_AGENT_RE.match(claim[end:])
                if trailing is None:
                    continue
                agent = trailing.group(1).strip()
                if not _agent_matches_signal_organization(agent, organization):
                    if _action_relation_is_historical(claim, (start, end)):
                        continue
                    return "organization_event_attribution_mismatch"
    return None


def _historical_reason(claim: str, signal: dict[str, Any]) -> str | None:
    """Classify a claim historical only when all retained relations are old."""
    spans = _signal_action_spans(claim, signal)
    if spans and all(_action_relation_is_historical(claim, span) for span in spans):
        return "historical_event_context"
    return None


def _action_context_reason(claim: str, signal: dict[str, Any]) -> str | None:
    for start, end in _signal_action_spans(claim, signal):
        relation_historical = _action_relation_is_historical(claim, (start, end))
        if _v3._v2._action_mention_is_negated(claim, start):
            if not relation_historical:
                return "lifecycle_negated"
            continue

        prefix = claim[max(0, start - 96):start]
        if _UNCERTAIN_ACTION_PREFIX_RE.search(prefix):
            if not relation_historical:
                return "lifecycle_noncurrent"
            continue

        state_span = _post_action_state_span(claim, (start, end))
        if state_span is not None and not _action_span_is_historical(claim, state_span):
            return "lifecycle_noncurrent"
    return None


def _strict_claim_reason(claim: str, signal: dict[str, Any]) -> str | None:
    # Resolve current contradictions/foreign attribution before generic history.
    # Each veto is itself relation-local, so historical background cannot veto a
    # separate current exact claim and unrelated old dates cannot hide a current
    # contradiction.
    contextual = _action_context_reason(claim, signal)
    if contextual:
        return contextual
    passive = _passive_attribution_reason(claim, signal)
    if passive:
        return passive
    historical = _historical_reason(claim, signal)
    if historical:
        return historical
    if _CONDITIONAL_PREFIX_RE.search(claim):
        return "lifecycle_noncurrent"
    if _UNCERTAIN_ASSERTION_RE.search(claim):
        return "lifecycle_noncurrent"

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
            preview_span, _ = _v3._active_term_span(_claim_match_surface(claim), _PREVIEW_TERMS)
            if preview_span is not None:
                return "preview_ga_mismatch"
    if "preview" in actions:
        for claim in claims:
            ga_span, _ = _v3._active_term_span(_claim_match_surface(claim), _GA_TERMS)
            if ga_span is not None:
                return "preview_ga_mismatch"
    return None


def exact_event_identity(surface: str, signal: dict[str, Any]) -> tuple[bool, str]:
    """Apply v3 structural primitives plus stricter v4 current-event guards."""
    text = _v3._v2._clean(surface)
    if not text:
        return False, "event_surface_missing"
    if not _v3._v2._contains_org(text, signal.get("organization")):
        return False, "organization_identity_mismatch"

    anchors = _v3._v2._anchors(signal)
    if not anchors:
        return False, "version_identity_missing"
    for anchor in anchors:
        if not _contains_exact_anchor(text, anchor):
            return False, "version_identity_mismatch"

    actions = _v3._v2._actions(signal)
    if not actions:
        return False, "lifecycle_identity_missing"
    if "replace" in actions:
        roles, role_reason = _v3._v2._replacement_roles(signal)
        if roles is None:
            return False, role_reason
        if _v3._replacement_direction_conflict(text, signal, roles):
            return False, "replacement_direction_conflict"

    candidate_claims = [
        claim
        for claim in _v3._v2._event_claims(text)
        if _v3._v2._contains_org(claim, signal.get("organization"))
        and all(_contains_exact_anchor(claim, anchor) for anchor in anchors)
    ]
    if not candidate_claims:
        return False, "exact_event_claim_missing"

    reasons: list[str] = []
    positive = False
    for claim in candidate_claims:
        match_claim = _claim_match_surface(claim)

        # Current contradictions and foreign attribution are checked first, but
        # both are relation-aware: old background is skipped, while an unrelated
        # old date cannot launder a current veto into historical context.
        contextual = _action_context_reason(match_claim, signal)
        if contextual:
            reasons.append(contextual)
            continue
        passive = _passive_attribution_reason(match_claim, signal)
        if passive:
            reasons.append(passive)
            continue
        historical = _historical_reason(match_claim, signal)
        if historical:
            reasons.append(historical)
            continue

        ok, reason = _v3._claim_lifecycle_matches(
            match_claim,
            signal,
            require_current_lifecycle=True,
        )
        if not ok:
            reasons.append(reason)
            continue
        strict_reason = _strict_claim_reason(match_claim, signal)
        if strict_reason is None:
            positive = True
            continue
        reasons.append(strict_reason)

    if positive:
        # Cross-claim contradiction is meaningful only when a retained positive
        # claim exists. Without one, preserve the ordinary v3 lifecycle reason
        # instead of replacing it with a global GA/preview mismatch label.
        conflict = _cross_claim_lifecycle_conflict_reason(candidate_claims, signal)
        if conflict:
            return False, conflict
        # Exact same-identity claims with foreign attribution or active lifecycle
        # contradiction cannot be rescued by a separate clean-looking duplicate.
        # Historical background is deliberately not a veto: an authoritative
        # page may mention an older release while proving a new current event.
        for veto in (
            "organization_event_attribution_mismatch",
            "lifecycle_negated",
            "lifecycle_noncurrent",
        ):
            if veto in reasons:
                return False, veto
        return True, "exact_event_identity"

    for preferred in (
        "organization_event_attribution_mismatch",
        "lifecycle_negated",
        "lifecycle_noncurrent",
        "historical_event_context",
        "replacement_direction_conflict",
        "benchmark_lifecycle_mismatch",
        "preview_ga_mismatch",
        "replacement_direction_mismatch",
        "model_action_attribution_mismatch",
        "lifecycle_identity_mismatch",
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
    if candidate.get("recommendation") not in {"include", "consider"}:
        return False, "candidate_not_eligible"
    if candidate.get("verification_status") != "verified":
        return False, "candidate_not_verified"
    if candidate.get("freshness_status") not in {"new_event", "material_update"}:
        return False, "candidate_not_fresh_event"
    if _v3.normalized_org(candidate.get("organization")) != _v3.normalized_org(
        signal.get("organization")
    ):
        return False, "organization_identity_mismatch"

    url = _v3.candidate_source_url(candidate)
    host = _v3.normalized_host(url)
    weak_host = _v3.normalized_host(((signal.get("source_provenance") or {}).get("url")))
    if not host or not _v3._v2._v1._host_allowed(host, authoritative_domains):
        return False, "primary_source_not_authoritative"
    if weak_host and host == weak_host:
        return False, "weak_source_cannot_self_authorize"

    final_url = _v3._v2._clean(authoritative_final_url) or url
    final_host = _v3.normalized_host(final_url)
    if not final_host or not _v3._v2._v1._host_allowed(final_host, authoritative_domains):
        return False, "authoritative_page_redirected_outside_allowlist"
    if weak_host and final_host == weak_host:
        return False, "weak_source_cannot_self_authorize"

    card_ok, card_reason = exact_event_identity(
        _v3._v2._current_candidate_surface(candidate), signal
    )
    if not card_ok:
        return False, card_reason

    page_surface = _v3._v2._clean(authoritative_page_surface)
    if not page_surface:
        return False, "authoritative_page_identity_unverified"
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
