from __future__ import annotations

import html
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class PolicyHTMLParser(HTMLParser):
    """Collect editorial structure without changing the HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.h2_texts: list[str] = []
        self.h3_texts: list[str] = []
        self.story_paragraph_counts: list[int] = []
        self.story_links: list[list[str]] = []
        self.what_it_means_items = 0
        self.first_top_level_tag: str | None = None
        self.first_top_level_text = ""
        self.visible_parts: list[str] = []

        self._capture_tag: str | None = None
        self._capture_parts: list[str] = []
        self._current_h2: str | None = None
        self._current_story_paragraphs: int | None = None
        self._current_story_links: list[str] | None = None
        self._first_depth: int | None = None
        self._first_parts: list[str] = []

    def _finish_story(self) -> None:
        if self._current_story_paragraphs is not None:
            self.story_paragraph_counts.append(self._current_story_paragraphs)
            self.story_links.append(list(self._current_story_links or []))
            self._current_story_paragraphs = None
            self._current_story_links = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        top_level = not self.stack

        if top_level and self.first_top_level_tag is None:
            self.first_top_level_tag = tag
            self._first_depth = 1
            self._first_parts = []
        elif self._first_depth is not None:
            self._first_depth += 1

        if tag in {"h2", "h3"}:
            self._finish_story()
            self._capture_tag = tag
            self._capture_parts = []
            if tag == "h3":
                self._current_story_paragraphs = 0
                self._current_story_links = []

        if tag == "a" and self._current_story_links is not None:
            href = dict(attrs).get("href")
            if href:
                self._current_story_links.append(href.strip())

        if tag == "p" and self._current_story_paragraphs is not None:
            self._current_story_paragraphs += 1

        if tag == "li" and self._current_h2 == "Что это значит":
            self.what_it_means_items += 1

        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self._capture_tag == tag:
            text = re.sub(r"\s+", " ", "".join(self._capture_parts)).strip()
            if tag == "h2":
                self.h2_texts.append(text)
                self._current_h2 = text
            else:
                self.h3_texts.append(text)
            self._capture_tag = None
            self._capture_parts = []

        if self.stack:
            self.stack.pop()

        if self._first_depth is not None:
            self._first_depth -= 1
            if self._first_depth == 0:
                self.first_top_level_text = re.sub(
                    r"\s+", " ", "".join(self._first_parts)
                ).strip()
                self._first_depth = None

    def handle_data(self, data: str) -> None:
        if data:
            self.visible_parts.append(data)
        if self._capture_tag:
            self._capture_parts.append(data)
        if self._first_depth is not None:
            self._first_parts.append(data)

    def finish(self) -> None:
        self._finish_story()

    @property
    def visible_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.visible_parts)).strip()


def normalize_candidate_ids(candidates: list[Any]) -> list[dict[str, str]]:
    """Assign stable sequential IDs to candidate objects.

    Candidate IDs are internal references used only between the research and
    editorial stages. Structured output can still repeat a schema-valid ID,
    so normalize them deterministically after freshness filtering.
    """
    changes: list[dict[str, str]] = []
    next_number = 1

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        old_id = str(candidate.get("id", ""))
        new_id = f"cand-{next_number:03d}"
        next_number += 1

        candidate["id"] = new_id
        if old_id != new_id:
            changes.append({"old_id": old_id, "new_id": new_id})

    return changes


def read_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден editorial config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный editorial config: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("editorial.json должен содержать JSON-объект.")
    return value


def parse_article(article_html: str) -> PolicyHTMLParser:
    parser = PolicyHTMLParser()
    parser.feed(article_html)
    parser.close()
    parser.finish()
    return parser


def _remove_exact_paragraph(article_html: str, text: str) -> str:
    pattern = re.compile(
        r"<p>\s*" + re.escape(text) + r"\s*</p>\s*",
        flags=re.IGNORECASE,
    )
    return pattern.sub("", article_html)


def _remove_dzen_block(article_html: str, heading: str) -> str:
    pattern = re.compile(
        r"\s*<h2>\s*"
        + re.escape(heading)
        + r"\s*</h2>\s*"
        r"<p>\s*<a\b[^>]*href\s*=\s*(['\"])[^'\"]*\1[^>]*>.*?</a>\s*</p>\s*",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub("\n", article_html)


def _remove_meta_footnotes(article_html: str) -> str:
    return re.sub(
        r"\s*<p>\s*<em>\s*\*Meta\b.*?</em>\s*</p>\s*",
        "\n",
        article_html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _normalise_update_headings(
    article_html: str,
    selected_candidates: list[dict[str, Any]],
    headline_prefix: str,
) -> tuple[str, list[dict[str, Any]]]:
    changes: list[dict[str, Any]] = []
    index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal index
        original_inner = match.group(1)
        plain = re.sub(r"<[^>]+>", "", original_inner)
        plain = html.unescape(re.sub(r"\s+", " ", plain)).strip()
        plain_without_prefix = re.sub(
            r"^Обновление:\s*", "", plain, flags=re.IGNORECASE
        )

        if index < len(selected_candidates):
            candidate = selected_candidates[index]
            is_update = candidate.get("archive_status") == "update"
        else:
            is_update = False

        desired = (
            headline_prefix + plain_without_prefix
            if is_update
            else plain_without_prefix
        )
        if desired != plain:
            changes.append(
                {
                    "field": f"article_html.h3[{index}]",
                    "model_value": plain,
                    "normalized_value": desired,
                }
            )
        index += 1
        return f"<h3>{html.escape(desired, quote=False)}</h3>"

    result = re.sub(
        r"<h3>(.*?)</h3>",
        replace,
        article_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return result, changes


def _mark_first_visible_meta(article_html: str) -> tuple[str, bool, list[dict[str, Any]]]:
    parts = re.split(r"(<[^>]+>)", article_html)
    seen = False
    changed = False
    mentions = 0

    def replace_text(text: str) -> str:
        nonlocal seen, changed, mentions

        def repl(match: re.Match[str]) -> str:
            nonlocal seen, changed, mentions
            mentions += 1
            original = match.group(0)
            desired = "Meta*" if not seen else "Meta"
            seen = True
            if original != desired:
                changed = True
            return desired

        return re.sub(r"(?<!\w)Meta\*?(?!\w)", repl, text)

    for position, part in enumerate(parts):
        if part.startswith("<") and part.endswith(">"):
            continue
        parts[position] = replace_text(part)

    changes: list[dict[str, Any]] = []
    if changed:
        changes.append(
            {
                "field": "article_html.meta_marking",
                "model_value": "inconsistent",
                "normalized_value": "first Meta*, subsequent Meta",
            }
        )
    return "".join(parts), mentions > 0, changes


def order_candidates_by_article_links(
    article_html: str,
    selected_candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve candidate order from the source links inside each h3 story block."""

    parser = parse_article(article_html)
    errors: list[str] = []
    remaining = {str(item.get("id", "")): item for item in selected_candidates}
    candidate_urls: dict[str, set[str]] = {}

    for candidate_id, candidate in remaining.items():
        urls: set[str] = set()
        primary = candidate.get("primary_source")
        if isinstance(primary, dict):
            url = str(primary.get("url", "")).strip()
            if url:
                urls.add(url)
        supporting = candidate.get("supporting_sources")
        if isinstance(supporting, list):
            for source in supporting:
                if not isinstance(source, dict):
                    continue
                url = str(source.get("url", "")).strip()
                if url:
                    urls.add(url)
        candidate_urls[candidate_id] = urls

    ordered: list[dict[str, Any]] = []
    for position, links in enumerate(parser.story_links, start=1):
        link_set = set(links)
        matches = [
            candidate_id
            for candidate_id, urls in candidate_urls.items()
            if candidate_id in remaining and urls & link_set
        ]
        if len(matches) == 1:
            candidate_id = matches[0]
            ordered.append(remaining.pop(candidate_id))
            continue
        if not matches:
            errors.append(
                f"Сюжет h3[{position}] не удалось сопоставить с кандидатом по ссылкам."
            )
        else:
            errors.append(
                f"Сюжет h3[{position}] совпал с несколькими кандидатами: "
                + ", ".join(sorted(matches))
                + "."
            )

    if len(parser.story_links) != len(selected_candidates):
        errors.append(
            f"Число сюжетных блоков со ссылками ({len(parser.story_links)}) "
            f"не равно числу выбранных кандидатов ({len(selected_candidates)})."
        )

    if remaining:
        errors.append(
            "Не удалось сопоставить с article_html кандидатов: "
            + ", ".join(sorted(remaining))
            + "."
        )

    return ordered, errors


