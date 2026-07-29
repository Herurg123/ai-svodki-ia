#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD_NOTICE = "День на новости выдался слабым - поэтому коротко"
NEW_NOTICE = "Новостей сегодня меньше, чем обычно"
NEW_NOTICE_HTML = f"<p><em>{NEW_NOTICE}</em></p>"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_required(text: str, old: str, new: str, label: str, count: int | None = 1) -> str:
    found = text.count(old)
    if count is not None and found != count:
        raise RuntimeError(f"{label}: expected {count} occurrence(s), found {found}")
    if found == 0:
        raise RuntimeError(f"{label}: pattern not found")
    return text.replace(old, new, found if count is None else count)


def patch_editorial_config() -> None:
    path = "automation/config/editorial.json"
    data = json.loads(read(path))
    counts = data["story_counts"]
    counts["total_target_minimum"] = 7
    counts["short_digest_minimum"] = 1
    counts["short_digest_notice"] = NEW_NOTICE
    counts["short_digest_notice_html"] = NEW_NOTICE_HTML
    article = data["article"]
    article["china_heading"] = "Китайские лидеры ИИ"
    article["allow_missing_china_section"] = True
    article["allow_missing_russian_section"] = True
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def patch_prompt() -> None:
    path = "automation/prompts/daily_digest.md"
    text = read(path)
    text = text.replace("Если найдено от 1 до 5 достойных сюжетов:", "Если найдено от 1 до 6 достойных сюжетов:")
    text = text.replace(f"<p>{OLD_NOTICE}</p>", NEW_NOTICE_HTML)
    text = text.replace(OLD_NOTICE, NEW_NOTICE)
    text = text.replace(
        "1. `<h2>Мировые лидеры ИИ</h2>`;\n2. мировые сюжеты;\n3. `<h2>Российские лидеры ИИ</h2>`, если выбраны российские сюжеты;\n4. российские сюжеты;\n5. `<h2>Что это значит</h2>`;\n6. `<ol>` с 4–6 выводами;\n7. точный блок Дзена, указанный ниже;\n8. сноска Meta, если она требуется.",
        "1. `<h2>Мировые лидеры ИИ</h2>`;\n2. мировые сюжеты, не относящиеся к китайским компаниям;\n3. `<h2>Китайские лидеры ИИ</h2>`, только если выбраны сюжеты о китайских компаниях или моделях;\n4. китайские сюжеты;\n5. `<h2>Российские лидеры ИИ</h2>`, только если выбраны российские сюжеты;\n6. российские сюжеты;\n7. `<h2>Что это значит</h2>`;\n8. `<ol>` с 4–6 выводами;\n9. точный блок Дзена, указанный ниже;\n10. сноска Meta, если она требуется.\n\nНе создавай пустые разделы «Китайские лидеры ИИ» и «Российские лидеры ИИ»."
    )
    text = text.replace(
        "Короткий выпуск сначала содержит точную фразу о слабом новостном дне, затем обычное вступление.",
        "Короткий выпуск сначала содержит точную курсивную пометку о меньшем числе новостей, затем обычное вступление."
    )
    write(path, text)


def patch_spec() -> None:
    path = "automation/specs/editorial-policy.md"
    text = read(path)
    text = text.replace("Версия: 2026-07-12", "Версия: 2026-07-29")
    text = text.replace("- 6–12 сюжетов.", "- 7–12 сюжетов.")
    text = text.replace("Если найдено 1–5 достойных сюжетов:", "Если найдено 1–6 достойных сюжетов:")
    text = text.replace(f"<p>{OLD_NOTICE}</p>", NEW_NOTICE_HTML)
    text = text.replace(OLD_NOTICE, NEW_NOTICE)
    text = text.replace(
        "<h2>Мировые лидеры ИИ</h2>\n<h2>Российские лидеры ИИ</h2>\n<h2>Что это значит</h2>",
        "<h2>Мировые лидеры ИИ</h2>\n<h2>Китайские лидеры ИИ</h2>\n<h2>Российские лидеры ИИ</h2>\n<h2>Что это значит</h2>"
    )
    text = text.replace(
        "Раздел с российскими новостями допускается не выводить, если достойных российских сюжетов нет.",
        "Разделы с китайскими и российскими новостями выводятся только при наличии соответствующих выбранных сюжетов. Пустые разделы запрещены."
    )
    write(path, text)


