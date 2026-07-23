from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from editorial_policy import (  # noqa: E402
    build_editorial_notes,
    build_stories,
    normalize_article_html,
    order_candidates_by_article_links,
    read_policy,
    validate_article_policy,
    validate_diversity_overrides,
    validate_stories,
)

POLICY_PATH = ROOT / "automation" / "config" / "editorial.json"
GENERATOR_PATH = ROOT / "automation" / "scripts" / "generate_digest_preview.py"
MANIFEST_PATH = (
    ROOT / "automation" / "fixtures" / "editorial-scenarios" / "manifest.json"
)
DEFAULT_REPORT = ROOT / "automation" / "preview" / "editorial-scenario-matrix.json"


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    status: str
    checks: list[str]
    error: str | None = None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def candidate(
    number: int,
    *,
    geography: str = "world",
    archive_status: str = "none",
    time_precision: str = "datetime",
    publisher: str | None = None,
    organization: str | None = None,
    url: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    identifier = f"cand-{number:03d}"
    organization_value = organization or f"Организация {number}"
    publisher_value = publisher or f"Издатель {number}"
    source_url = url or f"https://example.com/news/{identifier}"
    published_at = (
        "2026-07-11T06:30:00+03:00" if time_precision == "datetime" else None
    )
    return {
        "id": identifier,
        "title": title or f"Сюжет {number}",
        "organization": organization_value,
        "published_date": "2026-07-11",
        "published_at": published_at,
        "time_precision": time_precision,
        "topic": "models",
        "event_type": "product_update",
        "keywords": [organization_value, "ИИ"],
        "geography": geography,
        "category": "models",
        "source_type": "official",
        "primary_source": {
            "title": f"Источник сюжета {number}",
            "publisher": publisher_value,
            "url": source_url,
        },
        "supporting_sources": [],
        "event_summary": f"Подтверждённое событие для сюжета {number}.",
        "verified_facts": ["Подтверждён факт один.", "Подтверждён факт два."],
        "significance": "Событие влияет на рынок ИИ.",
        "significance_score": 4,
        "limitations": "Независимые сравнительные данные пока ограничены.",
        "archive_status": archive_status,
        "archive_reason": "Есть существенный новый факт." if archive_status == "update" else "",
        "recommendation": "include",
    }


def article_html(
    selected: list[dict[str, Any]],
    *,
    paragraphs: int = 2,
    what_items: int = 4,
    headline_overrides: dict[str, str] | None = None,
    body_phrase: str = "Событие подтверждено источником и имеет практическое значение.",
) -> str:
    headline_overrides = headline_overrides or {}
    world = [item for item in selected if item.get("geography") != "russia"]
    russian = [item for item in selected if item.get("geography") == "russia"]
    blocks = [
        "<p>Первое предложение вводит контекст. Второе предложение объясняет значение выпуска.</p>",
        "<h2>Мировые лидеры ИИ</h2>",
    ]

    def append_story(item: dict[str, Any]) -> None:
        identifier = str(item["id"])
        headline = headline_overrides.get(identifier, str(item["title"]))
        blocks.append(f"<h3>{headline}</h3>")
        for index in range(paragraphs):
            if index == paragraphs - 1:
                url = item["primary_source"]["url"]
                blocks.append(
                    "<p>"
                    + body_phrase
                    + f' <a href="{url}">Источник</a></p>'
                )
            else:
                blocks.append(
                    f"<p>{body_phrase} Абзац {index + 1} раскрывает ограничения и последствия.</p>"
                )

    for item in world:
        append_story(item)
    if russian:
        blocks.append("<h2>Российские лидеры ИИ</h2>")
        for item in russian:
            append_story(item)
    blocks.append("<h2>Что это значит</h2>")
    blocks.append("<ol>")
    for index in range(what_items):
        blocks.append(f"<li>Практический вывод {index + 1}.</li>")
    blocks.append("</ol>")
    return "\n".join(blocks)


def normalise_and_validate(
    source_html: str,
    selected: list[dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[str, bool, list[str], list[str], dict[str, Any]]:
    normalized, short_digest, _changes = normalize_article_html(
        source_html, selected, policy
    )
    errors, warnings, analysis = validate_article_policy(
        normalized, selected, short_digest, policy
    )
    return normalized, short_digest, errors, warnings, analysis


def scenario_normal_digest(policy: dict[str, Any]) -> list[str]:
    selected = [candidate(index) for index in range(1, 7)]
    normalized, short_digest, errors, _warnings, analysis = normalise_and_validate(
        article_html(selected), selected, policy
    )
    require(not short_digest, "Шесть сюжетов не должны считаться коротким выпуском.")
    require(errors == [], f"Обычный выпуск не прошёл политику: {errors}")
    require(analysis["what_it_means_items"] == 4, "Ожидалось четыре вывода.")
    notice = policy["story_counts"]["short_digest_notice"]
    require(not normalized.startswith(f"<p>{notice}</p>"), "Лишняя short notice.")
    return ["6 сюжетов", "short_digest=false", "4 вывода", "политика без ошибок"]


def scenario_short_digest(policy: dict[str, Any]) -> list[str]:
    selected = [candidate(index) for index in range(1, 4)]
    normalized, short_digest, errors, _warnings, _analysis = normalise_and_validate(
        article_html(selected), selected, policy
    )
    notice = policy["story_counts"]["short_digest_notice"]
    require(short_digest, "Три сюжета должны формировать короткий выпуск.")
    require(normalized.startswith(f"<p>{notice}</p>"), "Нет точной short notice.")
    require(errors == [], f"Короткий выпуск не прошёл политику: {errors}")
    notes = build_editorial_notes({"coverage": []}, selected, policy)
    note_types = {str(item.get("type")) for item in notes}
    require("low_news_volume" in note_types, "Нет low_news_volume.")
    return ["3 сюжета", "short_digest=true", "точная вводная", "low_news_volume"]


def scenario_zero_stories_guard(policy: dict[str, Any]) -> list[str]:
    require(
        policy["story_counts"].get("zero_stories_status") == "error",
        "editorial.json должен задавать zero_stories_status=error.",
    )
    generator = GENERATOR_PATH.read_text(encoding="utf-8")
    require(
        re.search(r"if\s+len\(selected\)\s*==\s*0\s*:", generator) is not None,
        "В генераторе отсутствует явная проверка нулевого выбора.",
    )
    require(
        "Редактор не выбрал ни одного достойного сюжета" in generator,
        "В генераторе отсутствует диагностическое сообщение нулевого выбора.",
    )
    return ["zero_stories_status=error", "явный runtime guard", "диагностика ошибки"]


def scenario_meta_marking(policy: dict[str, Any]) -> list[str]:
    meta = candidate(1, organization="Meta", title="Meta представила новую функцию")
    other = candidate(2, title="Рынок оценил решение Meta")
    selected = [meta, other]
    source = article_html(
        selected,
        body_phrase="Meta описала изменение, а участники рынка оценили последствия.",
    )
    normalized, short_digest, errors, _warnings, _analysis = normalise_and_validate(
        source, selected, policy
    )
    require(short_digest, "Два сюжета должны считаться коротким выпуском.")
    require(errors == [], f"Meta-сценарий не прошёл политику: {errors}")
    footnote = policy["meta_marking"]["footnote_html"]
    dzen = policy["dzen"]["html"]
    require(normalized.count("Meta*") == 1, "В видимом HTML должна быть одна Meta*.")
    require(normalized.count(footnote) == 1, "Должна быть ровно одна сноска Meta.")
    require(normalized.rfind(footnote) > normalized.rfind(dzen), "Сноска должна идти после Дзена.")
    stories = build_stories(selected, normalized)
    require(validate_stories(stories, selected) == [], "stories.json не прошёл проверку.")
    require("Meta*" not in json.dumps(stories, ensure_ascii=False), "Meta* попала в служебные поля.")
    return ["одна Meta*", "одна сноска", "сноска после Дзена", "служебные поля без звёздочки"]


def scenario_update_prefix(policy: dict[str, Any]) -> list[str]:
    update = candidate(1, archive_status="update", title="Существенный новый факт")
    fresh = candidate(2, archive_status="none", title="Новая самостоятельная тема")
    selected = [update, fresh]
    source = article_html(
        selected,
        headline_overrides={
            update["id"]: "Существенный новый факт",
            fresh["id"]: "Обновление: Новая самостоятельная тема",
        },
    )
    normalized, _short, errors, _warnings, analysis = normalise_and_validate(
        source, selected, policy
    )
    require(errors == [], f"Префиксы обновлений не нормализованы: {errors}")
    require(analysis["h3_texts"][0].startswith("Обновление: "), "Update без префикса.")
    require(not analysis["h3_texts"][1].startswith("Обновление: "), "Новая тема с префиксом.")
    stories = build_stories(selected, normalized)
    require(stories[0]["status"] == "update", "Update не перенесён в stories.json.")
    require(stories[1]["status"] == "new", "Новая тема получила неверный status.")
    return ["update получает префикс", "new теряет префикс", "stories status согласован"]


def scenario_russian_section(policy: dict[str, Any]) -> list[str]:
    world_only = [candidate(1), candidate(2)]
    normalized, _short, errors, _warnings, _analysis = normalise_and_validate(
        article_html(world_only), world_only, policy
    )
    require(errors == [], f"Выпуск без российского раздела отклонён: {errors}")
    require("<h2>Российские лидеры ИИ</h2>" not in normalized, "Создан пустой российский раздел.")

    invalid = normalized.replace(
        "<h2>Что это значит</h2>",
        "<h2>Российские лидеры ИИ</h2>\n<h2>Что это значит</h2>",
    )
    invalid_errors, _warnings, _analysis = validate_article_policy(
        invalid, world_only, True, policy
    )
    require(invalid_errors, "Пустой российский раздел должен блокироваться.")

    mixed = [candidate(1), candidate(2, geography="russia", organization="Яндекс")]
    mixed_html, _short, mixed_errors, _warnings, _analysis = normalise_and_validate(
        article_html(mixed), mixed, policy
    )
    require(mixed_errors == [], f"Российский раздел с сюжетом отклонён: {mixed_errors}")
    require("<h2>Российские лидеры ИИ</h2>" in mixed_html, "Нет российского раздела.")
    return ["раздел можно пропустить", "пустой раздел блокируется", "раздел обязателен при российском сюжете"]


def scenario_editorial_notes(policy: dict[str, Any]) -> list[str]:
    selected = [candidate(1, time_precision="date")]
    research = {
        "coverage": [
            {"area": "russian_ai", "status": "gap", "notes": "Нет достойных тем."},
            {"area": "world_ai", "status": "covered", "notes": "Покрытие есть."},
        ]
    }
    notes = build_editorial_notes(research, selected, policy)
    note_types = {str(item.get("type")) for item in notes}
    expected = {"low_news_volume", "regional_gap", "time_precision", "source_gap"}
    require(expected.issubset(note_types), f"Не хватает editorial_notes: {expected - note_types}")
    return sorted(expected)


def scenario_diversity_override(policy: dict[str, Any]) -> list[str]:
    selected = [
        candidate(index, publisher="Один издатель", organization="Одна компания")
        for index in range(1, 4)
    ]
    errors = validate_diversity_overrides(selected, [], policy)
    require(len(errors) == 2, f"Ожидались ошибки publisher и organization: {errors}")
    overrides = [
        {
            "type": "publisher",
            "value": "Один издатель",
            "reason": "Три независимых значимых события.",
        },
        {
            "type": "organization",
            "value": "Одна компания",
            "reason": "События относятся к разным продуктам и рынкам.",
        },
    ]
    require(
        validate_diversity_overrides(selected, overrides, policy) == [],
        "Полные diversity overrides должны разрешать превышение.",
    )
    return ["превышение без причины блокируется", "publisher override", "organization override"]


def scenario_candidate_order(policy: dict[str, Any]) -> list[str]:
    first = candidate(1)
    second = candidate(2)
    source = article_html([second, first])
    ordered, errors = order_candidates_by_article_links(source, [first, second])
    require(errors == [], f"Порядок не удалось сопоставить: {errors}")
    require([item["id"] for item in ordered] == [second["id"], first["id"]], "Неверный порядок кандидатов.")
    normalized, _short, policy_errors, _warnings, _analysis = normalise_and_validate(
        source, ordered, policy
    )
    require(policy_errors == [], f"Нормализованный порядок не прошёл политику: {policy_errors}")
    stories = build_stories(ordered, normalized)
    require(validate_stories(stories, ordered) == [], "Порядок stories.json не совпал.")

    shared_url = "https://example.com/shared"
    ambiguous_a = candidate(3, url=shared_url)
    ambiguous_b = candidate(4, url=shared_url)
    _ordered, ambiguous_errors = order_candidates_by_article_links(
        article_html([ambiguous_a]), [ambiguous_a, ambiguous_b]
    )
    require(
        any("несколькими кандидатами" in item for item in ambiguous_errors),
        f"Неоднозначное сопоставление не заблокировано: {ambiguous_errors}",
    )
    return ["порядок определяется ссылками", "stories следует порядку", "неоднозначность блокируется"]


def scenario_what_it_means_bounds(policy: dict[str, Any]) -> list[str]:
    selected = [candidate(1)]
    for valid_count in (4, 6):
        _html, _short, errors, _warnings, analysis = normalise_and_validate(
            article_html(selected, what_items=valid_count), selected, policy
        )
        require(errors == [], f"{valid_count} выводов должны быть допустимы: {errors}")
        require(analysis["what_it_means_items"] == valid_count, "Неверный подсчёт выводов.")
    for invalid_count in (3, 7):
        _html, _short, errors, _warnings, analysis = normalise_and_validate(
            article_html(selected, what_items=invalid_count), selected, policy
        )
        require(errors, f"{invalid_count} выводов должны блокироваться.")
        require(analysis["what_it_means_items"] == invalid_count, "Неверный подсчёт выводов.")
    return ["4 и 6 допустимы", "3 и 7 блокируются"]


def scenario_paragraph_bounds(policy: dict[str, Any]) -> list[str]:
    selected = [candidate(1)]
    for valid_count in (2, 3):
        _html, _short, errors, _warnings, analysis = normalise_and_validate(
            article_html(selected, paragraphs=valid_count), selected, policy
        )
        require(errors == [], f"{valid_count} абзаца должны быть допустимы: {errors}")
        require(analysis["story_paragraph_counts"] == [valid_count], "Неверный подсчёт абзацев.")
    for invalid_count in (1, 4):
        _html, _short, errors, _warnings, analysis = normalise_and_validate(
            article_html(selected, paragraphs=invalid_count), selected, policy
        )
        require(errors, f"{invalid_count} абзацев должны блокироваться.")
        require(analysis["story_paragraph_counts"] == [invalid_count], "Неверный подсчёт абзацев.")
    return ["2 и 3 допустимы", "1 и 4 блокируются"]


def scenario_terminology(policy: dict[str, Any]) -> list[str]:
    selected = [candidate(1)]
    _html, _short, bad_errors, _warnings, _analysis = normalise_and_validate(
        article_html(selected, body_phrase="AI agent выполнил задачу в тестовой среде."),
        selected,
        policy,
    )
    require(
        any("агент ИИ" in item for item in bad_errors),
        f"Форма AI agent не заблокирована: {bad_errors}",
    )
    _html, _short, good_errors, _warnings, _analysis = normalise_and_validate(
        article_html(selected, body_phrase="Агент ИИ выполнил задачу в тестовой среде."),
        selected,
        policy,
    )
    require(good_errors == [], f"Форма «агент ИИ» отклонена: {good_errors}")
    return ["AI agent блокируется", "агент ИИ допускается"]


def scenario_archive_dedup_guard(policy: dict[str, Any]) -> list[str]:
    del policy
    generator = GENERATOR_PATH.read_text(encoding="utf-8")
    required_markers = [
        "rejected_as_duplicates",
        "allowed_archive_reuse",
        'candidate.get("archive_status") == "update"',
        "normalize_url",
    ]
    missing = [marker for marker in required_markers if marker not in generator]
    require(not missing, f"В генераторе не хватает archive/dedup guards: {missing}")
    return [
        "research хранит rejected_as_duplicates",
        "URL нормализуются",
        "повторное использование разрешено только update",
    ]


def scenario_cited_sources_only(policy: dict[str, Any]) -> list[str]:
    item = candidate(1)
    supporting = {
        "title": "Подтверждающий источник",
        "publisher": "Независимое издание",
        "url": "https://example.com/supporting/cand-001",
    }
    item["supporting_sources"] = [supporting]
    source = article_html([item]).replace(
        item["primary_source"]["url"], supporting["url"]
    )
    normalized, _short, errors, _warnings, _analysis = normalise_and_validate(
        source, [item], policy
    )
    require(errors == [], f"Статья с supporting source отклонена: {errors}")
    stories = build_stories([item], normalized)
    require(validate_stories(stories, [item]) == [], "stories.json не прошёл проверку.")
    require(len(stories[0]["sources"]) == 1, "Должен сохраниться один процитированный источник.")
    require(
        stories[0]["sources"][0]["url"] == supporting["url"],
        "В stories.json попал непрочитированный primary source.",
    )
    return ["сохраняются только процитированные URL", "непроцитированный primary исключается"]


SCENARIOS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "normal-digest-6": scenario_normal_digest,
    "short-digest-3": scenario_short_digest,
    "zero-stories-error": scenario_zero_stories_guard,
    "meta-marking": scenario_meta_marking,
    "update-prefix": scenario_update_prefix,
    "russian-section": scenario_russian_section,
    "editorial-notes": scenario_editorial_notes,
    "diversity-override": scenario_diversity_override,
    "candidate-order": scenario_candidate_order,
    "archive-dedup-guard": scenario_archive_dedup_guard,
    "cited-sources-only": scenario_cited_sources_only,
    "what-it-means-bounds": scenario_what_it_means_bounds,
    "paragraph-bounds": scenario_paragraph_bounds,
    "terminology": scenario_terminology,
}


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден manifest сценариев: {MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный manifest сценариев: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("scenarios"), list):
        raise RuntimeError("Manifest сценариев должен содержать массив scenarios.")
    return value


def validate_manifest(manifest: dict[str, Any]) -> None:
    ids: list[str] = []
    for position, item in enumerate(manifest["scenarios"], start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"scenarios[{position}] должен быть объектом.")
        scenario_id = str(item.get("id", "")).strip()
        expected = str(item.get("expected", "")).strip()
        requirements = item.get("requirements")
        if not scenario_id:
            raise RuntimeError(f"scenarios[{position}] не содержит id.")
        if expected not in {"pass", "blocked"}:
            raise RuntimeError(f"scenarios[{position}] имеет неизвестный expected.")
        if not isinstance(requirements, list) or not requirements:
            raise RuntimeError(f"scenarios[{position}] не содержит requirements.")
        ids.append(scenario_id)
    if len(ids) != len(set(ids)):
        raise RuntimeError("Manifest содержит повторяющиеся scenario id.")
    implemented = set(SCENARIOS)
    declared = set(ids)
    if implemented != declared:
        missing = sorted(declared - implemented)
        extra = sorted(implemented - declared)
        raise RuntimeError(
            "Manifest и код сценариев расходятся. "
            f"Не реализованы: {missing}; не объявлены: {extra}."
        )


def run_scenarios() -> dict[str, Any]:
    policy = read_policy(POLICY_PATH)
    manifest = load_manifest()
    validate_manifest(manifest)
    results: list[ScenarioResult] = []
    for item in manifest["scenarios"]:
        scenario_id = str(item["id"])
        function = SCENARIOS[scenario_id]
        try:
            checks = function(policy)
            results.append(
                ScenarioResult(
                    scenario_id=scenario_id,
                    status="passed",
                    checks=checks,
                )
            )
        except Exception as exc:  # scenario report must include all failures
            results.append(
                ScenarioResult(
                    scenario_id=scenario_id,
                    status="failed",
                    checks=[],
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    failed = [item for item in results if item.status != "passed"]
    return {
        "status": "ok" if not failed else "error",
        "spec_version": policy.get("spec_version"),
        "scenario_count": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "network_used": False,
        "openai_used": False,
        "results": [asdict(item) for item in results],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Проверить расширенную офлайн-матрицу редакционных сценариев."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_scenarios()
        output = args.output
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Editorial scenario matrix: {report['status']}")
        print(f"Сценариев: {report['scenario_count']}; ошибок: {report['failed']}")
        print(f"Отчёт: {output.relative_to(ROOT)}")
        if report["status"] != "ok":
            for item in report["results"]:
                if item["status"] != "passed":
                    print(f"- {item['scenario_id']}: {item['error']}", file=sys.stderr)
            return 1
        return 0
    except Exception as exc:
        print(f"Editorial scenario matrix failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
