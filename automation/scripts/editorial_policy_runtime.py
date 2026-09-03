#!/usr/bin/env python3
"""Active editorial runtime with deterministic full-pool diversity repair.

The established runtime corrections remain in ``editorial_policy_runtime_base``
and are re-exported here unchanged. The split exists because the 2026-09-03
production incident proved that a prompt-only publisher-diversity instruction is
not an executable invariant: the editorial model saw the exact rule and still
returned the same invalid three-publisher selection.

This wrapper adds one narrow zero-paid repair before the existing validator. It
never changes the selected story IDs. It may synthesize the publisher override
already allowed by the canonical editorial policy only when the over-cap selected
stories are independently eligible and strictly stronger, by significance score,
than every unselected eligible candidate from another publisher. All ambiguous or
neighboring cases remain fail-closed in the existing validator.

``editorial_policy_runtime_base`` is an active compatibility dependency, not an
inert archive. Keep it until these established runtime corrections can be
consolidated without changing production/recovery behavior; re-audit that split
on the next material editorial-runtime refactor or after 2026-10-03.
"""
from __future__ import annotations

import copy
from collections import Counter
from typing import Any

import editorial_policy_runtime_base as _base
from editorial_policy_runtime_base import *  # noqa: F401,F403

FULL_POOL_PUBLISHER_REPAIR_VERSION = 1


def _publisher(candidate: dict[str, Any]) -> tuple[str, str] | None:
    primary = candidate.get("primary_source")
    if not isinstance(primary, dict):
        return None
    display = str(primary.get("publisher") or "").strip()
    if not display:
        return None
    return display.casefold(), display


def _primary_subject(candidate: dict[str, Any]) -> str:
    organization = str(candidate.get("organization") or "").strip()
    return organization.split(";", 1)[0].strip().casefold()


def _primary_url(candidate: dict[str, Any]) -> str:
    primary = candidate.get("primary_source")
    if not isinstance(primary, dict):
        return ""
    return str(primary.get("url") or "").strip()


