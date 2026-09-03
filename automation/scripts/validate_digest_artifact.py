#!/usr/bin/env python3
"""Public digest-artifact validator with shared-source story mapping.

The established validator remains byte-for-byte in
``validate_digest_artifact_base.py``. This entry point replaces only the final
story/source identity check so a URL legitimately shared by multiple research
candidates cannot make an otherwise explicit ``candidate_id`` mapping
ambiguous. The split is an active compatibility seam and should be consolidated
on the next material artifact-validator refactor or after 2026-10-03.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_BASE_PATH = Path(__file__).with_name("validate_digest_artifact_base.py")
_BASE_SPEC = importlib.util.spec_from_file_location(
    "validate_digest_artifact_base", _BASE_PATH
)
assert _BASE_SPEC and _BASE_SPEC.loader
_base = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _base
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_base, _name)


def validate_story_mapping(
    article_html: str,
    candidates_payload: Any,
    selection_payload: Any,
    stories_payload: Any,
    report: dict[str, Any],
) -> None:
    """Validate HTML stories against explicit story IDs and final story sources.

    Candidate research may legitimately reuse one source URL across several
    candidates. Identity therefore comes from the already-validated
    ``selection.selected_candidate_ids`` / ``stories[].candidate_id`` order,
    while ``stories[].sources`` owns the exact source set selected for each final
    story. Raw candidate URLs remain a provenance boundary: final story sources
    still have to come from the expected candidate.
    """

    candidates = json_list(candidates_payload, "candidates")
    stories = json_list(stories_payload, "stories")
    selected_raw = (
        selection_payload.get("selected_candidate_ids")
        if isinstance(selection_payload, dict)
        else None
    )
    if not isinstance(selected_raw, list):
        issue(
            report,
            "errors",
            "selected_ids_missing",
            "selection.json не содержит selected_candidate_ids[].",
        )
        return

    selected_ids = [str(value) for value in selected_raw]
    story_ids = [
        value for value in (story_id(story) for story in stories) if value is not None
    ]
    if len(story_ids) != len(stories):
        issue(
            report,
            "errors",
            "story_candidate_id",
            "Каждая запись stories.json должна содержать candidate_id.",
        )
    if story_ids != selected_ids:
        issue(
            report,
            "errors",
            "story_order",
            "Порядок candidate_id в stories.json не совпадает с "
            f"selected_candidate_ids: {story_ids} != {selected_ids}.",
        )

    candidate_map: dict[str, set[str]] = {}
    for candidate in candidates:
        cid = candidate_id(candidate)
        if cid is None:
            issue(
                report,
                "errors",
                "candidate_id",
                "У кандидата отсутствует candidate_id/id.",
            )
            continue
        if cid in candidate_map:
            issue(
                report,
                "errors",
                "duplicate_candidate_id",
                f"Повторяющийся candidate_id: {cid}.",
            )
        candidate_map[cid] = recursive_urls(candidate)

    missing = [cid for cid in selected_ids if cid not in candidate_map]
    if missing:
        issue(
            report,
            "errors",
            "selected_candidate_missing",
            f"Выбранные кандидаты отсутствуют в candidates.json: {missing}.",
        )

    inspector = ArticleInspector()
    inspector.feed(article_html)
    inspector.close()
    if len(inspector.stories) != len(selected_ids):
        issue(
            report,
            "errors",
            "html_story_count",
            "Число сюжетов <h3> "
            f"({len(inspector.stories)}) не совпадает с selected_candidate_ids "
            f"({len(selected_ids)}).",
        )
        return

    for index, block in enumerate(inspector.stories):
        expected_id = selected_ids[index]
        story = stories[index] if index < len(stories) and isinstance(stories[index], dict) else {}

        expected_headline = normalize_space(str(story.get("headline") or ""))
        actual_headline = normalize_space(str(block.headline or ""))
        if not expected_headline:
            issue(
                report,
                "errors",
                "story_headline_missing",
                f"У stories.json[{index}] отсутствует headline для {expected_id}.",
            )
        elif actual_headline != expected_headline:
            issue(
                report,
                "errors",
                "story_headline_order",
                f"HTML-сюжет #{index + 1} не соответствует {expected_id}: "
                f"{actual_headline!r} != {expected_headline!r}.",
            )

        story_urls = recursive_urls(story.get("sources", []))
        if not story_urls:
            issue(
                report,
                "errors",
                "story_sources_missing",
                f"У stories.json[{index}] для {expected_id} нет source URL.",
            )
            continue

        candidate_urls = candidate_map.get(expected_id, set())
        foreign_story_urls = sorted(story_urls - candidate_urls)
        if foreign_story_urls:
            issue(
                report,
                "errors",
                "story_source_not_candidate",
                f"Источники stories.json для {expected_id} отсутствуют у этого "
                f"кандидата: {foreign_story_urls}.",
            )

        block_urls = set(block.links)
        if not block_urls:
            issue(
                report,
                "errors",
                "story_source_links",
                f"У сюжета «{block.headline}» нет цитируемых ссылок для сопоставления.",
            )
            continue

        unexpected_links = sorted(block_urls - story_urls)
        if unexpected_links:
            issue(
                report,
                "errors",
                "article_story_source_mismatch",
                f"Сюжет «{block.headline}» содержит ссылки, которых нет в "
                f"stories.json для {expected_id}: {unexpected_links}.",
            )


_base.validate_story_mapping = validate_story_mapping


def main() -> int:
    _base.validate_story_mapping = validate_story_mapping
    return int(_base.main())


if __name__ == "__main__":
    raise SystemExit(main())