def patch_editorial_policy_runtime() -> None:
    path = "automation/scripts/editorial_policy.py"
    text = read(path)
    old_helper = '''def _remove_exact_paragraph(article_html: str, text: str) -> str:\n    pattern = re.compile(\n        r"<p>\\s*" + re.escape(text) + r"\\s*</p>\\s*",\n        flags=re.IGNORECASE,\n    )\n    return pattern.sub("", article_html)\n'''
    new_helper = '''def _remove_exact_paragraph(article_html: str, text: str) -> str:\n    pattern = re.compile(\n        r"<p>\\s*(?:<em>\\s*)?"\n        + re.escape(text)\n        + r"(?:\\s*</em>)?\\s*</p>\\s*",\n        flags=re.IGNORECASE,\n    )\n    return pattern.sub("", article_html)\n'''
    text = replace_required(text, old_helper, new_helper, "editorial_policy paragraph helper")
    text = replace_required(
        text,
        '''    short_notice = str(story_counts["short_digest_notice"])\n    total_target_minimum = int(story_counts["total_target_minimum"])\n    short_digest = 0 < len(selected_candidates) < total_target_minimum\n\n    cleaned = _remove_exact_paragraph(article_html, short_notice)\n''',
        '''    short_notice = str(story_counts["short_digest_notice"])\n    short_notice_html = str(\n        story_counts.get("short_digest_notice_html")\n        or f"<p><em>{html.escape(short_notice, quote=False)}</em></p>"\n    )\n    total_target_minimum = int(story_counts["total_target_minimum"])\n    short_digest = 0 < len(selected_candidates) < total_target_minimum\n\n    cleaned = _remove_exact_paragraph(article_html, short_notice)\n    cleaned = _remove_exact_paragraph(cleaned, "День на новости выдался слабым - поэтому коротко")\n''',
        "editorial_policy short setup"
    )
    text = replace_required(
        text,
        '''    if short_digest:\n        canonical_notice = f"<p>{html.escape(short_notice, quote=False)}</p>"\n        cleaned = canonical_notice + "\\n" + cleaned\n''',
        '''    if short_digest:\n        canonical_notice = short_notice_html\n        cleaned = canonical_notice + "\\n" + cleaned\n''',
        "editorial_policy short notice html"
    )
    text = replace_required(
        text,
        '''    if short_digest:\n        if parser.first_top_level_tag != "p" or parser.first_top_level_text != short_notice:\n            errors.append(\n                "Короткий выпуск должен начинаться с точной фразы о слабом новостном дне."\n            )\n''',
        '''    short_notice_html = str(\n        counts.get("short_digest_notice_html")\n        or f"<p><em>{html.escape(short_notice, quote=False)}</em></p>"\n    )\n    if short_digest:\n        if parser.first_top_level_tag != "p" or parser.first_top_level_text != short_notice:\n            errors.append(\n                "Короткий выпуск должен начинаться с точной пометки о меньшем числе новостей."\n            )\n        if not article_html.lstrip().startswith(short_notice_html):\n            errors.append("Пометка короткого выпуска должна быть курсивной и иметь точный HTML.")\n''',
        "editorial_policy short validation"
    )
    text = replace_required(
        text,
        '''    if selected_russian == 0 and russian_heading_count:\n        errors.append(\n            f"Пустой раздел «{russian_heading}» не должен присутствовать без "\n            "российских сюжетов."\n        )\n\n    intro_html = re.split''',
        '''    if selected_russian == 0 and russian_heading_count:\n        errors.append(\n            f"Пустой раздел «{russian_heading}» не должен присутствовать без "\n            "российских сюжетов."\n        )\n\n    china_heading = str(policy["article"].get("china_heading", "Китайские лидеры ИИ"))\n    tracked_asia = [str(item).casefold() for item in policy.get("tracked_asia_organizations", [])]\n    selected_china = 0\n    for item in selected_candidates:\n        organization = str(item.get("organization", "")).casefold()\n        title = str(item.get("title", "")).casefold()\n        if any(name and (name in organization or name in title) for name in tracked_asia):\n            selected_china += 1\n    china_heading_count = parser.h2_texts.count(china_heading)\n    if selected_china > 0 and china_heading_count != 1:\n        errors.append(\n            f"При выбранных китайских сюжетах заголовок «{china_heading}» "\n            "должен встречаться ровно один раз."\n        )\n    if selected_china == 0 and china_heading_count:\n        errors.append(\n            f"Пустой раздел «{china_heading}» не должен присутствовать без "\n            "китайских сюжетов."\n        )\n\n    intro_html = re.split''',
        "editorial_policy china section"
    )
    write(path, text)


