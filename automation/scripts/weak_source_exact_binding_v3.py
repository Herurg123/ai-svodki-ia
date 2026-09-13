from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

_V2_PATH = Path(__file__).with_name("weak_source_exact_binding_v2.py")
_V2_SPEC = importlib.util.spec_from_file_location(
    "weak_source_exact_binding_v2_for_v3",
    _V2_PATH,
)
assert _V2_SPEC and _V2_SPEC.loader
_v2 = importlib.util.module_from_spec(_V2_SPEC)
sys.modules[_V2_SPEC.name] = _v2
_V2_SPEC.loader.exec_module(_v2)

for _name in dir(_v2):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_v2, _name)

# This is an implementation hardening of the existing exact-binding contract, not
# a new durable request-contract generation. Keep VERSION/MODE stable so saved v2
# P3b journals can still be recognized and fail/replay under the same contract.
VERSION = _v2.VERSION
MODE = _v2.MODE

_ROLE_ENTITY_RE = re.compile(
    r"\b(?:rival|competitor|partner|supplier|customer|vendor|lab|company|organization)\b",
    re.I,
)
_REPORTING_SUBJECT_RE = re.compile(
    r"\b(?:"
    r"says?|said|reports?|reported|claims?|claimed|writes?|wrote|notes?|noted|"
    r"cites?|cited|quotes?|quoted|confirms?|confirmed|states?|stated"
    r")\b\s+(?:that\s+)?(?:the\s+|a\s+|an\s+)?"
    r"[a-z0-9][a-z0-9.+-]*\s*$",
    re.I,
)
_EVENT_BINDING_BREAK_RE = re.compile(
    r"\b(?:while|whereas|although|though|however|but)\b",
    re.I,
)
_EVENT_CONNECTOR_WORDS = frozenset({
    "a", "an", "and", "announces", "announced", "announce", "also", "as", "at",
    "by", "confirms", "confirmed", "confirm", "currently", "for", "from", "has",
    "have", "had", "in", "is", "its", "newly", "now", "officially", "on", "or",
    "says", "said", "reports", "reported", "states", "stated", "the", "this", "to",
    "today", "was", "were", "with",
})
_NONCURRENT_ACTION_PREFIX_RE = re.compile(
    r"(?:"
    r"\b(?:plan|plans|planned|planning|intend|intends|intended|intending|aim|aims|aimed|aiming|"
    r"expect|expects|expected|expecting|schedule|schedules|scheduled|scheduling|propose|proposes|"
    r"proposed|consider|considers|considered|considering)\b(?:\W+\w+){0,4}\W*$|"
    r"\b(?:may|might|could|would|will|should)\b(?:\W+\w+){0,3}\W*$|"
    r"\b(?:set|due|slated)\s+to\b(?:\W+\w+){0,3}\W*$|"
    r"\b(?:cancel|cancels|cancelled|canceled|abandon|abandons|abandoned|scrap|scraps|scrapped|"
    r"delay|delays|delayed|postpone|postpones|postponed|pause|pauses|paused|halt|halts|halted)\b"
    r"(?:\W+\w+){0,3}\W*$"
    r")",
    re.I,
)
_EXPLICIT_HISTORICAL_YEAR_RE = re.compile(
    r"\b(?:in|during|back\s+in|since)\s+(?:19|20)\d{2}\b",
    re.I,
)
_LIFECYCLE_WORD_RE = re.compile(
    r"\b(?:"
    r"replace|replaces|replaced|replacing|replacement|supersede|supersedes|superseded|superseding|"
    r"preview|pre[- ]?release|prerelease|beta|early\s+access|general\s+availability|"
    r"generally\s+available|stable\s+release|launch|launches|launched|release|releases|released|"
    r"update|updates|updated|upgrade|upgrades|upgraded|benchmark|benchmarks|benchmarked|evaluation|"
    r"eval|score|scores"
    r")\b",
    re.I,
)


