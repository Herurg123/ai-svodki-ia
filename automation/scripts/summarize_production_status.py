
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

REPORT_ROOT = Path("automation/preview/production-daily")


def read_json_if_exists(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def first_error(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None

    for key in ("error", "error_message", "failure_reason"):
        raw = value.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

    errors = value.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                nested = first_error(item)
                if nested:
                    return nested

    for key in (
        "research",
        "editorial",
        "api",
        "validation",
        "result",
    ):
        nested = first_error(value.get(key))
        if nested:
            return nested
    return None


def find_publication_dir(publication_date: str) -> Path | None:
    candidate = Path("automation/preview") / publication_date
    return candidate if candidate.is_dir() else None


def locate_reason(publication_date: str) -> tuple[str, str]:
    candidates = [
        (
            "Проверка состава новостей",
            REPORT_ROOT / "coverage-audit.json",
        ),
        (
            "Проверка состава новостей",
            REPORT_ROOT / "story-coverage-validation.json",
        ),
        (
            "Восстановление artifact",
            REPORT_ROOT / "recovery.json",
        ),
        (
            "Проверка предыдущего выпуска",
            REPORT_ROOT / "previous-release.json",
        ),
        (
            "Проверка окна поиска",
            REPORT_ROOT / "search-window-continuity.json",
        ),
        (
            "Предварительный production-контракт",
            REPORT_ROOT / "preflight" / "contract.json",
        ),
        (
            "Подготовка runtime",
            REPORT_ROOT / "preflight" / "runtime.json",
        ),
        (
            "Генерация изображения",
            REPORT_ROOT / "image-api-error.json",
        ),
        (
            "Проверка изображения",
            REPORT_ROOT
            / "image"
            / publication_date
            / "cover-validation.json",
        ),
        (
            "Сборка сайта",
            REPORT_ROOT / "candidate" / "site-validation.json",
        ),
        (
            "Structured data",
            REPORT_ROOT
            / "candidate"
            / "structured-data-validation.json",
        ),
        (
            "RSS",
            REPORT_ROOT
            / "candidate"
            / "dzen-feed-validation.json",
        ),
        (
            "Sitemap",
            REPORT_ROOT
            / "candidate"
            / "posts-sitemap-validation.json",
        ),
        (
            "Публикация candidate",
            REPORT_ROOT / "promotion.json",
        ),
        (
            "Проверка файлов перед commit",
            REPORT_ROOT / "publish-changes.json",
        ),
    ]

    publication_dir = find_publication_dir(publication_date)
    if publication_dir:
        candidates.extend(
            [
                (
                    "Research/editorial",
                    publication_dir / "run-info.json",
                ),
                (
                    "Проверка editorial artifact",
                    publication_dir / "artifact-validation.json",
                ),
            ]
        )

    for stage, path in candidates:
        value = read_json_if_exists(path)
        if not isinstance(value, dict):
            continue
        status = str(value.get("status", "")).casefold()
        reason = first_error(value)
        if status == "error" or reason:
            if reason:
                return stage, translate_reason(reason)
    return (
        "Неопределённый этап",
        "Точная причина не была сохранена в JSON-отчётах. "
        "Откройте первый красный шаг; artifact всё равно сохранён.",
    )


def translate_reason(reason: str) -> str:
    value = reason.strip()
    value = re.sub(
        r"^(RuntimeError|ValueError|AssertionError|RecoveryError):\s*",
        "",
        value,
    )
    translations = (
        (
            "После targeted audit пул всё ещё не позволяет собрать 5+2",
            "После дополнительного поиска всё ещё не найдено "
            "минимум 5 мировых и 2 российских достойных сюжета",
        ),
        (
            "Latest RSS item must be the previous calendar day",
            "Последний выпуск в RSS не датирован предыдущим календарным днём",
        ),
        (
            "main changed while generation was running",
            "Ветка main изменилась во время генерации; commit отменён",
        ),
        (
            "OPENAI_API_KEY missing",
            "Не настроен секрет OPENAI_API_KEY",
        ),
        (
            "Unexpected image model",
            "Указана неподдерживаемая модель изображения",
        ),
        (
            "Unexpected text model",
            "Указана неподдерживаемая текстовая модель",
        ),
        (
            "RSS already contains",
            "В RSS уже присутствует выпуск за эту дату",
        ),
    )
    for source, translated in translations:
        if source in value:
            value = value.replace(source, translated)
    return value


def stage_state(publication_date: str) -> dict[str, bool]:
    publication_dir = find_publication_dir(publication_date)
    run_info = (
        read_json_if_exists(publication_dir / "run-info.json")
        if publication_dir
        else None
    )
    coverage = read_json_if_exists(REPORT_ROOT / "coverage-audit.json")
    image_dir = REPORT_ROOT / "image" / publication_date
    image_manifest = read_json_if_exists(
        image_dir / "image-manifest.json"
    )
    promotion = read_json_if_exists(REPORT_ROOT / "promotion.json")

    research = False
    editorial = False
    if isinstance(run_info, dict):
        research_value = run_info.get("research")
        editorial_value = run_info.get("editorial")
        research = (
            isinstance(research_value, dict)
            and research_value.get("status") == "ok"
        )
        editorial = (
            isinstance(editorial_value, dict)
            and editorial_value.get("status") == "ok"
        )
    if publication_dir:
        research = research or (
            (publication_dir / "candidates.json").is_file()
            and (publication_dir / "research-output-raw.json").is_file()
        )
        editorial = editorial or (
            (publication_dir / "stories.json").is_file()
            and (publication_dir / "digest.json").is_file()
        )

    audit = (
        isinstance(coverage, dict)
        and bool(coverage.get("web_search_performed"))
    )
    image = (
        (image_dir / "cover.png").is_file()
        and isinstance(image_manifest, dict)
        and image_manifest.get("status") == "ok"
    )
    promoted = (
        isinstance(promotion, dict)
        and promotion.get("status") == "ok"
        and not bool(promotion.get("dry_run"))
    )
    return {
        "research": research,
        "editorial": editorial,
        "coverage_audit": audit,
        "image": image,
        "promoted": promoted,
    }


def markdown_bool(value: bool) -> str:
    return "✅ завершён" if value else "➖ не завершён"


def escape_annotation(value: str) -> str:
    return (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def build_summary(
    *,
    job_status: str,
    publication_date: str,
    publish: str,
    recovery_run_id: str,
    run_url: str,
    commit_sha: str,
) -> tuple[str, str | None]:
    states = stage_state(publication_date)
    success = job_status == "success"

    if success:
        title = (
            "## ✅ ИИ-Сводка: production завершён"
            if publish == "true"
            else "## ✅ ИИ-Сводка: dry-run завершён"
        )
        lines = [
            title,
            "",
            f"- **Дата выпуска:** `{publication_date}`",
            f"- **Commit:** `{commit_sha or 'не создавался'}`",
            f"- **Recovery run ID:** `{recovery_run_id or 'нет'}`",
            f"- **Run:** {run_url}",
            "",
            "### Этапы",
            f"- Research: {markdown_bool(states['research'])}",
            f"- Editorial: {markdown_bool(states['editorial'])}",
            (
                "- Дополнительный поиск: "
                f"{markdown_bool(states['coverage_audit'])}"
            ),
            f"- Изображение: {markdown_bool(states['image'])}",
            f"- Promotion: {markdown_bool(states['promoted'])}",
        ]
        return "\n".join(lines) + "\n", None

    stage, reason = locate_reason(publication_date)
    paid_completed = any(
        states[key]
        for key in (
            "research",
            "editorial",
            "coverage_audit",
            "image",
        )
    )

    if "не найдено минимум 5 мировых" in reason:
        action = (
            "Это редакционная остановка, а не техническая авария. "
            "Не повторяйте поиск сразу. Следующий выпуск возьмёт окно "
            "с последнего успешно опубликованного выпуска."
        )
    elif paid_completed:
        action = (
            "Не запускайте полный production повторно. Сначала скачайте "
            f"artifact `daily-production-{publication_date}` и используйте "
            f"`recovery_run_id={os.environ.get('GITHUB_RUN_ID', '')}` "
            "после исправления причины."
        )
    else:
        action = (
            "Платные этапы не подтверждены. Исправьте указанную причину, "
            "после чего создайте новый запуск."
        )

    lines = [
        "## ❌ ИИ-Сводка не опубликована",
        "",
        f"- **Дата выпуска:** `{publication_date}`",
        f"- **Этап остановки:** {stage}",
        f"- **Причина:** {reason}",
        f"- **Run:** {run_url}",
        f"- **Recovery run ID входа:** `{recovery_run_id or 'нет'}`",
        "",
        "### Что уже выполнено",
        f"- Research: {markdown_bool(states['research'])}",
        f"- Editorial: {markdown_bool(states['editorial'])}",
        (
            "- Дополнительный поиск: "
            f"{markdown_bool(states['coverage_audit'])}"
        ),
        f"- Изображение: {markdown_bool(states['image'])}",
        f"- Promotion: {markdown_bool(states['promoted'])}",
        "",
        "### Безопасное следующее действие",
        action,
    ]
    annotation = f"{stage}: {reason}"
    return "\n".join(lines) + "\n", annotation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-status", required=True)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--publish", default="false")
    parser.add_argument("--recovery-run-id", default="")
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        markdown, annotation = build_summary(
            job_status=args.job_status,
            publication_date=args.publication_date,
            publish=args.publish,
            recovery_run_id=args.recovery_run_id,
            run_url=args.run_url,
            commit_sha=args.commit_sha,
        )
        report = {
            "status": (
                "ok" if args.job_status == "success" else "error"
            ),
            "publication_date": args.publication_date,
            "job_status": args.job_status,
            "annotation": annotation,
            "run_url": args.run_url,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8") as stream:
                stream.write(markdown)

        print(markdown)
        if annotation:
            print(
                "::error title=ИИ-Сводка не опубликована::"
                + escape_annotation(annotation)
            )
    except Exception as exc:
        fallback = (
            "## ❌ Не удалось сформировать диагностическую сводку\n\n"
            f"- Ошибка диагностики: {type(exc).__name__}: {exc}\n"
            f"- Run: {args.run_url}\n"
        )
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8") as stream:
                stream.write(fallback)
        print(fallback)
        print(
            "::error title=Ошибка диагностики::"
            + escape_annotation(f"{type(exc).__name__}: {exc}")
        )

    # A summary must never hide the original workflow failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
