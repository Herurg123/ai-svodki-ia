from __future__ import annotations

import copy
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_KEYS = {"fbclid", "gclid", "yclid", "mc_cid", "mc_eid"}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def normalize_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"Некорректный URL: {value!r}")
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"Некорректный URL: {value!r}") from exc
    if port and not (
        (parts.scheme.lower() == "http" and port == 80)
        or (parts.scheme.lower() == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    clean_query: list[tuple[str, str]] = []
    for key, query_value in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in TRACKING_QUERY_KEYS:
            continue
        clean_query.append((key, query_value))
    clean_query.sort()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            netloc,
            path,
            urlencode(clean_query, doseq=True),
            "",
        )
    )


def geography_of_story(story: dict[str, Any]) -> str:
    geography = str(story.get("geography", "")).strip().lower()
    if geography in {"world", "russia"}:
        return geography
    section = str(story.get("section", "")).strip().lower()
    if section in {"world", "russia"}:
        return section
    return "unknown"


def coverage_summary(
    stories: list[Any],
    *,
    minimum_total: int = 7,
    minimum_world: int = 5,
    minimum_russia: int = 2,
) -> dict[str, Any]:
    world = 0
    russia = 0
    unknown = 0
    for raw_story in stories:
        if not isinstance(raw_story, dict):
            unknown += 1
            continue
        geography = geography_of_story(raw_story)
        if geography == "world":
            world += 1
        elif geography == "russia":
            russia += 1
        else:
            unknown += 1
    total = world + russia + unknown
    missing = {
        "total": max(0, minimum_total - total),
        "world": max(0, minimum_world - world),
        "russia": max(0, minimum_russia - russia),
    }
    return {
        "status": "ok" if not any(missing.values()) else "incomplete",
        "counts": {
            "total": total,
            "world": world,
            "russia": russia,
            "unknown": unknown,
        },
        "required": {
            "total": minimum_total,
            "world": minimum_world,
            "russia": minimum_russia,
        },
        "missing": missing,
        "valid": not any(missing.values()),
    }


def eligible_candidate_summary(candidates: list[Any]) -> dict[str, int]:
    result = {"total": 0, "world": 0, "russia": 0}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("recommendation") == "exclude":
            continue
        geography = candidate.get("geography")
        if geography not in {"world", "russia"}:
            continue
        result["total"] += 1
        result[str(geography)] += 1
    return result


def candidate_primary_url(candidate: dict[str, Any]) -> str | None:
    source = candidate.get("primary_source")
    if not isinstance(source, dict):
        return None
    value = source.get("url")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return normalize_url(value)
    except ValueError:
        return None


def candidate_fingerprint(candidate: dict[str, Any]) -> str:
    url = candidate_primary_url(candidate)
    if url:
        return f"url:{url}"
    pieces = [
        str(candidate.get("organization", "")).casefold(),
        str(candidate.get("topic", "")).casefold(),
        str(candidate.get("published_date", "")),
    ]
    normalized = "|".join(re.sub(r"\s+", " ", part).strip() for part in pieces)
    return f"semantic:{normalized}"


def _parse_aware_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def candidate_in_window(candidate: dict[str, Any], search_window: dict[str, Any]) -> bool:
    try:
        start_date = date.fromisoformat(str(search_window["start_date"]))
        end_date = date.fromisoformat(str(search_window["end_date"]))
        published_date = date.fromisoformat(str(candidate.get("published_date", "")))
    except (KeyError, ValueError):
        return False
    if not start_date <= published_date <= end_date:
        return False
    if candidate.get("time_precision") == "datetime":
        published_at = candidate.get("published_at")
        if not isinstance(published_at, str):
            return False
        parsed = _parse_aware_datetime(published_at)
        start_at = _parse_aware_datetime(str(search_window.get("start_at", "")))
        end_at = _parse_aware_datetime(str(search_window.get("end_at", "")))
        if parsed is None or start_at is None or end_at is None:
            return False
        return start_at <= parsed <= end_at
    return candidate.get("time_precision") == "date" and candidate.get("published_at") is None