def _anchor_followed_by_variant_suffix(text: str, match_end: int) -> bool:
    tail = text[match_end:]
    next_word = re.match(
        r"(?:\s+|\s*[\(\[]\s*)([A-Za-z0-9][A-Za-z0-9.+-]*)",
        tail,
    )
    if next_word is None:
        return False
    raw_token = next_word.group(1)
    token = raw_token.casefold()
    if token in _v2._ANCHOR_ALLOWED_FOLLOWING_WORDS:
        return False
    # Exact identity is fail-closed: an unknown adjacent lexical continuation can
    # be a model/version suffix just as easily as a capitalized or numeric one.
    return True


def _exact_anchor_spans(text: str, anchor: str) -> list[tuple[int, int]]:
    anchor = _v2._clean(anchor)
    cleaned = _v2._clean(text)
    if not anchor or not cleaned:
        return []
    spans: list[tuple[int, int]] = []
    for match in re.finditer(_v2._anchor_pattern(anchor), cleaned, re.I):
        if not _anchor_followed_by_variant_suffix(cleaned, match.end()):
            spans.append(match.span())
    return spans


def _contains_exact_anchor(text: str, anchor: str) -> bool:
    return bool(_exact_anchor_spans(text, anchor))


def _strip_signal_identity(text: str, signal: dict[str, Any]) -> str:
    result = str(text or "")
    for anchor in sorted(_v2._anchors(signal), key=len, reverse=True):
        result = re.sub(_v2._anchor_pattern(anchor), " ", result, flags=re.I)
    organization = _v2._clean(signal.get("organization"))
    if organization:
        result = re.sub(
            rf"(?<![\w]){re.escape(organization)}(?![\w])",
            " ",
            result,
            flags=re.I,
        )
    return result


def _segment_has_foreign_event_subject(text: str, signal: dict[str, Any]) -> bool:
    cleaned = _strip_signal_identity(text, signal)
    if not cleaned.strip():
        return False
    if _ROLE_ENTITY_RE.search(cleaned):
        return True
    if _REPORTING_SUBJECT_RE.search(cleaned):
        return True
    if _EVENT_BINDING_BREAK_RE.search(cleaned):
        return True
    if any(
        match.group(0).casefold() not in _v2._EVENT_ENTITY_GENERIC_TOKENS
        for match in _v2._EVENT_ENTITY_TOKEN_RE.finditer(cleaned)
    ):
        return True

    # Lowercase organizations are otherwise invisible to the proper-name regex.
    # Between an already-known signal organization and its lifecycle verb, an
    # unexplained content token is an alternate subject candidate. Keep only a
    # deliberately small connector vocabulary and ordinary adverbs.
    words = re.findall(r"[A-Za-z][A-Za-z0-9.+-]*", cleaned)
    for word in words:
        folded = word.casefold()
        if folded in _EVENT_CONNECTOR_WORDS or folded.endswith("ly"):
            continue
        return True
    return False


def _organization_binds_action_span(
    claim: str,
    signal: dict[str, Any],
    action_span: tuple[int, int],
) -> bool:
    organization = _v2._clean(signal.get("organization"))
    if not organization:
        return False
    start, end = action_span
    for org_match in _v2._term_matches(claim, organization):
        if org_match.end() <= start:
            between = claim[org_match.end():start]
            if not _segment_has_foreign_event_subject(between, signal):
                return True
        elif org_match.start() >= end:
            between = claim[end:org_match.start()]
            prefix = claim[:start]
            if (
                not _segment_has_foreign_event_subject(between, signal)
                and not _segment_has_foreign_event_subject(prefix, signal)
            ):
                return True
    return False


def _action_binds_identity_anchors(
    claim: str,
    signal: dict[str, Any],
    action_span: tuple[int, int],
) -> bool:
    start, end = action_span
    for anchor in _v2._anchors(signal):
        linked = False
        for anchor_start, anchor_end in _exact_anchor_spans(claim, anchor):
            if anchor_start >= end:
                segment = claim[end:anchor_start]
            elif anchor_end <= start:
                segment = claim[anchor_end:start]
            else:
                segment = ""
            if _LIFECYCLE_WORD_RE.search(segment):
                continue
            if _segment_has_foreign_event_subject(segment, signal):
                continue
            linked = True
            break
        if not linked:
            return False
    return True