def normalize_article_html(
    article_html: str,
    selected_candidates: list[dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[str, bool, list[dict[str, Any]]]:
    """Apply deterministic editorial rules to model-generated article HTML."""

    if not isinstance(article_html, str):
        article_html = str(article_html or "")

    article_html = article_html.strip()
    changes: list[dict[str, Any]] = []

    story_counts = policy["story_counts"]
    short_notice = str(story_counts["short_digest_notice"])
    total_target_minimum = int(story_counts["total_target_minimum"])
    short_digest = 0 < len(selected_candidates) < total_target_minimum

    cleaned = _remove_exact_paragraph(article_html, short_notice)
    cleaned = _remove_meta_footnotes(cleaned)
    cleaned = _remove_dzen_block(cleaned, str(policy["dzen"]["heading"]))
    cleaned = cleaned.strip()

    cleaned, heading_changes = _normalise_update_headings(
        cleaned,
        selected_candidates,
        str(policy["updates"]["headline_prefix"]),
    )
    changes.extend(heading_changes)

    cleaned, has_meta, meta_changes = _mark_first_visible_meta(cleaned)
    changes.extend(meta_changes)

    if short_digest:
        canonical_notice = f"<p>{html.escape(short_notice, quote=False)}</p>"
        cleaned = canonical_notice + "\n" + cleaned
        changes.append(
            {
                "field": "article_html.short_digest_notice",
                "model_value": None,
                "normalized_value": canonical_notice,
            }
        )

    dzen_html = str(policy["dzen"]["html"])
    cleaned = cleaned.rstrip() + "\n" + dzen_html

    if has_meta:
        cleaned += "\n" + str(policy["meta_marking"]["footnote_html"])

    return cleaned.strip(), short_digest, changes


def build_editorial_notes(
    research: dict[str, Any],
    selected_candidates: list[dict[str, Any]],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    counts = policy["story_counts"]

    if 0 < len(selected_candidates) < int(counts["total_target_minimum"]):
        notes.append(
            {
                "type": "low_news_volume",
                "area": "total",
                "message": (
                    "После проверки свежести и значимости выбрано "
                    f"{len(selected_candidates)} сюжетов."
                ),
            }
        )

    russian_count = sum(
        1 for item in selected_candidates if item.get("geography") == "russia"
    )
    russian_target = int(counts["russian_target_minimum"])
    if russian_count < russian_target:
        notes.append(
            {
                "type": "regional_gap",
                "area": "russian_ai",
                "message": (
                    f"Выбрано {russian_count} российских сюжетов при редакционной "
                    f"цели {russian_target}; слабые материалы не добавлялись."
                ),
            }
        )

    date_only = [
        str(item.get("id", "unknown"))
        for item in selected_candidates
        if item.get("time_precision") == "date"
    ]
    if date_only:
        notes.append(
            {
                "type": "time_precision",
                "area": "sources",
                "message": (
                    "У части источников доступна только дата без точного времени: "
                    + ", ".join(date_only)
                    + "."
                ),
            }
        )

    coverage = research.get("coverage")
    if isinstance(coverage, list):
        gaps = [
            str(item.get("area", "")).strip()
            for item in coverage
            if isinstance(item, dict) and item.get("status") == "gap"
        ]
        gaps = [item for item in gaps if item]
        if gaps:
            notes.append(
                {
                    "type": "source_gap",
                    "area": "research",
                    "message": "Пробелы покрытия research: " + ", ".join(gaps) + ".",
                }
            )

    return notes


def build_stories(
    selected_candidates: list[dict[str, Any]],
    article_html: str,
) -> list[dict[str, Any]]:
    parser = parse_article(article_html)
    stories: list[dict[str, Any]] = []

    for index, candidate in enumerate(selected_candidates):
        headline = (
            parser.h3_texts[index]
            if index < len(parser.h3_texts)
            else str(candidate.get("title", "")).strip()
        )
        headline = headline.replace("Meta*", "Meta")
        candidate_sources: list[dict[str, Any]] = []
        primary = candidate.get("primary_source")
        if isinstance(primary, dict):
            candidate_sources.append(primary)
        supporting = candidate.get("supporting_sources")
        if isinstance(supporting, list):
            candidate_sources.extend(
                item for item in supporting if isinstance(item, dict)
            )

        linked_urls = set(
            parser.story_links[index] if index < len(parser.story_links) else []
        )
        sources: list[dict[str, Any]] = []
        seen_source_urls: set[str] = set()
        for source in candidate_sources:
            source_url = str(source.get("url", "")).strip()
            if not source_url or source_url not in linked_urls:
                continue
            if source_url in seen_source_urls:
                continue
            seen_source_urls.add(source_url)
            sources.append(source)

        keywords = candidate.get("keywords")
        if not isinstance(keywords, list) or not keywords:
            keywords = [
                str(candidate.get("organization", "")).strip(),
                str(candidate.get("category", "")).strip(),
            ]
            keywords = [item for item in keywords if item]

        stories.append(
            {
                "candidate_id": str(candidate.get("id", "")),
                "section": (
                    "russia" if candidate.get("geography") == "russia" else "world"
                ),
                "headline": headline,
                "organization": str(candidate.get("organization", "")).strip(),
                "topic": str(
                    candidate.get("topic") or candidate.get("category") or "other"
                ).strip(),
                "event_type": str(
                    candidate.get("event_type") or candidate.get("category") or "other"
                ).strip(),
                "status": (
                    "update"
                    if candidate.get("archive_status") == "update"
                    else "new"
                ),
                "summary": str(candidate.get("event_summary", "")).strip(),
                "published_at": candidate.get("published_at"),
                "published_date": str(candidate.get("published_date", "")),
                "time_precision": str(
                    candidate.get("time_precision") or "date"
                ),
                "sources": sources,
                "keywords": keywords,
                "geography": str(candidate.get("geography", "world")),
                "category": str(candidate.get("category", "other")),
            }
        )

    return stories


def _canonical_dzen_block(policy: dict[str, Any]) -> str:
    return str(policy["dzen"]["html"])


def validate_article_policy(
    article_html: str,
    selected_candidates: list[dict[str, Any]],
    short_digest: bool,
    policy: dict[str, Any],
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    parser = parse_article(article_html)

    counts = policy["story_counts"]
    short_notice = str(counts["short_digest_notice"])

    if short_digest:
        if parser.first_top_level_tag != "p" or parser.first_top_level_text != short_notice:
            errors.append(
                "Короткий выпуск должен начинаться с точной фразы о слабом новостном дне."
            )
    elif parser.first_top_level_text == short_notice:
        errors.append("Обычный выпуск не должен содержать фразу короткого выпуска.")

    world_heading = str(policy["article"]["world_heading"])
    russian_heading = str(policy["article"]["russian_heading"])
    what_heading = "Что это значит"
    if parser.h2_texts.count(world_heading) != 1:
        errors.append(f"Заголовок «{world_heading}» должен встречаться ровно один раз.")
    if parser.h2_texts.count(what_heading) != 1:
        errors.append(f"Заголовок «{what_heading}» должен встречаться ровно один раз.")

    selected_russian = sum(
        1 for item in selected_candidates if item.get("geography") == "russia"
    )
    russian_heading_count = parser.h2_texts.count(russian_heading)
    if selected_russian > 0 and russian_heading_count != 1:
        errors.append(
            f"При выбранных российских сюжетах заголовок «{russian_heading}» "
            "должен встречаться ровно один раз."
        )
    if selected_russian == 0 and russian_heading_count:
        errors.append(
            f"Пустой раздел «{russian_heading}» не должен присутствовать без "
            "российских сюжетов."
        )

    intro_html = re.split(r"<h2\b", article_html, maxsplit=1, flags=re.IGNORECASE)[0]
    if short_digest:
        intro_html = _remove_exact_paragraph(intro_html, short_notice)
    intro_text = parse_article(intro_html).visible_text
    intro_sentence_count = len(
        re.findall(r"[.!?…]+(?=\s|$)", intro_text)
    )
    minimum_intro = int(policy["article"]["introduction_sentences_minimum"])
    maximum_intro = int(policy["article"]["introduction_sentences_maximum"])
    if not minimum_intro <= intro_sentence_count <= maximum_intro:
        errors.append(
            f"Вступление содержит {intro_sentence_count} предложений; требуется "
            f"{minimum_intro}–{maximum_intro}."
        )

    if len(parser.h3_texts) != len(selected_candidates):
        errors.append(
            f"Число h3 ({len(parser.h3_texts)}) не равно числу выбранных сюжетов "
            f"({len(selected_candidates)})."
        )

    minimum_paragraphs = int(policy["article"]["paragraphs_per_story_minimum"])
    maximum_paragraphs = int(policy["article"]["paragraphs_per_story_maximum"])
    for index, count in enumerate(parser.story_paragraph_counts, start=1):
        if not minimum_paragraphs <= count <= maximum_paragraphs:
            errors.append(
                f"Сюжет {index} содержит {count} абзацев; требуется "
                f"{minimum_paragraphs}–{maximum_paragraphs}."
            )

    what_policy = policy["what_it_means"]
    if not int(what_policy["minimum_items"]) <= parser.what_it_means_items <= int(
        what_policy["maximum_items"]
    ):
        errors.append(
            "Раздел «Что это значит» должен содержать от "
            f"{what_policy['minimum_items']} до {what_policy['maximum_items']} "
            "пунктов списка."
        )

    dzen_block = _canonical_dzen_block(policy)
    if article_html.count(dzen_block) != 1:
        errors.append("В статье должен быть ровно один точный блок Дзена.")
    if parser.h2_texts.count(str(policy["dzen"]["heading"])) != 1:
        errors.append("Заголовок «Все ИИ-Сводки» должен встречаться ровно один раз.")

    expected_ending = dzen_block
    footnote = str(policy["meta_marking"]["footnote_html"])
    if footnote in article_html:
        expected_ending += "\n" + footnote
    if not article_html.rstrip().endswith(expected_ending):
        errors.append("Блок Дзена и возможная сноска Meta должны завершать article_html.")

    body_without_footnote = article_html.replace(footnote, "")
    body_parser = parse_article(body_without_footnote)
    meta_mentions = re.findall(r"(?<!\w)Meta\*?(?!\w)", body_parser.visible_text)

    if meta_mentions:
        if meta_mentions[0] != "Meta*":
            errors.append("Первое видимое упоминание Meta должно быть Meta*.")
        if any(item != "Meta" for item in meta_mentions[1:]):
            errors.append("После первого упоминания Meta звёздочка повторяться не должна.")
        if article_html.count(footnote) != 1:
            errors.append("При упоминании Meta требуется ровно одна точная сноска.")
        elif article_html.rfind(footnote) < article_html.rfind(dzen_block):
            errors.append("Сноска Meta должна находиться после блока Дзена.")
    elif footnote in article_html:
        errors.append("Сноска Meta присутствует без упоминания Meta в статье.")

    prefix = str(policy["updates"]["headline_prefix"])
    for index, candidate in enumerate(selected_candidates):
        if index >= len(parser.h3_texts):
            break
        headline = parser.h3_texts[index]
        is_update = candidate.get("archive_status") == "update"
        if is_update and not headline.startswith(prefix):
            errors.append(
                f"Сюжет {candidate.get('id')} со статусом update должен начинаться "
                f"с {prefix!r}."
            )
        if not is_update and headline.startswith(prefix):
            errors.append(
                f"Новый сюжет {candidate.get('id')} не должен иметь префикс {prefix!r}."
            )

    visible_text = body_parser.visible_text
    prohibited_agent_forms = [r"\bAI\s+agent\b", r"\bAI[- ]агент\w*\b"]
    if any(re.search(pattern, visible_text, flags=re.IGNORECASE) for pattern in prohibited_agent_forms):
        errors.append("Используй «агент ИИ», а не AI agent или AI-агент.")

    # Standalone AI is a warning because it can be part of an official product name.
    cleaned_for_ai = visible_text
    for official in (
        list(policy.get("tracked_world_organizations", []))
        + list(policy.get("tracked_asia_organizations", []))
        + list(policy.get("tracked_russian_organizations", []))
    ):
        cleaned_for_ai = cleaned_for_ai.replace(str(official), "")
    if re.search(r"\bAI\b", cleaned_for_ai):
        warnings.append(
            "Обнаружено отдельное написание AI; проверь, не следует ли заменить его на ИИ."
        )

    analysis = {
        "h2_texts": parser.h2_texts,
        "h3_texts": parser.h3_texts,
        "story_paragraph_counts": parser.story_paragraph_counts,
        "story_links": parser.story_links,
        "what_it_means_items": parser.what_it_means_items,
        "first_top_level_tag": parser.first_top_level_tag,
        "first_top_level_text": parser.first_top_level_text,
        "intro_sentence_count": intro_sentence_count,
        "meta_mentions": meta_mentions,
    }
    return errors, warnings, analysis


def validate_stories(
    stories: list[dict[str, Any]],
    selected_candidates: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if len(stories) != len(selected_candidates):
        errors.append(
            f"stories.json содержит {len(stories)} записей, ожидалось "
            f"{len(selected_candidates)}."
        )
        return errors

    required = {
        "candidate_id",
        "section",
        "headline",
        "organization",
        "topic",
        "event_type",
        "status",
        "summary",
        "published_at",
        "published_date",
        "time_precision",
        "sources",
        "keywords",
        "geography",
        "category",
    }
    seen_ids: set[str] = set()
    for position, story in enumerate(stories, start=1):
        missing = sorted(required.difference(story))
        if missing:
            errors.append(
                f"stories[{position}] не содержит поля: {', '.join(missing)}."
            )
            continue
        candidate_id = str(story["candidate_id"])
        if candidate_id in seen_ids:
            errors.append(f"Повторный candidate_id в stories.json: {candidate_id}.")
        seen_ids.add(candidate_id)
        if "Meta*" in json.dumps(story, ensure_ascii=False):
            errors.append("В stories.json запрещено служебное написание Meta*.")
        if story["status"] not in {"new", "update"}:
            errors.append(f"Некорректный status у {candidate_id}.")
        if story["time_precision"] not in {"date", "datetime"}:
            errors.append(f"Некорректный time_precision у {candidate_id}.")
        sources = story.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"У {candidate_id} отсутствуют процитированные источники.")
        else:
            seen_urls: set[str] = set()
            for source in sources:
                if not isinstance(source, dict):
                    errors.append(f"У {candidate_id} источник должен быть объектом.")
                    continue
                for key in ("title", "publisher", "url"):
                    if not isinstance(source.get(key), str) or not source[key].strip():
                        errors.append(
                            f"У {candidate_id} источник не содержит поле {key}."
                        )
                source_url = str(source.get("url", "")).strip()
                if source_url in seen_urls:
                    errors.append(f"У {candidate_id} повторяется источник {source_url}.")
                seen_urls.add(source_url)

    expected_ids = [str(item.get("id", "")) for item in selected_candidates]
    actual_ids = [str(item.get("candidate_id", "")) for item in stories]
    if actual_ids != expected_ids:
        errors.append("Порядок stories.json не совпадает с selected_candidate_ids.")
    return errors


def validate_diversity_overrides(
    selected_candidates: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
    policy: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    publisher_counter: Counter[str] = Counter()
    organization_counter: Counter[str] = Counter()

    for candidate in selected_candidates:
        primary = candidate.get("primary_source")
        if isinstance(primary, dict):
            publisher = str(primary.get("publisher", "")).strip().casefold()
            if publisher:
                publisher_counter[publisher] += 1
        organization = str(candidate.get("organization", "")).strip().casefold()
        if organization:
            organization_counter[organization] += 1

    override_keys = {
        (
            str(item.get("type", "")).strip(),
            str(item.get("value", "")).strip().casefold(),
        )
        for item in overrides
        if isinstance(item, dict) and str(item.get("reason", "")).strip()
    }

    max_publisher = int(policy["diversity"]["max_selected_per_publisher_soft"])
    max_organization = int(
        policy["diversity"]["max_selected_per_organization_soft"]
    )

    for value, count in publisher_counter.items():
        if count > max_publisher and ("publisher", value) not in override_keys:
            errors.append(
                f"Издатель {value!r} представлен {count} сюжетами без "
                "diversity override с причиной."
            )

    for value, count in organization_counter.items():
        if count > max_organization and ("organization", value) not in override_keys:
            errors.append(
                f"Организация {value!r} представлена {count} сюжетами без "
                "diversity override с причиной."
            )

    return errors
