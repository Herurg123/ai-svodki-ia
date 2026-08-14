#!/usr/bin/env python3
"""Normalize deterministic digest fields before contract validation.

This utility performs no network requests. It is intentionally safe to run for
both freshly generated and recovered editorial artifacts. It repairs legacy
image prompts, corrects the legacy saved-research label for trusted fresh
Primary Recall artifacts, and rejects obviously degraded Primary Recall source
health before a weak digest can be published.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONSTRAINTS = (
    "без логотипов",
    "без дополнительного текста",
    "без водяных знаков",
    "без узнаваемых лиц",
)
JSON_FILES = (
    "digest.json",
    "editorial-output.json",
    "editorial-output-raw.json",
)
TEXT_FILES = ("image-prompt.txt", "image_prompt.txt")
LOW_SIGNAL_DISCOVERY_DOMAINS = (
    "wikipedia.org",
    "reddit.com",
    "arxiv.org",
)
AGENCY_DISCOVERY_DOMAINS = (
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "ft.com",
)
URL_DATE_PATTERN = re.compile(r"(20\d{2})-(\d{2})-(\d{2})(?:/|$)")
FRESH_PRIMARY_PIPELINE = "primary_recall_v2_then_editorial"


class NormalizationError(RuntimeError):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NormalizationError(f"Не найден обязательный файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise NormalizationError(f"Некорректный JSON {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_prompt(prompt: str) -> tuple[str, list[str]]:
    value = prompt.strip()
    if not value:
        raise NormalizationError("image_prompt пуст")

    lower = value.lower()
    missing = [constraint for constraint in CONSTRAINTS if constraint not in lower]
    if not missing:
        return value, []

    suffix = "Ограничения: " + "; ".join(missing) + "."
    separator = "\n" if value.endswith((".", ";", ":")) else ".\n"
    normalized = value + separator + suffix
    return normalized, missing


def normalize_json_prompts(payload: Any, *, path: str = "$") -> tuple[Any, list[dict[str, Any]]]:
    changes: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in list(payload.items()):
            child_path = f"{path}.{key}"
            if key == "image_prompt" and isinstance(value, str):
                normalized, missing = normalize_prompt(value)
                if missing:
                    payload[key] = normalized
                    changes.append(
                        {
                            "field": child_path,
                            "added_constraints": missing,
                        }
                    )
            else:
                _, nested_changes = normalize_json_prompts(value, path=child_path)
                changes.extend(nested_changes)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _, nested_changes = normalize_json_prompts(value, path=f"{path}[{index}]")
            changes.extend(nested_changes)
    return payload, changes


def _hostname(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _host_matches(host: str, domains: tuple[str, ...]) -> bool:
    host = host.casefold().strip(".")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _is_low_signal_host(host: str) -> bool:
    return _host_matches(host, LOW_SIGNAL_DISCOVERY_DOMAINS)


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _primary_window_dates(primary: dict[str, Any]) -> tuple[date, date] | None:
    window = primary.get("search_window")
    if not isinstance(window, dict):
        return None
    try:
        start = datetime.fromisoformat(str(window.get("start_at") or "").replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(window.get("end_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None or end.tzinfo is None or end < start:
        return None
    return start.date(), end.date()


def _url_embedded_date(url: str) -> date | None:
    try:
        path = urlparse(url).path
    except ValueError:
        return None
    match = URL_DATE_PATTERN.search(path)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _candidate_has_fresh_agency_evidence(
    candidate: Any, *, start_day: date, end_day: date
) -> bool:
    if not isinstance(candidate, dict):
        return False
    published_day = _parse_date(candidate.get("published_date"))
    if published_day is None or not (start_day <= published_day <= end_day):
        return False
    source = candidate.get("primary_source")
    if not isinstance(source, dict) or not isinstance(source.get("url"), str):
        return False
    return _host_matches(_hostname(source["url"]), AGENCY_DISCOVERY_DOMAINS)


def _artifact_has_fresh_agency_evidence(
    artifact_dir: Path, *, start_day: date, end_day: date
) -> bool:
    candidates_path = artifact_dir / "candidates.json"
    if not candidates_path.is_file():
        return False
    payload = read_json(candidates_path)
    candidates = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(candidates, list):
        return False
    return any(
        _candidate_has_fresh_agency_evidence(
            candidate, start_day=start_day, end_day=end_day
        )
        for candidate in candidates
    )


def _direction_has_fresh_agency_evidence(
    direction: dict[str, Any], *, start_day: date, end_day: date
) -> bool:
    for candidate in direction.get("raw_candidates") or []:
        if _candidate_has_fresh_agency_evidence(
            candidate, start_day=start_day, end_day=end_day
        ):
            return True

    api = direction.get("api")
    if not isinstance(api, dict):
        return False
    for source in api.get("consulted_sources") or []:
        if not isinstance(source, dict) or not isinstance(source.get("url"), str):
            continue
        url = source["url"]
        if not _host_matches(_hostname(url), AGENCY_DISCOVERY_DOMAINS):
            continue
        embedded_day = _url_embedded_date(url)
        if embedded_day is not None and start_day <= embedded_day <= end_day:
            return True
    return False


def normalize_fresh_primary_metadata(artifact_dir: Path, report: dict[str, Any]) -> None:
    """Correct the legacy generator label only when Primary Recall proved freshness."""
    run_info_path = artifact_dir / "run-info.json"
    if not run_info_path.is_file():
        return
    run_info = read_json(run_info_path)
    if not isinstance(run_info, dict):
        raise NormalizationError("run-info.json должен содержать объект")
    research = run_info.get("research")
    if not isinstance(research, dict) or research.get("mode") != "primary_recall_v2":
        return
    response = research.get("response")
    if not isinstance(response, dict):
        raise NormalizationError("Primary Recall run-info не содержит research.response")
    try:
        search_calls = int(response.get("web_search_calls", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise NormalizationError("Primary Recall web_search_calls должен быть целым числом") from exc
    if search_calls != 12:
        raise NormalizationError(
            f"Primary Recall fresh artifact должен содержать 12 search operations, получено: {search_calls}"
        )

    changes: list[dict[str, Any]] = []
    if run_info.get("pipeline") != FRESH_PRIMARY_PIPELINE:
        changes.append(
            {
                "field": "$.pipeline",
                "from": run_info.get("pipeline"),
                "to": FRESH_PRIMARY_PIPELINE,
            }
        )
        run_info["pipeline"] = FRESH_PRIMARY_PIPELINE
    settings = research.get("settings")
    if isinstance(settings, dict) and settings.get("source") == "saved_fixture":
        settings["source"] = "trusted_runtime_primary_recall"
        changes.append(
            {
                "field": "$.research.settings.source",
                "from": "saved_fixture",
                "to": "trusted_runtime_primary_recall",
            }
        )
    if changes:
        write_json(run_info_path, run_info)
        if "run-info.json" not in report["changed_files"]:
            report["changed_files"].append("run-info.json")
        report["changes"].extend({"file": "run-info.json", **item} for item in changes)


def validate_primary_source_health(artifact_dir: Path) -> None:
    """Fail closed when a completed fresh primary searched mostly junk/empty sources."""
    primary_path = artifact_dir / "primary-recall.json"
    if not primary_path.is_file():
        return
    primary = read_json(primary_path)
    if not isinstance(primary, dict):
        raise NormalizationError("primary-recall.json должен содержать объект")
    directions = primary.get("directions")
    if not isinstance(directions, list):
        raise NormalizationError("primary-recall.json не содержит directions[]")

    agency = next(
        (
            item
            for item in directions
            if isinstance(item, dict) and item.get("direction_id") == "major_agencies"
        ),
        None,
    )
    if not isinstance(agency, dict):
        raise NormalizationError("Primary Recall не содержит обязательный major_agencies pass")
    if int(agency.get("web_search_calls_completed", 0) or 0) != 1:
        raise NormalizationError("major_agencies не завершил обязательную search operation")
    agency_api = agency.get("api")
    agency_sources = (
        agency_api.get("consulted_sources")
        if isinstance(agency_api, dict)
        else None
    )
    if not isinstance(agency_sources, list) or not agency_sources:
        raise NormalizationError(
            "Primary Recall source-health degraded: major_agencies завершился без единого consulted source."
        )

    all_urls: list[str] = []
    for item in directions:
        if not isinstance(item, dict):
            continue
        api = item.get("api")
        if not isinstance(api, dict):
            continue
        for source in api.get("consulted_sources") or []:
            if isinstance(source, dict) and isinstance(source.get("url"), str):
                all_urls.append(source["url"])
    high_signal = [url for url in all_urls if not _is_low_signal_host(_hostname(url))]
    if len(high_signal) < 2:
        raise NormalizationError(
            "Primary Recall source-health degraded: после 12 searches найдено меньше двух "
            "источников вне Wikipedia/Reddit/arXiv."
        )

    # Merely consulting a Bloomberg author page or an old newsletter is not
    # sufficient evidence that current-news retrieval is healthy. With the
    # source-neutral routing introduced after the 2026-08-14 live experiment,
    # publisher placement is no longer an invariant: a fresh Reuters/AP/
    # Bloomberg/FT candidate may legitimately be discovered by security,
    # business, regional, developer or another thematic Primary direction.
    # Therefore modern diagnostics require fresh agency evidence anywhere in the
    # completed 12-pass Primary matrix, not specifically in former anchor slots.
    # Legacy Primary artifacts without search_window keep compatibility behavior.
    window_days = _primary_window_dates(primary)
    if window_days is not None:
        start_day, end_day = window_days
        primary_has_fresh_agency = any(
            _direction_has_fresh_agency_evidence(
                item, start_day=start_day, end_day=end_day
            )
            for item in directions
            if isinstance(item, dict)
        )
        final_pool_has_fresh_agency = _artifact_has_fresh_agency_evidence(
            artifact_dir, start_day=start_day, end_day=end_day
        )
        if not (primary_has_fresh_agency or final_pool_has_fresh_agency):
            raise NormalizationError(
                "Primary Recall source-health degraded: ни Primary diagnostics, ни "
                "финальный validated candidate pool после mandatory Coverage не "
                "подтвердили свежий Reuters/AP/Bloomberg/FT материал в effective "
                "window; служебные, author и старые newsletter URL не считаются "
                "доказательством свежего agency retrieval."
            )


def normalize_artifact(artifact_dir: Path, report_path: Path) -> dict[str, Any]:
    if not artifact_dir.is_dir():
        raise NormalizationError(f"Каталог artifact не найден: {artifact_dir}")

    report: dict[str, Any] = {
        "status": "ok",
        "artifact_dir": str(artifact_dir),
        "changed_files": [],
        "changes": [],
    }
    prompt_locations = 0

    for name in JSON_FILES:
        path = artifact_dir / name
        if not path.is_file():
            if name == "digest.json":
                raise NormalizationError(f"Не найден обязательный файл: {path}")
            continue
        payload = read_json(path)
        normalized, changes = normalize_json_prompts(payload)
        prompt_locations += sum(1 for change in changes) or _count_prompts(payload)
        if changes:
            write_json(path, normalized)
            report["changed_files"].append(name)
            report["changes"].extend(
                {"file": name, **change} for change in changes
            )

    for name in TEXT_FILES:
        path = artifact_dir / name
        if not path.is_file():
            continue
        prompt_locations += 1
        original = path.read_text(encoding="utf-8")
        normalized, missing = normalize_prompt(original)
        if missing:
            path.write_text(normalized + "\n", encoding="utf-8")
            report["changed_files"].append(name)
            report["changes"].append(
                {
                    "file": name,
                    "field": "text",
                    "added_constraints": missing,
                }
            )

    if prompt_locations == 0:
        raise NormalizationError("В artifact не найден image_prompt")

    normalize_fresh_primary_metadata(artifact_dir, report)
    validate_primary_source_health(artifact_dir)

    # The old validation report hashes pre-normalized files and must never be
    # reused as an image source manifest. The validator immediately recreates it.
    stale_validation = artifact_dir / "artifact-validation.json"
    if stale_validation.resolve() != report_path.resolve() and stale_validation.exists():
        stale_validation.unlink()
        report["removed_stale_validation"] = True
    else:
        report["removed_stale_validation"] = False

    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report)
    return report


def _count_prompts(payload: Any) -> int:
    if isinstance(payload, dict):
        return sum(
            (1 if key == "image_prompt" and isinstance(value, str) else _count_prompts(value))
            for key, value in payload.items()
        )
    if isinstance(payload, list):
        return sum(_count_prompts(value) for value in payload)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = normalize_artifact(args.artifact_dir, args.report)
    except NormalizationError as exc:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            args.report,
            {
                "status": "error",
                "artifact_dir": str(args.artifact_dir),
                "error": str(exc),
            },
        )
        print(f"Digest normalization failed: {exc}")
        return 1
    print(
        "Digest normalization: ok; changed files: "
        + (", ".join(report["changed_files"]) or "none")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
