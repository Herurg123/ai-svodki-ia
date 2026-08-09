from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def _counts(items: list[dict]) -> Counter:
    return Counter(str(item.get("classification") or "unknown") for item in items)


def _cell(counts: Counter, key: str) -> str:
    return str(int(counts.get(key, 0)))


def _details(title: str, lines: list[str]) -> list[str]:
    if not lines:
        return []
    return [
        "",
        "<details>",
        f"<summary>{title}</summary>",
        "",
        *[f"- {line}" for line in lines],
        "",
        "</details>",
    ]


def render_report(report: dict) -> str:
    plan = dict(report.get("plan") or {})
    summary = dict(report.get("summary") or {})
    branch_apply = report.get("branch_apply")
    actions_apply = report.get("actions_apply")

    if branch_apply is not None:
        title = "Repository hygiene: очистка веток"
    elif actions_apply is not None:
        title = "Repository hygiene: очистка Actions"
    else:
        title = "Repository hygiene: аудит"

    lines = [
        f"## {title}",
        "",
        "**Статус:** ✅ проверка завершена",
        f"**main:** `{str(summary.get('main_sha') or plan.get('main_sha') or '')[:12]}`",
    ]

    recent = summary.get("recent_merged_prs") or []
    if recent:
        lines.append("**Защитное окно merged PR:** " + ", ".join(f"#{number}" for number in recent))

    branch_counts = _counts(list(plan.get("branches") or []))
    visible_artifacts = [
        item
        for item in plan.get("artifacts") or []
        if not str(item.get("name") or "").startswith("repository-hygiene-")
    ]
    artifact_counts = _counts(visible_artifacts)
    workflow_counts = _counts(list(plan.get("workflows") or []))
    run_counts = _counts(list(plan.get("workflow_runs") or []))

    lines.extend(
        [
            "",
            "### Состояние репозитория",
            "",
            "| Объект | Защищено | Можно убрать | Требует внимания |",
            "|---|---:|---:|---:|",
            f"| Ветки | {_cell(branch_counts, 'protected')} | {_cell(branch_counts, 'safe_delete')} | {_cell(branch_counts, 'review_only')} |",
            f"| Actions artifacts | {_cell(artifact_counts, 'protected')} | {_cell(artifact_counts, 'safe_delete')} | {_cell(artifact_counts, 'review_only')} |",
            f"| Actions workflows | {_cell(workflow_counts, 'protected')} | {_cell(workflow_counts, 'safe_disable')} | {_cell(workflow_counts, 'review_only')} |",
            f"| Старые workflow runs | {_cell(run_counts, 'protected')} | {_cell(run_counts, 'safe_delete')} | {_cell(run_counts, 'review_only')} |",
            "",
            f"**Source watchlist:** {int(summary.get('source_watchlist') or 0)}  ",
            f"**Suspected orphan files:** {int(summary.get('suspected_orphans') or 0)}",
        ]
    )

    if branch_apply is not None:
        branch_apply = dict(branch_apply or {})
        deleted = list(branch_apply.get("deleted") or [])
        skipped = list(branch_apply.get("skipped") or [])
        lines.extend(
            [
                "",
                "### Что сделано с ветками",
                "",
                f"- Удалено доказанно устаревших merged-веток: **{len(deleted)}**",
                f"- Пропущено после повторной проверки: **{len(skipped)}**",
            ]
        )
        lines.extend(_details("Удалённые ветки", [f"`{name}`" for name in deleted]))
        lines.extend(
            _details(
                "Пропущенные ветки",
                [f"`{item.get('name')}`: {item.get('reason')}" for item in skipped],
            )
        )

    if actions_apply is not None:
        actions_apply = dict(actions_apply or {})
        deleted_ids = [int(value) for value in actions_apply.get("artifacts_deleted") or []]
        disabled_ids = [int(value) for value in actions_apply.get("workflows_disabled") or []]
        artifact_skipped = list(actions_apply.get("artifact_skipped") or [])
        workflow_skipped = list(actions_apply.get("workflow_skipped") or [])
        run_deleted_ids = [int(value) for value in actions_apply.get("workflow_runs_deleted") or []]
        run_skipped = list(actions_apply.get("workflow_run_skipped") or [])
        artifact_names = {
            int(item["id"]): str(item.get("name") or item["id"])
            for item in plan.get("artifacts") or []
            if item.get("id") is not None
        }
        workflow_names = {
            int(item["id"]): str(item.get("name") or item.get("path") or item["id"])
            for item in plan.get("workflows") or []
            if item.get("id") is not None
        }

        lines.extend(
            [
                "",
                "### Что сделано в Actions",
                "",
                f"- Удалено superseded artifacts: **{len(deleted_ids)}**",
                f"- Отключено orphaned workflows: **{len(disabled_ids)}**",
                f"- Удалено просроченных runs доказанных orphan-workflows: **{len(run_deleted_ids)}**",
                f"- Пропущено artifacts после повторной проверки: **{len(artifact_skipped)}**",
                f"- Пропущено workflows после повторной проверки: **{len(workflow_skipped)}**",
                f"- Пропущено workflow runs после повторной проверки: **{len(run_skipped)}**",
            ]
        )
        if actions_apply.get("skipped"):
            lines.append(f"- Actions-уборка остановлена безопасно: `{actions_apply['skipped']}`")
        lines.extend(
            _details(
                "Удалённые artifacts",
                [f"`{artifact_names.get(item_id, item_id)}` (id {item_id})" for item_id in deleted_ids],
            )
        )
        lines.extend(
            _details(
                "Отключённые workflows",
                [f"`{workflow_names.get(item_id, item_id)}` (id {item_id})" for item_id in disabled_ids],
            )
        )
        lines.extend(
            _details(
                "Удалённые orphan workflow runs",
                [f"run id {item_id}" for item_id in run_deleted_ids],
            )
        )

    lines.extend(
        [
            "",
            "### Гарантированно не трогается",
            "",
            "`posts/**`, `automation/content/**`, releases, tags, текущий `main`, открытые PR и tracked source/config/docs.",
            "",
            "> Полный JSON этого этапа приложен к запуску как краткоживущий Actions artifact (retention: 2 дня).",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    markdown = render_report(report)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("a", encoding="utf-8") as handle:
        handle.write(markdown)


if __name__ == "__main__":
    main()
