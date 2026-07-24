from __future__ import annotations

import argparse
import json
from pathlib import Path

from story_coverage import coverage_summary, read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверить обязательный состав итоговой ИИ-сводки."
    )
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--minimum-total", type=int, default=7)
    parser.add_argument("--minimum-world", type=int, default=5)
    parser.add_argument("--minimum-russia", type=int, default=2)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    stories_path = args.artifact_dir / "stories.json"
    stories = read_json(stories_path)
    if not isinstance(stories, list):
        report = {
            "status": "error",
            "errors": ["stories.json должен содержать массив"],
        }
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
    if not report["valid"]:
        report["errors"] = [
            "Итоговый выпуск не выполняет обязательный минимум: "
            f"всего {report['counts']['total']}/{args.minimum_total}, "
            f"мировых {report['counts']['world']}/{args.minimum_world}, "
            f"российских {report['counts']['russia']}/{args.minimum_russia}."
        ]
        report["status"] = "error"
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
