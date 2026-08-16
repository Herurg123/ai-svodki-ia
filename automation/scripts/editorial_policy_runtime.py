#!/usr/bin/env python3
"""Runtime corrections for deterministic editorial validation.

Production entry points import this module before calling the shared editorial
validator. The corrections are deliberately narrow: preserve every unrelated
policy error, accept only the explicitly allowed Russian wording, classify the
regional section from a story's primary subject rather than a secondary model
reference, normalize one safe research-ranking metadata contradiction, restore
source metadata from the paid research pool instead of asking the model to copy
URLs perfectly, and repair the one mandatory world-section heading when the
model omits it from an otherwise structurally valid short digest.
"""
from __future__ import annotations

import copy
import html
import re
from typing import Any, Callable

AGENT_ERROR = "Используй «агент ИИ», а не AI agent или AI-агент."
WORLD_HEADING = "Мировые лидеры ИИ"
Validator = Callable[..., tuple[list[str], list[str], dict[str, Any]]]
EditorialValidator = Callable[..., Any]
ResearchSanitizer = Callable[..., Any]
UrlNormalizer = Callable[[str], str]


def actual_prohibited_agent_form(text: str) -> bool:
    """Return True only for the explicitly forbidden noun forms."""

    patterns = (
        r"\bAI\s+agents?\b",
        r"\bAI[- ]агент(?:а|у|ом|е|ы|ов|ам|ами|ах)?\b",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def primary_subject_is_asia(
    candidate: dict[str, Any], policy: dict[str, Any]
) -> bool:
    """Classify the China/Asia section from the story's primary subject.

    ``organization`` may contain several semicolon-separated entities. The first
    one is the event subject; later entities can be dependencies, suppliers or
    model provenance. Counting every later name made Writer + Z.ai look like a
    Chinese story on 2026-08-15 and triggered an invalid structural retry.
    """

    tracked = [
        str(item).strip().casefold()
        for item in policy.get("tracked_asia_organizations", [])
        if str(item).strip()
    ]
    organization = str(candidate.get("organization") or "").strip()
    primary = organization.split(";", 1)[0].strip().casefold()
    if primary and any(name in primary for name in tracked):
        return True
    # A secondary tracked organization is a regional subject only when the
    # editorial title itself names it as a party to the event. This keeps
    # metadata-only provenance such as Writer; Z.ai out of the China section,
    # while joint events such as Uber; Pony.ai are classified correctly.
    title = str(candidate.get("title") or "").casefold()
    return any(name in title for name in tracked)


def _selected_candidates_and_policy(
    args: tuple[Any, ...], kwargs: dict[str, Any]
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    selected = args[0] if len(args) >= 1 else kwargs.get("selected_candidates")
    policy = args[2] if len(args) >= 3 else kwargs.get("policy")
    if not isinstance(selected, list) or not isinstance(policy, dict):
        return None, None
    candidates = [item for item in selected if isinstance(item, dict)]
    return candidates, policy


def wrap_validator(original: Validator) -> Validator:
    """Wrap one article validator while preserving every unrelated error."""

    if getattr(original, "_ai_svodki_agent_policy_fixed", False):
        return original

    def corrected(
        article_html: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[list[str], list[str], dict[str, Any]]:
        errors, warnings, analysis = original(article_html, *args, **kwargs)
        filtered = list(errors)
        updated_warnings = list(warnings)

        if AGENT_ERROR in filtered:
            try:
                import editorial_policy

                visible_text = editorial_policy.parse_article(article_html).visible_text
            except Exception:
                visible_text = article_html

            if not actual_prohibited_agent_form(visible_text):
                filtered = [error for error in filtered if error != AGENT_ERROR]
                updated_warnings.append(
                    "Игнорировано ложное совпадение AI + прилагательное «агентный»: "
                    "название продукта с AI не является формой AI-агент."
                )

        selected, policy = _selected_candidates_and_policy(args, kwargs)
        if selected is not None and policy is not None:
            china_heading = str(
                policy.get("article", {}).get(
                    "china_heading", "Китайские лидеры ИИ"
                )
            )
            china_required_error = (
                f"При выбранных китайских сюжетах заголовок «{china_heading}» "
                "должен встречаться ровно один раз."
            )
            if (
                china_required_error in filtered
                and not any(primary_subject_is_asia(item, policy) for item in selected)
            ):
                filtered = [
                    error for error in filtered if error != china_required_error
                ]
                updated_warnings.append(
                    "Игнорировано ложное требование китайского раздела: "
                    "азиатский бренд присутствует только как вторичная организация, "
                    "а не основной субъект выбранного сюжета."
                )

        return filtered, updated_warnings, analysis

    setattr(corrected, "_ai_svodki_agent_policy_fixed", True)
    setattr(corrected, "__wrapped__", original)
    return corrected


def _research_sources(research: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    candidates = research.get("candidates")
    if not isinstance(candidates, list):
        return sources
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        primary = candidate.get("primary_source")
        if isinstance(primary, dict):
            sources.append(primary)
        supporting = candidate.get("supporting_sources")
        if isinstance(supporting, list):
            sources.extend(item for item in supporting if isinstance(item, dict))
    return sources


def _canonical_sources_by_url(
    research: dict[str, Any],
    normalize_url: UrlNormalizer,
) -> dict[str, dict[str, Any]]:
    canonical_by_url: dict[str, dict[str, Any]] = {}
    for source in _research_sources(research):
        raw_url = str(source.get("url", "")).strip()
        if not raw_url:
            continue
        try:
            key = normalize_url(raw_url)
        except Exception:
            continue
        canonical_by_url.setdefault(key, copy.deepcopy(source))
    return canonical_by_url


def _normalize_article_source_links(
    article_html: str,
    canonical_by_url: dict[str, dict[str, Any]],
    normalize_url: UrlNormalizer,
) -> tuple[str, list[dict[str, Any]]]:
    changes: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?P<prefix><a\b[^>]*\bhref\s*=\s*)"
        r"(?P<quote>[\"'])(?P<url>[^\"']+)(?P=quote)",
        flags=re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        raw_url = html.unescape(match.group("url")).strip()
        try:
            key = normalize_url(raw_url)
        except Exception:
            return match.group(0)
        canonical = canonical_by_url.get(key)
        if canonical is None:
            return match.group(0)
        canonical_url = str(canonical.get("url", "")).strip()
        if not canonical_url or canonical_url == raw_url:
            return match.group(0)
        changes.append(
            {
                "field": "digest.article_html.href",
                "model_url": raw_url,
                "canonical_url": canonical_url,
            }
        )
        escaped_url = html.escape(canonical_url, quote=True)
        return (
            match.group("prefix")
            + match.group("quote")
            + escaped_url
            + match.group("quote")
        )

    return pattern.sub(replace, article_html), changes


def normalize_editorial_structure(editorial: dict[str, Any]) -> list[dict[str, Any]]:
    """Restore the mandatory world heading without weakening validation.

    The editorial contract has always required ``Мировые лидеры ИИ`` exactly
    once, including a Russia-only short digest. The model can reasonably omit
    an empty world section when every selected story is Russian, which used to
    make all downstream validators reject an otherwise publishable digest.

    Repair only the single missing heading. Duplicates, missing story blocks,
    malformed HTML and every other structural problem remain validator errors.
    """

    digest = editorial.get("digest")
    if not isinstance(digest, dict):
        return []
    article_html = digest.get("article_html")
    if not isinstance(article_html, str) or not article_html.strip():
        return []

    try:
        import editorial_policy

        h2_texts = editorial_policy.parse_article(article_html).h2_texts
    except Exception:
        h2_texts = []
    if WORLD_HEADING in h2_texts:
        return []

    first_h2 = re.search(r"<h2\b[^>]*>", article_html, flags=re.IGNORECASE)
    if first_h2 is None:
        return []

    insertion = f"<h2>{WORLD_HEADING}</h2>"
    digest["article_html"] = (
        article_html[: first_h2.start()]
        + insertion
        + article_html[first_h2.start() :]
    )
    return [
        {
            "field": "digest.article_html.world_heading",
            "model_value": None,
            "normalized_value": insertion,
        }
    ]


def normalize_editorial_sources(
    editorial: dict[str, Any],
    research: dict[str, Any],
    normalize_url: UrlNormalizer,
) -> list[dict[str, Any]]:
    """Restore exact source metadata and links already present in research.

    The model may remove a trailing slash or repeat a publisher title with a
    cosmetic difference. Source identity is owned by ``candidates.json``;
    editorial may select and cite a source, but it must not redefine it. New or
    unknown URLs are intentionally left untouched so the original validator can
    reject them.
    """

    digest = editorial.get("digest")
    if not isinstance(digest, dict):
        return []

    canonical_by_url = _canonical_sources_by_url(research, normalize_url)
    changes: list[dict[str, Any]] = []
    editorial_sources = digest.get("sources")
    if isinstance(editorial_sources, list):
        for index, source in enumerate(editorial_sources):
            if not isinstance(source, dict):
                continue
            raw_url = str(source.get("url", "")).strip()
            if not raw_url:
                continue
            try:
                key = normalize_url(raw_url)
            except Exception:
                continue
            canonical = canonical_by_url.get(key)
            if canonical is None or source == canonical:
                continue
            editorial_sources[index] = copy.deepcopy(canonical)
            changes.append(
                {
                    "field": f"digest.sources[{index}]",
                    "model_url": raw_url,
                    "canonical_url": str(canonical.get("url", "")),
                }
            )

    article_html = digest.get("article_html")
    if isinstance(article_html, str):
        normalized_html, link_changes = _normalize_article_source_links(
            article_html,
            canonical_by_url,
            normalize_url,
        )
        digest["article_html"] = normalized_html
        changes.extend(link_changes)
    return changes


def wrap_editorial_validator(
    original: EditorialValidator,
    normalize_url: UrlNormalizer,
) -> EditorialValidator:
    """Normalize deterministic structure/source seams immediately before validation."""

    if getattr(original, "_ai_svodki_source_metadata_fixed", False):
        return original

    def corrected(
        editorial: dict[str, Any],
        research: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if isinstance(editorial, dict) and isinstance(research, dict):
            normalize_editorial_structure(editorial)
            normalize_editorial_sources(editorial, research, normalize_url)
        return original(editorial, research, *args, **kwargs)

    setattr(corrected, "_ai_svodki_source_metadata_fixed", True)
    setattr(corrected, "__wrapped__", original)
    return corrected


def normalize_research_recommendations(
    research: dict[str, Any],
) -> list[dict[str, Any]]:
    """Repair the deterministic ``include``/score contradiction before validation.

    The downstream validator already requires ``include`` to have
    ``significance_score >= 3``. Structured Output validates those two fields
    independently, so a model can still emit an otherwise valid candidate with
    ``include`` and score 1-2. Preserve the score and every factual/source field,
    but downgrade only that contradictory recommendation to ``consider``.
    """

    candidates = research.get("candidates")
    if not isinstance(candidates, list):
        return []

    changes: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue
        score = candidate.get("significance_score")
        if (
            candidate.get("recommendation") == "include"
            and isinstance(score, int)
            and score < 3
        ):
            candidate["recommendation"] = "consider"
            changes.append(
                {
                    "candidate_id": str(candidate.get("id") or f"candidate-{index}"),
                    "significance_score": score,
                    "from": "include",
                    "to": "consider",
                }
            )
    return changes


def wrap_research_sanitizer(original: ResearchSanitizer) -> ResearchSanitizer:
    """Normalize safe ranking metadata after sanitation and before validation."""

    if getattr(original, "_ai_svodki_recommendation_contract_fixed", False):
        return original

    def corrected(research: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        result = original(research, *args, **kwargs)
        if not isinstance(result, tuple) or len(result) != 3:
            return result
        sanitized, filtered, warnings = result
        if not isinstance(sanitized, dict):
            return result
        changes = normalize_research_recommendations(sanitized)
        if not changes:
            return result
        updated_warnings = list(warnings) if isinstance(warnings, list) else []
        details = ", ".join(
            f"{item['candidate_id']}:{item['significance_score']}"
            for item in changes
        )
        updated_warnings.append(
            "Нормализованы противоречивые research-рекомендации "
            f"include→consider без изменения significance_score: {details}."
        )
        return sanitized, filtered, updated_warnings

    setattr(corrected, "_ai_svodki_recommendation_contract_fixed", True)
    setattr(corrected, "__wrapped__", original)
    return corrected


def patch_research_validation(module: Any) -> ResearchSanitizer | None:
    """Patch one generator research sanitizer when that seam is available."""

    original = getattr(module, "sanitize_research_candidates", None)
    if original is None:
        return None
    corrected = wrap_research_sanitizer(original)
    module.sanitize_research_candidates = corrected
    return corrected


def patch_editorial_policy(*consumer_modules: Any) -> Validator:
    """Patch the shared article validator and direct-import consumer bindings."""

    import editorial_policy

    corrected = wrap_validator(editorial_policy.validate_article_policy)
    editorial_policy.validate_article_policy = corrected
    for module in consumer_modules:
        if hasattr(module, "validate_article_policy"):
            module.validate_article_policy = corrected
    return corrected


def patch_editorial_source_validation(module: Any) -> EditorialValidator:
    """Patch deterministic research/editorial seams without weakening validation."""

    patch_research_validation(module)
    if not hasattr(module, "validate_editorial") or not hasattr(module, "normalize_url"):
        raise RuntimeError("Generator module lacks editorial validation helpers")
    corrected = wrap_editorial_validator(
        module.validate_editorial,
        module.normalize_url,
    )
    module.validate_editorial = corrected
    return corrected
