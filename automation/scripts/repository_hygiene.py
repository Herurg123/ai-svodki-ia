from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from repository_hygiene_github import ApiError, GitHub
from repository_hygiene_policy import (
    CI_RE,
    KEEP_FINAL_PRODUCTION_DATES,
    KEEP_FULL_PRODUCTION_DATES,
    ORPHAN_SUSPECT_MERGES,
    ORPHAN_WATCH_MERGES,
    PRODUCTION_RE,
    RECENT_MERGED_PRS,
    STALE_QUEUED_AFTER_DAYS,
    branch_history_class,
    classify_branch,
    classify_ci,
    classify_production,
    classify_workflow,
    has_publish_step,
    live_run,
    merged_sorted,
    pr_branch,
    publication_dates,
    scan_sources,
)


def build_plan(api: GitHub, root: Path):
    meta = api.repo()
    default_branch = str(meta.get("default_branch") or "main")
    default = api.branch(default_branch)
    if not default:
        raise RuntimeError("default branch is missing")
    main_sha = str((default.get("commit") or {}).get("sha") or "")

    open_prs = api.prs("open")
    closed_main_prs = api.prs("closed", base=default_branch)
    all_prs = open_prs + closed_main_prs
    merged = merged_sorted(closed_main_prs)
    recent = merged[:RECENT_MERGED_PRS]
    recent_numbers = {int(pr["number"]) for pr in recent}

    status_runs = [run for status in ("queued", "in_progress") for run in api.runs(status)]
    active_runs = [run for run in status_runs if live_run(run)]
    active_branches = {str(run.get("head_branch")) for run in active_runs if run.get("head_branch")}

    historical_names = {name for pr in all_prs if (name := pr_branch(pr, api.repository))}
    history_classes = {
        name: branch_history_class(name, all_prs, api.repository, recent_numbers)
        for name in historical_names
    }
    branch_records = []
    branch_classes = {}
    for branch in api.branches():
        classification, reason, pr = classify_branch(
            branch,
            repository=api.repository,
            default_branch=default_branch,
            prs=all_prs,
            recent_numbers=recent_numbers,
            active_branches=active_branches,
        )
        name = str(branch.get("name") or "")
        branch_classes[name] = classification
        branch_records.append({
            "name": name,
            "sha": (branch.get("commit") or {}).get("sha"),
            "classification": classification,
            "reason": reason,
            "pull_request": int(pr["number"]) if pr else None,
        })

    canonical_paths = {
        str(item.get("path"))
        for item in api.contents(".github/workflows", default_branch)
        if item.get("type") == "file"
    }
    workflow_records = []
    for workflow in api.workflows():
        runs = api.workflow_runs(int(workflow["id"]))
        classification, reason = classify_workflow(
            workflow, canonical_paths, bool(meta.get("has_pages")),
            branch_classes, history_classes, runs,
        )
        latest = max(runs, key=lambda run: run.get("created_at") or "") if runs else None
        workflow_records.append({
            "id": int(workflow["id"]),
            "name": workflow.get("name"),
            "path": workflow.get("path"),
            "state": workflow.get("state"),
            "classification": classification,
            "reason": reason,
            "latest_run_branch": (latest or {}).get("head_branch"),
        })

    dates = publication_dates(api.file_text("posts/rss.xml", default_branch))
    artifacts = [artifact for artifact in api.artifacts() if not artifact.get("expired")]
    groups = defaultdict(list)
    for artifact in artifacts:
        match = PRODUCTION_RE.match(str(artifact.get("name") or ""))
        if match:
            groups[match.group(1)].append(artifact)

    final_runs = set()
    positions = {date: index for index, date in enumerate(dates)}
    for date, group in groups.items():
        position = positions.get(date)
        if position is None or not (KEEP_FULL_PRODUCTION_DATES <= position < KEEP_FINAL_PRODUCTION_DATES):
            continue
        for artifact in group:
            run_id = int((artifact.get("workflow_run") or {}).get("id") or -1)
            if run_id >= 0 and run_id not in final_runs and has_publish_step(api.jobs(run_id)):
                final_runs.add(run_id)
    production_classes = classify_production(groups, dates, final_runs)

    protected_shas = {main_sha}
    for pr in recent:
        head_sha = (pr.get("head") or {}).get("sha")
        if head_sha:
            protected_shas.add(str(head_sha))
        if pr.get("merge_commit_sha"):
            protected_shas.add(str(pr["merge_commit_sha"]))
    for pr in open_prs:
        head_sha = (pr.get("head") or {}).get("sha")
        if head_sha:
            protected_shas.add(str(head_sha))

    artifact_records = []
    for artifact in artifacts:
        artifact_id = int(artifact["id"])
        name = str(artifact.get("name") or "")
        if artifact_id in production_classes:
            classification, reason = production_classes[artifact_id]
        elif CI_RE.match(name):
            classification, reason = classify_ci(artifact, protected_shas, branch_classes, history_classes)
        else:
            classification, reason = "review_only", "unknown_artifact_type"
        run = artifact.get("workflow_run") or {}
        artifact_records.append({
            "id": artifact_id,
            "name": name,
            "size_in_bytes": int(artifact.get("size_in_bytes") or 0),
            "created_at": artifact.get("created_at"),
            "expires_at": artifact.get("expires_at"),
            "run_id": run.get("id"),
            "head_branch": run.get("head_branch"),
            "head_sha": run.get("head_sha"),
            "classification": classification,
            "reason": reason,
        })

    workflows_by_id = {item["id"]: item for item in workflow_records}
    stale_runs = []
    for run in (item for item in status_runs if item.get("status") == "queued" and not live_run(item)):
        workflow = workflows_by_id.get(int(run.get("workflow_id") or -1))
        if workflow and workflow["classification"] == "safe_disable":
            stale_runs.append({
                "id": run.get("id"),
                "name": run.get("name"),
                "created_at": run.get("created_at"),
                "classification": "review_only",
                "reason": "queued_run_of_orphan_workflow",
            })

    active_production = [
        {"id": run.get("id"), "status": run.get("status"), "name": run.get("name")}
        for run in active_runs
        if run.get("path") == ".github/workflows/daily-production.yml"
    ]
    return {
        "version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository": api.repository,
        "default_branch": default_branch,
        "main_sha": main_sha,
        "policy": {
            "recent_merged_pr_window": RECENT_MERGED_PRS,
            "recent_publication_full_chain": KEEP_FULL_PRODUCTION_DATES,
            "recent_publication_keep_final": KEEP_FINAL_PRODUCTION_DATES,
            "orphan_watch_merges": ORPHAN_WATCH_MERGES,
            "orphan_suspect_merges": ORPHAN_SUSPECT_MERGES,
            "stale_queued_after_days": STALE_QUEUED_AFTER_DAYS,
        },
        "recent_merged_prs": [
            {"number": pr.get("number"), "merged_at": pr.get("merged_at"), "head": (pr.get("head") or {}).get("ref")}
            for pr in recent
        ],
        "publication_dates": dates,
        "active_production_runs": active_production,
        "branches": sorted(branch_records, key=lambda item: item["name"]),
        "workflows": sorted(workflow_records, key=lambda item: (str(item["path"]), item["id"])),
        "artifacts": sorted(artifact_records, key=lambda item: item["id"], reverse=True),
        "workflow_runs_review_only": stale_runs,
        "source_scan": scan_sources(root, merged),
    }


