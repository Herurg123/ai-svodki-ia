from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

VERSION = 1
MODE = "weak_source_exact_authoritative_binding"
TERMINAL_NEGATIVE_REASON_CODES = frozenset({
    "duplicate",
    "outside_window",
    "old_reprint",
    "minor_legal_event",
    "satire_or_fiction",
    "not_ai_news",
})
_ACTION_TERMS: dict[str, tuple[str, ...]] = {
    "replace": ("replace", "replaces", "replaced", "replacing", "supersede", "supersedes", "superseded", "superseding"),
    "release": ("release", "releases", "released", "releasing"),
    "launch": ("launch", "launches", "launched", "launching"),
    "introduce": ("introduce", "introduces", "introduced", "introducing"),
    "unveil": ("unveil", "unveils", "unveiled", "unveiling"),
    "update": ("update", "updates", "updated", "updating"),
    "upgrade": ("upgrade", "upgrades", "upgraded", "upgrading"),
    "ship": ("ship", "ships", "shipped", "shipping"),
    "rollout": ("rollout", "roll out", "rolls out", "rolled out", "rolling out"),
    "preview": ("preview", "previews", "previewed", "previewing"),
    "general_availability": ("general availability", "generally available", "ga release", "ga launch"),
    "retire": ("retire", "retires", "retired", "retiring", "discontinue", "discontinues", "discontinued", "discontinuing"),
}
_WORD_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _words(value: Any) -> list[str]:
    return [item.casefold() for item in _WORD_RE.findall(_clean(value))]


def _compact_identity(value: Any) -> str:
    return "".join(_words(value))


def _contains_sequence(text: str, anchor: str) -> bool:
    haystack = _words(text)
    needle = _words(anchor)
    if not needle or len(needle) > len(haystack):
        return False
    return any(
        haystack[index:index + len(needle)] == needle
        for index in range(len(haystack) - len(needle) + 1)
    )


def _host(value: Any) -> str:
    try:
        host = (urlsplit(_clean(value)).hostname or "").casefold().strip(".")
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _host_allowed(host: str, domains: tuple[str, ...]) -> bool:
    return bool(
        host
        and any(host == domain or host.endswith("." + domain) for domain in domains)
    )


def _candidate_text(candidate: dict[str, Any]) -> str:
    keywords = candidate.get("keywords") if isinstance(candidate.get("keywords"), list) else []
    facts = candidate.get("verified_facts") if isinstance(candidate.get("verified_facts"), list) else []
    return " ".join(
        [
            _clean(candidate.get("title")),
            _clean(candidate.get("organization")),
            _clean(candidate.get("event_type")),
            _clean(candidate.get("event_summary")),
            *[_clean(item) for item in keywords],
            *[_clean(item) for item in facts],
        ]
    )


def _rejection_text(rejection: dict[str, Any]) -> str:
    return " ".join([
        _clean(rejection.get("title")),
        _clean(rejection.get("reason")),
    ])


def _action_matches(text: str, event_type: Any, action: str) -> bool:
    folded = f"{text} {_clean(event_type)}".casefold()
    terms = _ACTION_TERMS.get(action, (action.replace("_", " "),))
    return any(term in folded for term in terms)


def qualifying_signals(report: Any, *, contract_version: int) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    if report.get("retrieval_quality_contract_version") != contract_version:
        return []
    rows = report.get("unresolved_signals")
    if not isinstance(rows, list):
        return []
    result: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        provenance = item.get("source_provenance")
        versions = item.get("product_version_anchors")
        actions = item.get("lifecycle_action_anchors")
        if not (
            item.get("status") == "unresolved"
            and item.get("reason_code") == "weak_source"
            and item.get("signal_class") == "weak_source_product"
            and item.get("resolution_required") is False
            and item.get("candidate_eligible") is False
            and item.get("resolution_eligibility") == "deferred_exact_authoritative_binding"
            and isinstance(provenance, dict)
            and _clean(provenance.get("url")).startswith("https://")
            and _host(provenance.get("url"))
            and _clean(item.get("organization"))
            and isinstance(versions, list)
            and any(_clean(value) for value in versions)
            and isinstance(actions, list)
            and any(_clean(value) for value in actions)
        ):
            continue
        result.append(dict(item))
    result.sort(
        key=lambda item: (
            -int(item.get("likely_significance_score", 0) or 0),
            _clean(item.get("signal_id")),
        )
    )
    return result