def patch_coverage_script() -> None:
    path = "automation/scripts/ensure_story_coverage.py"
    text = read(path)
    helper = r'''

SHORT_NOTICE = "Новостей сегодня меньше, чем обычно"
SHORT_NOTICE_HTML = f"<p><em>{SHORT_NOTICE}</em></p>"
LEGACY_SHORT_NOTICE = "День на новости выдался слабым - поэтому коротко"


def completed_prior_audit(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    api = payload.get("api") or {}
    return (
        payload.get("web_search_performed") is True
        and isinstance(api, dict)
        and api.get("status") == "completed"
    )


def _remove_short_notices(article_html: str) -> str:
    value = article_html
    for notice in (SHORT_NOTICE, LEGACY_SHORT_NOTICE):
        value = re.sub(
            r"^\s*<p>\s*(?:<em>\s*)?" + re.escape(notice) + r"(?:\s*</em>)?\s*</p>\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
    return value.strip()


def apply_short_edition_marker(artifact_dir: Path, *, short_edition: bool) -> None:
    digest_path = artifact_dir / "digest.json"
    meta_path = artifact_dir / "meta.json"
    editorial_path = artifact_dir / "editorial-output.json"
    article_path = artifact_dir / "article.html"
    digest = read_json(digest_path)
    if not isinstance(digest, dict):
        raise RuntimeError("digest.json должен содержать объект")
    article_html = _remove_short_notices(str(digest.get("article_html", "")))
    notes = digest.get("editorial_notes")
    if not isinstance(notes, list):
        notes = []
    notes = [
        item
        for item in notes
        if not (isinstance(item, dict) and item.get("type") == "low_news_volume")
    ]
    if short_edition:
        article_html = SHORT_NOTICE_HTML + "\n" + article_html
        notes.insert(
            0,
            {
                "type": "low_news_volume",
                "area": "total",
                "message": "После основного и дополнительного поиска опубликован сокращённый выпуск.",
            },
        )
    digest["short_digest"] = short_edition
    digest["article_html"] = article_html
    digest["editorial_notes"] = notes
    write_json(digest_path, digest)
    article_path.write_text(article_html.rstrip() + "\n", encoding="utf-8")

    if meta_path.is_file():
        meta = read_json(meta_path)
        if isinstance(meta, dict):
            meta["short_digest"] = short_edition
            meta["editorial_notes"] = notes
            write_json(meta_path, meta)

    if editorial_path.is_file():
        editorial = read_json(editorial_path)
        if isinstance(editorial, dict) and isinstance(editorial.get("digest"), dict):
            editorial["digest"] = digest
            write_json(editorial_path, editorial)
'''
    text = replace_required(text, "\ndef main() -> int:\n", helper + "\n\ndef main() -> int:\n", "coverage helper insertion")
    text = replace_required(
        text,
        "    args = parser.parse_args()\n\n    report: dict[str, Any] = {",
        "    args = parser.parse_args()\n\n    prior_report: dict[str, Any] | None = None\n    if args.report.is_file():\n        try:\n            loaded_prior = read_json(args.report)\n            if isinstance(loaded_prior, dict):\n                prior_report = loaded_prior\n        except Exception:\n            prior_report = None\n\n    report: dict[str, Any] = {",
        "coverage prior report"
    )
    text = replace_required(
        text,
        '''        "web_search_performed": False,\n        "before": None,''',
        '''        "web_search_performed": False,\n        "prior_audit_reused": False,\n        "publication_mode": None,\n        "before": None,''',
        "coverage report fields"
    )
    text = replace_required(
        text,
        '''        additional_candidates: list[Any] = []\n        if not pool_has_required_geography:\n''',
        '''        additional_candidates: list[Any] = []\n        prior_audit_complete = completed_prior_audit(prior_report)\n        if not pool_has_required_geography and not prior_audit_complete:\n''',
        "coverage audit condition"
    )
    text = replace_required(
        text,
        '''            if not isinstance(additional_candidates, list):\n                raise RuntimeError("Coverage audit candidates должен быть массивом")\n\n        merged, accepted, rejected = merge_candidates(''',
        '''            if not isinstance(additional_candidates, list):\n                raise RuntimeError("Coverage audit candidates должен быть массивом")\n        elif not pool_has_required_geography and prior_audit_complete:\n            report["audit_needed"] = True\n            report["prior_audit_reused"] = True\n            report["api"] = prior_report.get("api") if prior_report else None\n            report["queries_used"] = (prior_report or {}).get("queries_used", [])\n            report["audit_notes"] = (\n                "Использован уже завершённый targeted audit из recovery artifact; "\n                "повторный web search не выполнялся."\n            )\n\n        merged, accepted, rejected = merge_candidates(''',
        "coverage prior audit branch"
    )
    old_pool_fail = '''        pool_after = report["candidate_pool_after"]\n        if (\n            pool_after["total"] < args.minimum_total\n            or pool_after["world"] < args.minimum_world\n            or pool_after["russia"] < args.minimum_russia\n        ):\n            raise RuntimeError(\n                "После targeted audit пул всё ещё не позволяет собрать 5+2: "\n                f"всего={pool_after['total']}, world={pool_after['world']}, "\n                f"russia={pool_after['russia']}"\n            )\n\n'''
    new_pool_logic = '''        pool_after = report["candidate_pool_after"]\n        if pool_after["total"] < 1:\n            raise RuntimeError(\n                "После основного и targeted поиска не осталось ни одного достойного сюжета"\n            )\n        full_pool_available = (\n            pool_after["total"] >= args.minimum_total\n            and pool_after["world"] >= args.minimum_world\n            and pool_after["russia"] >= args.minimum_russia\n        )\n        report["short_edition_candidate"] = not full_pool_available\n\n'''
    text = replace_required(text, old_pool_fail, new_pool_logic, "coverage pool fallback")
    old_after = '''        report["after"] = after\n        if not after["valid"]:\n            raise RuntimeError(\n                "Редакторский повтор не выполнил обязательный минимум 5+2: "\n                f"всего={after['counts']['total']}, "\n                f"world={after['counts']['world']}, "\n                f"russia={after['counts']['russia']}"\n            )\n        report["status"] = "ok"\n        report["mode"] = (\n            "targeted_web_search_and_editorial_rerun"\n            if report["web_search_performed"]\n            else "editorial_rerun_only"\n        )\n'''
    new_after = '''        report["after"] = after\n        if after["counts"]["total"] < 1:\n            raise RuntimeError("Редакторский повтор не выбрал ни одного достойного сюжета")\n        short_edition = not after["valid"]\n        apply_short_edition_marker(args.artifact_dir, short_edition=short_edition)\n        report["publication_mode"] = "short" if short_edition else "full"\n        report["status"] = "ok"\n        if report["prior_audit_reused"]:\n            report["mode"] = "reused_completed_audit_and_editorial_rerun"\n        elif report["web_search_performed"]:\n            report["mode"] = "targeted_web_search_and_editorial_rerun"\n        else:\n            report["mode"] = "editorial_rerun_only"\n'''
    text = replace_required(text, old_after, new_after, "coverage final short mode")
    if "import re" not in text.split("\n", 20):
        text = text.replace("import os\n", "import os\nimport re\n", 1)
    write(path, text)