def revalidate_main(api: GitHub, plan):
    current = api.branch(plan["default_branch"])
    current_sha = str(((current or {}).get("commit") or {}).get("sha") or "")
    if current_sha != plan["main_sha"]:
        raise RuntimeError(f"main changed during hygiene: {plan['main_sha']} -> {current_sha}")


def apply_branches(api: GitHub, root: Path):
    plan = build_plan(api, root)
    revalidate_main(api, plan)
    actions = []
    for item in (record for record in plan["branches"] if record["classification"] == "safe_delete"):
        name = item["name"]
        branch = api.branch(name)
        if not branch:
            actions.append(f"skip branch `{name}`: already absent")
            continue
        if any(pr_branch(pr, api.repository) == name for pr in api.prs("open")):
            actions.append(f"skip branch `{name}`: open PR appeared")
            continue
        active = {
            str(run.get("head_branch"))
            for status in ("queued", "in_progress")
            for run in api.runs(status)
            if live_run(run)
        }
        if name in active:
            actions.append(f"skip branch `{name}`: Actions run is active")
            continue
        if (branch.get("commit") or {}).get("sha") != item["sha"]:
            actions.append(f"skip branch `{name}`: head changed")
            continue
        revalidate_main(api, plan)
        api.delete_branch(name)
        actions.append(f"deleted merged branch `{name}`")
    return plan, actions