def select_signal(signals: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not signals:
        return None
    ordered = sorted(
        (dict(item) for item in signals if isinstance(item, dict)),
        key=lambda item: (
            -int(item.get("likely_significance_score", 0) or 0),
            _clean(item.get("signal_id")),
        ),
    )
    return ordered[0] if ordered else None


def build_query(signal: dict[str, Any]) -> str:
    organization = _clean(signal.get("organization"))
    versions = [
        _clean(value)
        for value in signal.get("product_version_anchors") or []
        if _clean(value)
    ][:2]
    actions = [
        _clean(value).replace("_", " ")
        for value in signal.get("lifecycle_action_anchors") or []
        if _clean(value)
    ][:1]
    parts = [organization, *versions, *actions, "latest"]
    query = " ".join(part for part in parts if part).strip()
    if not organization or not versions or not actions:
        raise ValueError("weak-source exact binding requires organization, version and lifecycle anchors")
    if any(token in query.casefold() for token in ("site:", "reuters", "bloomberg", "apnews", "ft.com")):
        raise ValueError("weak-source exact binding query must stay publisher-neutral")
    return query


def build_prompt(
    *,
    search_window: dict[str, Any],
    signal: dict[str, Any],
    archive: list[dict[str, Any]],
) -> str:
    query = build_query(signal)
    evidence = {
        key: signal.get(key)
        for key in (
            "signal_id",
            "title",
            "origin_direction",
            "evidence_reason",
            "organization",
            "product_version_anchors",
            "lifecycle_action_anchors",
            "source_provenance",
        )
    }
    return f"""Ты — P3b exact authoritative binding-проход редакции «ИИ-Сводки».

Строгое редакционное окно: {search_window.get('start_at')} → {search_window.get('end_at')}
Идентификатор направления: general_coverage_gaps
Версия exact binding: {VERSION}

Это opportunistic-проверка ОДНОГО weak-source сигнала в уже существующем optional
seventh Coverage slot. Она не создаёт восьмой поиск и не имеет права вытеснять
старый обязательный unresolved/unverified resolution.

Выполни РОВНО ОДИН source-neutral Web Search без API domain filter. Фактический
query ТОЧНО:
`{query}`

Weak-source карточка ниже является только указателем, НЕ доказательством. Чтобы
вернуть include/consider candidate, независимо найди авторитетный источник и
подтверди ТОЧНО ТО ЖЕ событие: ту же организацию, каждую указанную version/model
anchor и тот же lifecycle/action. Совпадение только компании запрещено. Similar
version запрещена. Preview и general availability являются разными lifecycle
событиями. Старый релиз/reprint не является подтверждением нового события.
Aggregator/source_provenance из weak evidence не может сам стать authoritative
proof. Для include/consider обязательны verification_status=verified и
freshness_status=new_event/material_update.

Если точное событие не доказано, не угадывай. Верни пустой candidates. Rejection
может считаться terminal только когда его title/url сами относятся к exact same
event; unverified/weak_source никогда не являются automatic closure.

Weak evidence:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

Archive:
{json.dumps(archive, ensure_ascii=False, indent=2)}

Верни только JSON по штатной Coverage-схеме."""


def candidate_exact_binding(
    candidate: Any,
    signal: dict[str, Any],
    *,
    authoritative_domains: tuple[str, ...],
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
    weak_host = _host((signal.get("source_provenance") or {}).get("url"))
    if not _host_allowed(source_host, authoritative_domains):
        return False, "primary_source_not_authoritative"
    if source_host == weak_host:
        return False, "weak_source_cannot_self_authorize"

    text = _candidate_text(candidate)
    versions = [
        _clean(value)
        for value in signal.get("product_version_anchors") or []
        if _clean(value)
    ]
    if not versions or not all(_contains_sequence(text, anchor) for anchor in versions):
        return False, "version_identity_mismatch"

    actions = [
        _clean(value)
        for value in signal.get("lifecycle_action_anchors") or []
        if _clean(value)
    ]
    if not actions or not all(
        _action_matches(text, candidate.get("event_type"), action)
        for action in actions
    ):
        return False, "lifecycle_identity_mismatch"
    return True, "exact_authoritative_binding"


def rejection_exact_terminal_binding(
    rejection: Any,
    signal: dict[str, Any],
    *,
    authoritative_domains: tuple[str, ...],
) -> tuple[bool, str]:
    if not isinstance(rejection, dict):
        return False, "rejection_not_object"
    if rejection.get("reason_code") not in TERMINAL_NEGATIVE_REASON_CODES:
        return False, "rejection_not_terminal"
    source_host = _host(rejection.get("url"))
    weak_host = _host((signal.get("source_provenance") or {}).get("url"))
    if not _host_allowed(source_host, authoritative_domains):
        return False, "rejection_source_not_authoritative"
    if source_host == weak_host:
        return False, "weak_source_cannot_self_authorize"

    text = _rejection_text(rejection)
    organization = _clean(signal.get("organization"))
    if organization and not _contains_sequence(text, organization):
        return False, "rejection_organization_mismatch"
    versions = [
        _clean(value)
        for value in signal.get("product_version_anchors") or []
        if _clean(value)
    ]
    if not versions or not all(_contains_sequence(text, anchor) for anchor in versions):
        return False, "rejection_version_mismatch"
    actions = [
        _clean(value)
        for value in signal.get("lifecycle_action_anchors") or []
        if _clean(value)
    ]
    if not actions or not all(_action_matches(text, "", action) for action in actions):
        return False, "rejection_lifecycle_mismatch"
    return True, "exact_terminal_negative"