def _significance_score(candidate: dict[str, Any]) -> int | None:
    value = candidate.get("significance_score")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def normalize_full_pool_publisher_overrides(
    editorial: dict[str, Any],
    research: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Repair one mechanically omitted full-pool publisher override.

    The canonical policy treats publisher diversity as a soft balancing rule for
    a normal 7-12 story edition and permits an explicit override for independent,
    sufficiently significant events. The model remains responsible for selection.
    This function only records that already-authorized exception when a
    deterministic comparison proves there is no equally strong unselected
    baseline-eligible alternative from another publisher.

    Fail closed unless every guard below is satisfied:
    * normal/full pool and normal/full selection;
    * exactly one publisher exceeds the cap, and only by one story;
    * no existing reasoned publisher override for that publisher;
    * every over-cap publisher story is include + baseline eligible, score >= 3;
    * those stories have distinct primary subjects and distinct primary URLs;
    * every unselected eligible different-publisher alternative scores strictly
      below the weakest selected over-cap story.

    Organization diversity, article validity and all unrelated errors remain for
    the canonical validator to enforce.
    """

    diversity = policy.get("diversity")
    story_counts = policy.get("story_counts")
    candidates_raw = research.get("candidates")
    selected_ids = editorial.get("selected_candidate_ids")
    overrides = editorial.get("diversity_overrides")
    if not isinstance(diversity, dict) or not isinstance(story_counts, dict):
        return []
    if not isinstance(candidates_raw, list):
        return []
    if not isinstance(selected_ids, list) or not isinstance(overrides, list):
        return []

    try:
        target = int(story_counts.get("total_target_minimum", 0) or 0)
        publisher_cap = int(diversity.get("max_selected_per_publisher_soft", 0) or 0)
    except (TypeError, ValueError):
        return []
    if target <= 0 or publisher_cap <= 0:
        return []

    candidates = [item for item in candidates_raw if isinstance(item, dict)]
    eligible = [
        item for item in candidates if _base._baseline_selection_eligible(item, policy)
    ]
    if len(eligible) < target or len(selected_ids) < target:
        return []
    if len(set(str(item) for item in selected_ids)) != len(selected_ids):
        return []

    candidate_map = {str(item.get("id")): item for item in candidates}
    selected: list[dict[str, Any]] = []
    for raw_id in selected_ids:
        candidate = candidate_map.get(str(raw_id))
        if candidate is None:
            return []
        selected.append(candidate)

    counts: Counter[str] = Counter()
    display_values: dict[str, str] = {}
    for candidate in selected:
        publisher = _publisher(candidate)
        if publisher is None:
            continue
        key, display = publisher
        counts[key] += 1
        display_values.setdefault(key, display)

    over_cap = [
        (key, count)
        for key, count in counts.items()
        if count > publisher_cap
    ]
    if len(over_cap) != 1:
        return []
    publisher_key, publisher_count = over_cap[0]
    if publisher_count != publisher_cap + 1:
        return []

    existing_reasoned = {
        str(item.get("value") or "").strip().casefold()
        for item in overrides
        if isinstance(item, dict)
        and item.get("type") == "publisher"
        and str(item.get("reason") or "").strip()
    }
    if publisher_key in existing_reasoned:
        return []

    publisher_selected = [
        item for item in selected
        if (_publisher(item) or (None, None))[0] == publisher_key
    ]
    if len(publisher_selected) != publisher_count:
        return []
    if any(item.get("recommendation") != "include" for item in publisher_selected):
        return []
    if any(
        not _base._baseline_selection_eligible(item, policy)
        for item in publisher_selected
    ):
        return []

    selected_scores = [_significance_score(item) for item in publisher_selected]
    if any(score is None or score < 3 for score in selected_scores):
        return []
    weakest_selected = min(score for score in selected_scores if score is not None)

    subjects = [_primary_subject(item) for item in publisher_selected]
    if any(not subject for subject in subjects) or len(set(subjects)) != len(subjects):
        return []
    primary_urls = [_primary_url(item) for item in publisher_selected]
    if any(not url for url in primary_urls) or len(set(primary_urls)) != len(primary_urls):
        return []

    selected_id_set = {str(item) for item in selected_ids}
    alternative_scores: list[int] = []
    for candidate in eligible:
        if str(candidate.get("id")) in selected_id_set:
            continue
        publisher = _publisher(candidate)
        if publisher is None or publisher[0] == publisher_key:
            continue
        score = _significance_score(candidate)
        if score is not None:
            alternative_scores.append(score)
    best_alternative = max(alternative_scores, default=0)
    if best_alternative >= weakest_selected:
        return []

    publisher_display = display_values[publisher_key]
    override = {
        "type": "publisher",
        "value": publisher_display,
        "reason": (
            f"Сохранены {publisher_count} независимых verified-события от разных "
            f"основных организаций. Минимальный significance_score этой выбранной "
            f"группы — {weakest_selected}; лучший невыбранный baseline-eligible "
            f"кандидат другого издателя имеет score {best_alternative}, поэтому "
            "сопоставимой diversity-замены без потери значимости нет."
        ),
    }
    overrides.append(override)

    digest = editorial.get("digest")
    if isinstance(digest, dict):
        notes = digest.get("editorial_notes")
        if isinstance(notes, list):
            notes.append(
                {
                    "type": "diversity_override",
                    "area": "publisher",
                    "message": f"{publisher_display}: {override['reason']}",
                }
            )
    return [copy.deepcopy(override)]


def wrap_editorial_validator(
    original: EditorialValidator,
    normalize_url: UrlNormalizer,
) -> EditorialValidator:
    """Add the full-pool repair before all established runtime normalizers."""

    if getattr(original, "_ai_svodki_full_pool_publisher_fixed", False):
        return original

    established = _base.wrap_editorial_validator(original, normalize_url)

    def corrected(
        editorial: dict[str, Any],
        research: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        changes: list[dict[str, Any]] = []
        if isinstance(editorial, dict) and isinstance(research, dict):
            policy = _base._editorial_policy_from_validate_args(args, kwargs)
            if policy is not None:
                changes = normalize_full_pool_publisher_overrides(
                    editorial,
                    research,
                    policy,
                )
        result = established(editorial, research, *args, **kwargs)
        if not changes or not isinstance(result, tuple) or len(result) != 3:
            return result
        errors, warnings, stories = result
        updated_warnings = list(warnings) if isinstance(warnings, list) else []
        publishers = ", ".join(item["value"] for item in changes)
        updated_warnings.append(
            "Автоматически сохранён строго ограниченный full-pool publisher "
            f"diversity override: {publishers}."
        )
        return errors, updated_warnings, stories

    setattr(corrected, "_ai_svodki_full_pool_publisher_fixed", True)
    setattr(corrected, "__wrapped__", original)
    return corrected


def patch_editorial_source_validation(module: Any) -> EditorialValidator:
    """Patch deterministic seams and retain the canonical fail-closed validator."""

    _base.patch_research_validation(module)
    if not hasattr(module, "validate_editorial") or not hasattr(module, "normalize_url"):
        raise RuntimeError("Generator module lacks editorial validation helpers")
    corrected = wrap_editorial_validator(
        module.validate_editorial,
        module.normalize_url,
    )
    module.validate_editorial = corrected
    return corrected