def _action_mention_is_noncurrent(text: str, start: int) -> bool:
    prefix = text[max(0, start - 104):start]
    return bool(_NONCURRENT_ACTION_PREFIX_RE.search(prefix))


def _action_mention_is_historical(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 120):start]
    suffix = text[end:min(len(text), end + 120)]
    if _v2._CURRENT_ACTION_NEAR_RE.search(prefix[-40:]) or _v2._CURRENT_ACTION_NEAR_RE.search(suffix[:40]):
        return False
    local = prefix + " " + suffix
    return bool(
        _v2._HISTORICAL_ACTION_PREFIX_RE.search(prefix)
        or _v2._HISTORICAL_ACTION_SUFFIX_RE.search(suffix)
        or _EXPLICIT_HISTORICAL_YEAR_RE.search(local)
    )


def _span_state(text: str, span: tuple[int, int]) -> str | None:
    start, end = span
    if _v2._action_mention_is_negated(text, start):
        return "lifecycle_negated"
    if _action_mention_is_noncurrent(text, start):
        return "lifecycle_noncurrent"
    if _action_mention_is_historical(text, start, end):
        return "historical_event_context"
    return None


def _active_term_span(
    text: str,
    terms: tuple[str, ...],
) -> tuple[tuple[int, int] | None, str | None]:
    seen_reasons: list[str] = []
    for term in terms:
        for match in _v2._term_matches(text, term):
            reason = _span_state(text, match.span())
            if reason is None:
                return match.span(), None
            seen_reasons.append(reason)
    for preferred in ("lifecycle_negated", "lifecycle_noncurrent", "historical_event_context"):
        if preferred in seen_reasons:
            return None, preferred
    return None, "lifecycle_identity_mismatch"


def _directed_replace_spans(
    text: str,
    old_anchor: str,
    new_anchor: str,
) -> list[tuple[int, int]]:
    cleaned = _v2._clean(text)
    old = _v2._anchor_pattern(old_anchor)
    new = _v2._anchor_pattern(new_anchor)
    relation = r"(?:replace|replaces|replaced|replacing|supersede|supersedes|superseded|superseding)"
    patterns = (
        rf"{relation}\s+{old}\s+(?:with|by)\s+{new}",
        rf"{new}\s+{relation}\s+{old}",
        rf"{old}\s+(?:is\s+|was\s+)?(?:replaced|superseded)\s+by\s+{new}",
    )
    spans: list[tuple[int, int]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned, re.I):
            segment = cleaned[match.start():match.end()]
            if not _contains_exact_anchor(segment, old_anchor):
                continue
            if not _contains_exact_anchor(segment, new_anchor):
                continue
            if match.span() not in spans:
                spans.append(match.span())
    spans.sort()
    return spans


def _active_replace_span(
    claim: str,
    old_anchor: str,
    new_anchor: str,
) -> tuple[tuple[int, int] | None, str | None]:
    seen_reasons: list[str] = []
    for span in _directed_replace_spans(claim, old_anchor, new_anchor):
        reason = _span_state(claim, span)
        if reason is None:
            return span, None
        seen_reasons.append(reason)
    for preferred in ("lifecycle_negated", "lifecycle_noncurrent", "historical_event_context"):
        if preferred in seen_reasons:
            return None, preferred
    return None, "replacement_direction_mismatch"


def _replacement_direction_conflict(
    text: str,
    signal: dict[str, Any],
    roles: tuple[str, str],
) -> bool:
    old_anchor, new_anchor = roles
    for claim in _v2._event_claims(text):
        for span in _directed_replace_spans(claim, new_anchor, old_anchor):
            if _span_state(claim, span) is None:
                return True
    return False