def validate_audit_candidate(
    candidate: dict[str, Any], search_window: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    required_strings = (
        "title",
        "organization",
        "published_date",
        "topic",
        "event_type",
        "geography",
        "category",
        "source_type",
        "event_summary",
        "significance",
        "archive_status",
        "archive_reason",
        "recommendation",
    )
    for field in required_strings:
        if not isinstance(candidate.get(field), str):
            errors.append(f"{field} должен быть строкой")
    if candidate.get("geography") not in {"world", "russia"}:
        errors.append("geography должен быть world или russia")
    if candidate.get("time_precision") not in {"date", "datetime"}:
        errors.append("time_precision должен быть date или datetime")
    if candidate.get("recommendation") not in {"include", "consider", "exclude"}:
        errors.append("некорректный recommendation")
    if candidate.get("archive_status") not in {"none", "update"}:
        errors.append("некорректный archive_status")
    if not isinstance(candidate.get("keywords"), list) or not candidate["keywords"]:
        errors.append("keywords должен быть непустым массивом")
    if not isinstance(candidate.get("verified_facts"), list) or len(candidate["verified_facts"]) < 2:
        errors.append("verified_facts должен содержать минимум два факта")
    if not isinstance(candidate.get("supporting_sources"), list):
        errors.append("supporting_sources должен быть массивом")
    primary = candidate.get("primary_source")
    if not isinstance(primary, dict):
        errors.append("primary_source должен быть объектом")
    else:
        for field in ("title", "publisher", "url"):
            if not isinstance(primary.get(field), str) or not primary[field].strip():
                errors.append(f"primary_source.{field} должен быть непустым")
        try:
            normalize_url(str(primary.get("url", "")))
        except ValueError as exc:
            errors.append(str(exc))
    score = candidate.get("significance_score")
    if not isinstance(score, int) or not 1 <= score <= 5:
        errors.append("significance_score должен быть целым 1..5")
    if not candidate_in_window(candidate, search_window):
        errors.append("кандидат находится вне редакционного окна")
    return errors


def merge_candidates(
    base_research: dict[str, Any],
    additional_candidates: list[Any],
    *,
    maximum_candidates: int = 20,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    merged = copy.deepcopy(base_research)
    base_candidates = merged.get("candidates")
    if not isinstance(base_candidates, list):
        raise RuntimeError("candidates.json: candidates должен быть массивом")
    search_window = merged.get("search_window")
    if not isinstance(search_window, dict):
        raise RuntimeError("candidates.json: search_window должен быть объектом")

    result: list[dict[str, Any]] = [
        copy.deepcopy(item) for item in base_candidates if isinstance(item, dict)
    ]
    seen = {candidate_fingerprint(item) for item in result}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    ranked = sorted(
        (item for item in additional_candidates if isinstance(item, dict)),
        key=lambda item: (
            0 if item.get("recommendation") == "include" else 1,
            -int(item.get("significance_score", 0) or 0),
        ),
    )
    for raw_candidate in ranked:
        candidate = copy.deepcopy(raw_candidate)
        candidate.pop("id", None)
        errors = validate_audit_candidate(candidate, search_window)
        fingerprint = candidate_fingerprint(candidate)
        if fingerprint in seen:
            errors.append("дубликат существующего кандидата")
        if errors:
            rejected.append(
                {
                    "title": candidate.get("title"),
                    "primary_url": candidate_primary_url(candidate),
                    "errors": errors,
                }
            )
            continue
        if len(result) >= maximum_candidates:
            rejected.append(
                {
                    "title": candidate.get("title"),
                    "primary_url": candidate_primary_url(candidate),
                    "errors": ["достигнут maximum_candidates"],
                }
            )
            continue
        seen.add(fingerprint)
        result.append(candidate)
        accepted.append(candidate)

    for index, candidate in enumerate(result, start=1):
        candidate["id"] = f"cand-{index:03d}"
    merged["candidates"] = result
    merged["research_notes"] = (
        str(merged.get("research_notes", "")).rstrip()
        + f"\nTargeted coverage audit добавил кандидатов: {len(accepted)}."
    ).strip()
    return merged, accepted, rejected


def compact_archive(archive: dict[str, Any], *, limit: int = 200) -> list[dict[str, Any]]:
    items = archive.get("items")
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        stories = raw.get("stories")
        compact_stories: list[dict[str, Any]] = []
        if isinstance(stories, list):
            for story in stories:
                if not isinstance(story, dict):
                    continue
                compact_stories.append(
                    {
                        "headline": story.get("headline") or story.get("title"),
                        "organization": story.get("organization"),
                        "topic": story.get("topic"),
                        "source_urls": story.get("source_urls") or [
                            source.get("url")
                            for source in story.get("sources", [])
                            if isinstance(source, dict) and source.get("url")
                        ],
                    }
                )
        normalized.append(
            {
                "date": raw.get("date"),
                "title": raw.get("title"),
                "stories": compact_stories,
                "source_urls": raw.get("source_urls", []),
            }
        )
    normalized.sort(key=lambda item: str(item.get("date", "")), reverse=True)
    return normalized[:limit]
