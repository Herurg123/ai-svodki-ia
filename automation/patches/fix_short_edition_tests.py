#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD_NOTICE = "День на новости выдался слабым - поэтому коротко"
NEW_NOTICE = "Новостей сегодня меньше, чем обычно"
OLD_HTML = f"<p>{OLD_NOTICE}</p>"
NEW_HTML = f"<p><em>{NEW_NOTICE}</em></p>"
OLD_STEP = "Enforce 5 world plus 2 Russian stories"
NEW_STEP = "Complete coverage and allow short edition after audit"


def patch(path: str, replacements: list[tuple[str, str]]) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    for old, new in replacements:
        text = text.replace(old, new)
    target.write_text(text, encoding="utf-8")


def main() -> None:
    patch(
        "automation/scripts/ensure_story_coverage.py",
        [
            (
                '    digest_path = artifact_dir / "digest.json"\n    meta_path = artifact_dir / "meta.json"',
                '    digest_path = artifact_dir / "digest.json"\n    if not digest_path.is_file():\n        return\n    meta_path = artifact_dir / "meta.json"',
            ),
        ],
    )

    patch(
        "automation/scripts/validate_production_daily_contract.py",
        [(OLD_STEP, NEW_STEP)],
    )
    patch(
        "automation/tests/test_resilient_partial_recovery.py",
        [(OLD_STEP, NEW_STEP)],
    )
    patch(
        "automation/tests/test_story_coverage.py",
        [
            ('editorial["story_counts"]["total_target_minimum"], 6', 'editorial["story_counts"]["total_target_minimum"], 7'),
            (OLD_STEP, NEW_STEP),
        ],
    )
    patch(
        "automation/tests/test_editorial_policy.py",
        [
            (OLD_HTML, NEW_HTML),
            (OLD_NOTICE, NEW_NOTICE),
            ('candidates = [candidate(str(index)) for index in range(6)]', 'candidates = [candidate(str(index)) for index in range(7)]'),
            ('base_article([f"Сюжет {index}" for index in range(6)])', 'base_article([f"Сюжет {index}" for index in range(7)])'),
        ],
    )
    patch(
        "automation/scripts/validate_editorial_scenarios.py",
        [
            ('selected = [candidate(index) for index in range(1, 7)]', 'selected = [candidate(index) for index in range(1, 8)]'),
            ('Шесть сюжетов не должны считаться коротким выпуском.', 'Семь сюжетов не должны считаться коротким выпуском.'),
            ('normalized.startswith(f"<p>{notice}</p>")', 'normalized.startswith(str(policy["story_counts"].get("short_digest_notice_html")))'),
            ('return ["6 сюжетов", "short_digest=false", "4 вывода", "политика без ошибок"]', 'return ["7 сюжетов", "short_digest=false", "4 вывода", "политика без ошибок"]'),
            ('require(normalized.startswith(f"<p>{notice}</p>"), "Нет точной short notice.")', 'require(normalized.startswith(str(policy["story_counts"].get("short_digest_notice_html"))), "Нет точной short notice.")'),
        ],
    )

    tests_root = ROOT / "automation" / "tests"
    for target in tests_root.rglob("*.py"):
        text = target.read_text(encoding="utf-8")
        text = text.replace(OLD_HTML, NEW_HTML)
        text = text.replace(OLD_NOTICE, NEW_NOTICE)
        text = text.replace(OLD_STEP, NEW_STEP)
        target.write_text(text, encoding="utf-8")

    print("Follow-up short edition fixes applied")


if __name__ == "__main__":
    main()