def _claim_lifecycle_matches(
    claim: str,
    signal: dict[str, Any],
    *,
    require_current_lifecycle: bool,
) -> tuple[bool, str]:
    actions = _v2._actions(signal)
    for action in actions:
        if action == "replace":
            if require_current_lifecycle and _v2._BENCHMARK_RE.search(claim):
                return False, "benchmark_lifecycle_mismatch"
            roles, role_reason = _v2._replacement_roles(signal)
            if roles is None:
                return False, role_reason
            old_anchor, new_anchor = roles
            span, reason = _active_replace_span(claim, old_anchor, new_anchor)
            if span is None:
                return False, str(reason or "replacement_direction_mismatch")
            if not _organization_binds_action_span(claim, signal, span):
                return False, "organization_event_attribution_mismatch"
            continue

        terms = _v2._LIFECYCLE_GROUPS.get(action, (action,))
        span, reason = _active_term_span(claim, terms)
        if span is None:
            return False, str(reason or "lifecycle_identity_mismatch")
        if not _organization_binds_action_span(claim, signal, span):
            return False, "organization_event_attribution_mismatch"
        if not _action_binds_identity_anchors(claim, signal, span):
            return False, "model_action_attribution_mismatch"

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


def _identity_surface_matches(
    text: str,
    signal: dict[str, Any],
    *,
    require_current_lifecycle: bool,
) -> tuple[bool, str]:
    text = _v2._clean(text)
    if not text:
        return False, "event_surface_missing"
    if not _v2._contains_org(text, signal.get("organization")):
        return False, "organization_identity_mismatch"
    anchors = _v2._anchors(signal)
    if not anchors:
        return False, "version_identity_missing"
    for anchor in anchors:
        if not _contains_exact_anchor(text, anchor):
            return False, "version_identity_mismatch"
    actions = _v2._actions(signal)
    if not actions:
        return False, "lifecycle_identity_missing"

    if "replace" in actions:
        roles, role_reason = _v2._replacement_roles(signal)
        if roles is None:
            return False, role_reason
        if _replacement_direction_conflict(text, signal, roles):
            return False, "replacement_direction_conflict"

    candidate_claims = [
        claim
        for claim in _v2._event_claims(text)
        if _v2._contains_org(claim, signal.get("organization"))
        and all(_contains_exact_anchor(claim, anchor) for anchor in anchors)
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
        "lifecycle_noncurrent",
        "historical_event_context",
        "replacement_direction_conflict",
        "benchmark_lifecycle_mismatch",
        "preview_ga_mismatch",
        "replacement_direction_mismatch",
        "organization_event_attribution_mismatch",
        "model_action_attribution_mismatch",
        "lifecycle_identity_mismatch",
    ):
        if preferred in reasons:
            return False, preferred
    return False, reasons[0] if reasons else "exact_event_claim_missing"


def exact_event_identity(surface: str, signal: dict[str, Any]) -> tuple[bool, str]:
    return _identity_surface_matches(surface, signal, require_current_lifecycle=True)


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
    if normalized_org(candidate.get("organization")) != normalized_org(signal.get("organization")):
        return False, "organization_identity_mismatch"
    url = candidate_source_url(candidate)
    host = normalized_host(url)
    weak_host = normalized_host(((signal.get("source_provenance") or {}).get("url")))
    if not host or not _v2._v1._host_allowed(host, authoritative_domains):
        return False, "primary_source_not_authoritative"
    if weak_host and host == weak_host:
        return False, "weak_source_cannot_self_authorize"
    final_url = _v2._clean(authoritative_final_url) or url
    final_host = normalized_host(final_url)
    if not final_host or not _v2._v1._host_allowed(final_host, authoritative_domains):
        return False, "authoritative_page_redirected_outside_allowlist"
    if weak_host and final_host == weak_host:
        return False, "weak_source_cannot_self_authorize"
    card_ok, card_reason = exact_event_identity(_v2._current_candidate_surface(candidate), signal)
    if not card_ok:
        return False, card_reason
    page_surface = _v2._clean(authoritative_page_surface)
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
    return _v2.rejection_exact_terminal_binding(
        rejection,
        signal,
        authoritative_domains=authoritative_domains,
    )