def patch_story_coverage_validator() -> None:
    path = "automation/scripts/validate_story_coverage.py"
    content = '''from __future__ import annotations

import argparse
import json
from pathlib import Path

from story_coverage import coverage_summary, read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверить состав итоговой ИИ-сводки и разрешённый короткий выпуск."
    )
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--minimum-total", type=int, default=7)
    parser.add_argument("--minimum-world", type=int, default=5)
    parser.add_argument("--minimum-russia", type=int, default=2)
    parser.add_argument("--audit-report", type=Path)
    parser.add_argument("--allow-short-after-audit", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    stories = read_json(args.artifact_dir / "stories.json")
    if not isinstance(stories, list):
        report = {"status": "error", "errors": ["stories.json должен содержать массив"]}
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    report = coverage_summary(
        stories,
        minimum_total=args.minimum_total,
        minimum_world=args.minimum_world,
        minimum_russia=args.minimum_russia,
    )
    report["artifact_dir"] = args.artifact_dir.as_posix()
    report["publication_mode"] = "full" if report["valid"] else "short"

    if report["valid"]:
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    audit = None
    if args.audit_report and args.audit_report.is_file():
        audit = read_json(args.audit_report)
    short_allowed = (
        args.allow_short_after_audit
        and len(stories) > 0
        and isinstance(audit, dict)
        and audit.get("status") == "ok"
        and audit.get("publication_mode") == "short"
    )
    if short_allowed:
        report["status"] = "ok"
        report["valid"] = True
        report["coverage_target_met"] = False
        report["warning"] = (
            "После основного и дополнительного поиска опубликован короткий выпуск."
        )
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    report["errors"] = [
        "Итоговый выпуск не выполняет обычный минимум и не подтверждён как короткий: "
        f"всего {report['counts']['total']}/{args.minimum_total}, "
        f"мировых {report['counts']['world']}/{args.minimum_world}, "
        f"российских {report['counts']['russia']}/{args.minimum_russia}."
    ]
    report["status"] = "error"
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''
    write(path, content)


def patch_digest_validator() -> None:
    path = "automation/scripts/validate_digest_artifact.py"
    text = read(path)
    old = '''    elif 1 <= story_count <= 5:\n        if short_digest is not True:\n            issue(report, "errors", "short_digest_flag", "Для 1–5 сюжетов short_digest должен быть true.")\n        notice = "<p>День на новости выдался слабым - поэтому коротко</p>"\n        if article_html and not article_html.lstrip().startswith(notice):\n            issue(report, "errors", "short_digest_notice", "Короткий выпуск должен начинаться с точного уведомления о слабом новостном дне.")\n        if "low_news_volume" not in note_types(meta.get("editorial_notes")):\n            issue(report, "errors", "low_news_volume_note", "Для короткого выпуска editorial_notes должен содержать low_news_volume.")\n    elif story_count >= 6 and short_digest is True:\n        issue(report, "errors", "short_digest_false", "Для 6 и более сюжетов short_digest не должен быть true.")\n'''
    new = '''    elif 1 <= story_count <= 6:\n        if short_digest is not True:\n            issue(report, "errors", "short_digest_flag", "Для 1–6 сюжетов short_digest должен быть true.")\n        notice = "<p><em>Новостей сегодня меньше, чем обычно</em></p>"\n        if article_html and not article_html.lstrip().startswith(notice):\n            issue(report, "errors", "short_digest_notice", "Короткий выпуск должен начинаться с точной курсивной пометки о меньшем числе новостей.")\n        if "low_news_volume" not in note_types(meta.get("editorial_notes")):\n            issue(report, "errors", "low_news_volume_note", "Для короткого выпуска editorial_notes должен содержать low_news_volume.")\n    elif story_count >= 7 and short_digest is True:\n        issue(report, "errors", "short_digest_false", "Для 7 и более сюжетов short_digest не должен быть true.")\n'''
    text = replace_required(text, old, new, "digest short validation")
    write(path, text)


def patch_workflow() -> None:
    path = ".github/workflows/daily-production.yml"
    text = read(path)
    text = replace_required(
        text,
        '''          terminal = (\n              data.get("status") == "error"\n              and data.get("web_search_performed") is True\n              and api.get("status") == "completed"\n          )\n''',
        '''          pool = data.get("candidate_pool_after") or data.get("candidate_pool_before") or {}\n          before_counts = (data.get("before") or {}).get("counts") or {}\n          available = max(\n              int(pool.get("total", 0) or 0),\n              int(before_counts.get("total", 0) or 0),\n          )\n          terminal = (\n              data.get("status") == "error"\n              and data.get("web_search_performed") is True\n              and api.get("status") == "completed"\n              and available == 0\n          )\n''',
        "workflow terminal reuse"
    )
    text = text.replace(
        "Enforce 5 world plus 2 Russian stories",
        "Complete coverage and allow short edition after audit"
    )
    text = replace_required(
        text,
        '''            --minimum-russia 2 \\\n            --report automation/preview/production-daily/story-coverage-validation.json\n''',
        '''            --minimum-russia 2 \\\n            --audit-report automation/preview/production-daily/coverage-audit.json \\\n            --allow-short-after-audit \\\n            --report automation/preview/production-daily/story-coverage-validation.json\n''',
        "workflow short validator args"
    )
    write(path, text)


def patch_contract_validator() -> None:
    path = "automation/scripts/validate_editorial_contract.py"
    text = read(path)
    text = text.replace(
        '''        nested(editorial, "story_counts", "total_target_minimum"),\n        6,\n        "Внутренний порог обычного выпуска",''',
        '''        nested(editorial, "story_counts", "total_target_minimum"),\n        7,\n        "Порог обычного выпуска",'''
    )
    text = text.replace(OLD_NOTICE, NEW_NOTICE)
    text = text.replace("7–12 сюжетов всего", "7–12 сюжетов всего")
    write(path, text)


def patch_tests() -> None:
    replacements = {
        "automation/tests/test_production_contract_sync.py": [
            ("self.assertEqual(editorial[\"story_counts\"][\"total_target_minimum\"], 6)", "self.assertEqual(editorial[\"story_counts\"][\"total_target_minimum\"], 7)"),
            ("Enforce 5 world plus 2 Russian stories", "Complete coverage and allow short edition after audit"),
        ],
        "automation/tests/test_production_reliability_patch.py": [
            ("Enforce 5 world plus 2 Russian stories", "Complete coverage and allow short edition after audit"),
        ],
    }
    for path, pairs in replacements.items():
        text = read(path)
        for old, new in pairs:
            text = text.replace(old, new)
        if path.endswith("test_production_contract_sync.py"):
            anchor = '        self.assertIn("--maximum-audit-web-search-calls 5", workflow)\n'
            if anchor in text and "--allow-short-after-audit" not in text:
                text = text.replace(
                    anchor,
                    anchor
                    + '        self.assertIn("--allow-short-after-audit", workflow)\n'
                    + '        self.assertIn("--audit-report automation/preview/production-daily/coverage-audit.json", workflow)\n',
                    1,
                )
        write(path, text)


def patch_all_notice_references() -> None:
    targets = [
        "automation/scripts/validate_editorial_contract.py",
        "automation/tests/test_short_digest.py",
        "automation/tests/test_editorial_policy.py",
    ]
    for path in targets:
        file_path = ROOT / path
        if not file_path.is_file():
            continue
        text = file_path.read_text(encoding="utf-8")
        text = text.replace(f"<p>{OLD_NOTICE}</p>", NEW_NOTICE_HTML)
        text = text.replace(OLD_NOTICE, NEW_NOTICE)
        text = text.replace("1–5", "1–6")
        text = text.replace("1-5", "1-6")
        file_path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_editorial_config()
    patch_prompt()
    patch_spec()
    patch_editorial_policy_runtime()
    patch_coverage_script()
    patch_story_coverage_validator()
    patch_digest_validator()
    patch_workflow()
    patch_contract_validator()
    patch_tests()
    patch_all_notice_references()
    print("Short edition patch applied")


if __name__ == "__main__":
    main()
