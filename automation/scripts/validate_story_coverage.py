from __future__ import annotations

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
    audit_path = args.audit_report or Path("automation/preview/production-daily/coverage-audit.json")
    if audit_path.is_file():
        audit = read_json(audit_path)
    short_allowed = (
        len(stories) > 0
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
