from __future__ import annotations

import argparse
import json
from pathlib import Path

from story_coverage import coverage_summary, read_json, write_json


SHORT_NOTICE_HTML = "<p><em>Новостей сегодня меньше, чем обычно</em></p>"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Проверить, что выпуск содержит хотя бы один сюжет и корректно "
            "помечен как обычный или короткий."
        )
    )
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--usual-total", type=int, default=7)
    parser.add_argument("--minimum-publishable", type=int, default=1)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    stories = read_json(args.artifact_dir / "stories.json")
    if not isinstance(stories, list):
        report = {
            "status": "error",
            "valid": False,
            "errors": ["stories.json должен содержать массив"],
        }
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    report = coverage_summary(
        stories,
        usual_total=args.usual_total,
        minimum_publishable=args.minimum_publishable,
    )
    report["artifact_dir"] = args.artifact_dir.as_posix()
    report["publication_mode"] = (
        "full"
        if report["usual_target_met"]
        else ("short" if report["publication_allowed"] else "empty")
    )

    curiosity_count = sum(
        1
        for story in stories
        if isinstance(story, dict) and story.get("category") == "curiosity"
    )
    report["curiosity_story_count"] = curiosity_count
    if curiosity_count > 1:
        errors.append(
            "В выпуске допускается не более одного сюжета категории curiosity."
        )

    if not report["publication_allowed"]:
        errors.append(
            "После проверки не осталось ни одного достойного сюжета; "
            "пустой выпуск публиковать нельзя."
        )
    else:
        digest = read_json(args.artifact_dir / "digest.json")
        if not isinstance(digest, dict):
            errors.append("digest.json должен содержать объект")
        else:
            expected_short = bool(report["short_digest"])
            actual_short = digest.get("short_digest")
            article_html = str(digest.get("article_html", "")).lstrip()
            if actual_short is not expected_short:
                errors.append(
                    "short_digest не соответствует числу сюжетов: "
                    f"ожидалось {expected_short}, получено {actual_short!r}."
                )
            if expected_short and not article_html.startswith(SHORT_NOTICE_HTML):
                errors.append(
                    "Короткий выпуск должен начинаться с точной курсивной "
                    "пометки о меньшем числе новостей."
                )
            if not expected_short and article_html.startswith(SHORT_NOTICE_HTML):
                errors.append(
                    "Обычный выпуск не должен содержать пометку короткого выпуска."
                )

    report["errors"] = errors
    report["valid"] = not errors
    report["status"] = "ok" if not errors else "error"
    if report["publication_mode"] == "short" and not errors:
        report["warning"] = (
            "Опубликован короткий выпуск; региональные квоты не применяются."
        )
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
