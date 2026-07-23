from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EDITORIAL_CONFIG = ROOT / "automation" / "config" / "editorial.json"
SITE_CONFIG = ROOT / "automation" / "config" / "site.json"
POLICY_SPEC = ROOT / "automation" / "specs" / "editorial-policy.md"
DAILY_PROMPT = ROOT / "automation" / "prompts" / "daily_digest.md"
RESEARCH_PROMPT = ROOT / "automation" / "prompts" / "research_candidates.md"
GENERATOR = ROOT / "automation" / "scripts" / "generate_digest_preview.py"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный файл: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} должен содержать JSON-объект.")
    return value


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"Не найден обязательный файл: {path}") from exc


def require_equal(
    errors: list[str],
    actual: Any,
    expected: Any,
    label: str,
) -> None:
    if actual != expected:
        errors.append(f"{label}: ожидалось {expected!r}, получено {actual!r}.")


def require_markers(
    errors: list[str],
    text: str,
    markers: list[str],
    label: str,
) -> None:
    for marker in markers:
        if marker not in text:
            errors.append(f"{label}: отсутствует обязательный маркер {marker!r}.")


def nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def validate() -> list[str]:
    errors: list[str] = []
    editorial = read_json(EDITORIAL_CONFIG)
    site = read_json(SITE_CONFIG)
    spec = read_text(POLICY_SPEC)
    daily = read_text(DAILY_PROMPT)
    research = read_text(RESEARCH_PROMPT)
    generator = read_text(GENERATOR)

    require_equal(
        errors,
        nested(editorial, "story_counts", "total_target_minimum"),
        6,
        "Минимальная обычная цель сюжетов",
    )
    require_equal(
        errors,
        nested(editorial, "story_counts", "total_target_maximum"),
        12,
        "Максимальная цель сюжетов",
    )
    require_equal(
        errors,
        nested(editorial, "story_counts", "short_digest_minimum"),
        1,
        "Минимум короткого выпуска",
    )
    require_equal(
        errors,
        nested(editorial, "story_counts", "short_digest_notice"),
        "День на новости выдался слабым - поэтому коротко",
        "Точная фраза короткого выпуска",
    )
    require_equal(
        errors,
        nested(editorial, "dzen", "heading"),
        "Все ИИ-Сводки",
        "Заголовок Дзена",
    )
    require_equal(
        errors,
        nested(editorial, "dzen", "anchor_text"),
        "Архив ИИ-Сводок",
        "Текст ссылки Дзена",
    )
    require_equal(
        errors,
        nested(editorial, "meta_marking", "first_visible_form"),
        "Meta*",
        "Первое видимое упоминание Meta",
    )
    require_equal(
        errors,
        nested(editorial, "meta_marking", "footnote_html"),
        "<p><em>*Meta и ее сервисы - в России запрещены</em></p>",
        "Сноска Meta",
    )
    require_equal(
        errors,
        nested(editorial, "updates", "headline_prefix"),
        "Обновление: ",
        "Префикс обновления",
    )
    require_equal(
        errors,
        nested(editorial, "article", "paragraphs_per_story_minimum"),
        2,
        "Минимум абзацев на сюжет",
    )
    require_equal(
        errors,
        nested(editorial, "article", "paragraphs_per_story_maximum"),
        3,
        "Максимум абзацев на сюжет",
    )
    require_equal(
        errors,
        nested(editorial, "what_it_means", "minimum_items"),
        4,
        "Минимум выводов",
    )
    require_equal(
        errors,
        nested(editorial, "what_it_means", "maximum_items"),
        6,
        "Максимум выводов",
    )
    require_equal(
        errors,
        site.get("editorial_config_file"),
        "automation/config/editorial.json",
        "Путь editorial config",
    )
    require_equal(
        errors,
        site.get("stories_filename"),
        "stories.json",
        "Имя структурированного архива выпуска",
    )

    common_markers = [
        "День на новости выдался слабым - поэтому коротко",
        "Все ИИ-Сводки",
        "Архив ИИ-Сводок",
        "Meta*",
        "*Meta и ее сервисы - в России запрещены",
        "Обновление:",
        "stories.json",
    ]
    require_markers(errors, spec, common_markers, "editorial-policy.md")
    require_markers(
        errors,
        daily,
        [
            "День на новости выдался слабым - поэтому коротко",
            "5–8 мировых сюжетов",
            "3–5 российских сюжетов",
            "2–3 абзаца на сюжет",
            "Количество выводов: 4–6",
            "Архив ИИ-Сводок",
            "Meta*",
            "Обновление:",
            "агент ИИ",
            "Изображение 16:9:",
            "Главные визуальные темы:",
            "Композиция:",
            "Стиль:",
        ],
        "daily_digest.md",
    )
    require_markers(
        errors,
        research,
        [
            "{{SEARCH_WINDOW_START_AT}}",
            "{{SEARCH_WINDOW_END_AT}}",
            "Alibaba и Qwen",
            "Baidu и ERNIE",
            "Moonshot AI и Kimi",
            "Z.ai, Zhipu AI и GLM",
            "Claude Code",
            "GitHub Copilot",
            "OpenCode",
            "Cline",
            "Яндекс",
            "МТС AI",
            "Газпромбанк",
            "Ростелеком",
            "time_precision",
        ],
        "research_candidates.md",
    )
    require_markers(
        errors,
        generator,
        [
            "from editorial_policy import",
            "normalize_article_html",
            "build_editorial_notes",
            "build_stories",
            'output_dir / "stories.json"',
            'output_dir / "policy-normalization.json"',
        ],
        "generate_digest_preview.py",
    )

    return errors


def main() -> int:
    try:
        errors = validate()
    except Exception as exc:
        print(f"Editorial contract check failed unexpectedly: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("Editorial contract check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Editorial contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