def apply_actions(api: GitHub, root: Path):
    plan = build_plan(api, root)
    revalidate_main(api, plan)
    if plan["active_production_runs"]:
        return plan, ["skipped Actions cleanup: production run is active"]
    actions = []
    for item in (record for record in plan["artifacts"] if record["classification"] == "safe_delete"):
        revalidate_main(api, plan)
        status, artifact = api.request(
            "GET", f"/repos/{api.repository}/actions/artifacts/{item['id']}", (200, 404)
        )
        if status == 404:
            actions.append(f"skip artifact `{item['id']}`: already absent")
            continue
        branch = str(((artifact or {}).get("workflow_run") or {}).get("head_branch") or "")
        if branch and any(pr_branch(pr, api.repository) == branch for pr in api.prs("open")):
            actions.append(f"skip artifact `{item['id']}`: branch gained an open PR")
            continue
        api.delete_artifact(item["id"])
        actions.append(f"deleted artifact `{item['name']}` ({item['id']})")

    fresh = build_plan(api, root)
    revalidate_main(api, plan)
    for item in (record for record in fresh["workflows"] if record["classification"] == "safe_disable"):
        status, workflow = api.request(
            "GET", f"/repos/{api.repository}/actions/workflows/{item['id']}", (200, 404)
        )
        if status == 404 or (workflow or {}).get("state") != "active":
            actions.append(f"skip workflow `{item['id']}`: absent or already disabled")
            continue
        api.disable_workflow(item["id"])
        actions.append(f"disabled orphan workflow `{item['name']}` ({item['id']})")
    return fresh, actions


def render_summary(plan, mode, actions=None):
    branches = Counter(item["classification"] for item in plan["branches"])
    workflows = Counter(item["classification"] for item in plan["workflows"])
    artifacts = Counter(item["classification"] for item in plan["artifacts"])
    reclaim = sum(item["size_in_bytes"] for item in plan["artifacts"] if item["classification"] == "safe_delete")
    lines = [
        "# Repository hygiene",
        "",
        f"Режим: **{mode}**",
        f"Снимок `main`: `{plan['main_sha']}`",
        f"Окно веток: последние **{RECENT_MERGED_PRS}** merged PR по `merged_at`.",
        "",
        f"- Ветки: `{dict(branches)}`",
        f"- Workflows: `{dict(workflows)}`",
        f"- Artifacts: `{dict(artifacts)}`",
        f"- Потенциально освобождаемый объём artifacts: **{reclaim / 1024 / 1024:.1f} MiB**.",
        f"- Source watchlist: **{len(plan['source_scan']['watchlist'])}**.",
        f"- Suspected orphan files, report-only: **{len(plan['source_scan']['suspected_orphans'])}**.",
        f"- Stale workflow runs, report-only: **{len(plan['workflow_runs_review_only'])}**.",
    ]
    if plan["active_production_runs"]:
        lines += ["", "**Actions cleanup blocked: production run is active.**"]
    if actions is not None:
        lines += ["", "## Выполненные действия", ""]
        lines += [f"- {action}" for action in actions] or ["- Изменений нет."]
    return "\n".join(lines) + "\n"


def write_results(plan, output: Path | None, summary_path: Path | None, mode: str, actions=None):
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text = render_summary(plan, mode, actions)
    if summary_path:
        with summary_path.open("a", encoding="utf-8") as stream:
            stream.write(text)
    else:
        print(text, end="")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "apply"), default="plan")
    parser.add_argument("--scope", choices=("branches", "actions"), default="branches")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not args.repository or not token:
        parser.error("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
    api = GitHub(args.repository, token, args.api_url)
    try:
        if args.mode == "plan":
            plan = build_plan(api, Path.cwd())
            write_results(plan, args.output, args.summary, "plan")
        elif args.scope == "branches":
            plan, actions = apply_branches(api, Path.cwd())
            write_results(plan, args.output, args.summary, "apply/branches", actions)
        else:
            plan, actions = apply_actions(api, Path.cwd())
            write_results(plan, args.output, args.summary, "apply/actions", actions)
        return 0
    except (ApiError, RuntimeError) as exc:
        print(f"repository hygiene failed safely: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
