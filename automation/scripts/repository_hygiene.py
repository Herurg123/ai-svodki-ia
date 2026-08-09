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
    RECENT_MERGED_TTL_DAYS,
    CLOSED_UNMERGED_TTL_DAYS,
    STALE_QUEUED_AFTER_DAYS,
    branch_history_class,
    currently_protected_recent_merges,
    classify_branch,
    classify_ci,
    classify_production,
    classify_workflow,
    has_publish_step,
    latest_pr_for_branch,
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
    now = dt.datetime.now(dt.timezone.utc)
    merged = merged_sorted(closed_main_prs)
    recent = currently_protected_recent_merges(merged, now)
    recent_numbers = {int(pr["number"]) for pr in recent}

    status_runs = [run for status in ("queued", "in_progress") for run in api.runs(status)]
    live_runs = [run for run in status_runs if live_run(run)]
    active_branches = {str(run.get("head_branch") or "") for run in live_runs if run.get("head_branch")}

    branches = api.branches()
    branch_classes = {}
    branch_items = []
    for branch in branches:
        cls, reason, related = classify_branch(
            branch,
            repository=api.repository,
            default_branch=default_branch,
            prs=all_prs,
            recent_numbers=recent_numbers,
            active_branches=active_branches,
            now=now,
        )
        name = str(branch.get("name") or "")
        branch_classes[name] = cls
        branch_items.append({
            "name": name,
            "sha": str((branch.get("commit") or {}).get("sha") or ""),
            "classification": cls,
            "reason": reason,
            "pull_request": int(related["number"]) if related else None,
        })

    history_classes = {}
    history_names = {pr_branch(pr, api.repository) for pr in all_prs}
    for name in sorted(item for item in history_names if item):
        history_classes[name] = branch_history_class(name, all_prs, api.repository, recent_numbers, now)

    workflow_entries = api.contents(".github/workflows", default_branch)
    canonical_paths = {
        str(item.get("path") or "")
        for item in workflow_entries
        if item.get("type") == "file" and str(item.get("path") or "").endswith((".yml", ".yaml"))
    }
    workflows = api.workflows()
    workflow_runs = {int(w["id"]): api.workflow_runs(int(w["id"])) for w in workflows}
    workflow_items = []
    for workflow in workflows:
        cls, reason = classify_workflow(
            workflow,
            canonical_paths,
            bool(meta.get("has_pages")),
            branch_classes,
            history_classes,
            workflow_runs[int(workflow["id"])],
            default_branch=default_branch,
        )
        workflow_items.append({
            "id": int(workflow["id"]),
            "name": str(workflow.get("name") or ""),
            "path": str(workflow.get("path") or ""),
            "state": str(workflow.get("state") or ""),
            "classification": cls,
            "reason": reason,
        })

    rss_text = api.file_text("posts/rss.xml", default_branch)
    dates = publication_dates(rss_text)
    artifacts = [artifact for artifact in api.artifacts() if not artifact.get("expired")]
    production_groups = defaultdict(list)
    for artifact in artifacts:
        match = PRODUCTION_RE.match(str(artifact.get("name") or ""))
        if match:
            production_groups[match.group(1)].append(artifact)

    production_run_ids = {
        int((artifact.get("workflow_run") or {}).get("id") or 0)
        for group in production_groups.values()
        for artifact in group
        if (artifact.get("workflow_run") or {}).get("id")
    }
    final_runs = {run_id for run_id in production_run_ids if has_publish_step(api.jobs(run_id))}
    production_classes = classify_production(production_groups, dates, final_runs)

    protected_shas = {main_sha}
    for pr in recent:
        head_sha = str((pr.get("head") or {}).get("sha") or "")
        merge_sha = str(pr.get("merge_commit_sha") or "")
        if head_sha:
            protected_shas.add(head_sha)
        if merge_sha:
            protected_shas.add(merge_sha)
    for pr in open_prs:
        head_sha = str((pr.get("head") or {}).get("sha") or "")
        if head_sha:
            protected_shas.add(head_sha)

    artifact_items = []
    for artifact in artifacts:
        artifact_id = int(artifact["id"])
        name = str(artifact.get("name") or "")
        if artifact_id in production_classes:
            cls, reason = production_classes[artifact_id]
        elif CI_RE.match(name):
            cls, reason = classify_ci(artifact, protected_shas, branch_classes, history_classes)
        else:
            cls, reason = "review_only", "unknown_artifact_type"
        artifact_items.append({
            "id": artifact_id,
            "name": name,
            "created_at": artifact.get("created_at"),
            "run_id": int((artifact.get("workflow_run") or {}).get("id") or 0) or None,
            "classification": cls,
            "reason": reason,
        })

    stale_runs = []
    workflow_classes = {item["id"]: item["classification"] for item in workflow_items}
    for workflow in workflows:
        workflow_id = int(workflow["id"])
        for run in workflow_runs[workflow_id]:
            status = str(run.get("status") or "")
            if status != "queued" or live_run(run, now):
                continue
            stale_runs.append({
                "id": int(run["id"]),
                "workflow_id": workflow_id,
                "workflow": str(workflow.get("name") or ""),
                "head_branch": str(run.get("head_branch") or ""),
                "created_at": run.get("created_at"),
                "classification": "review_only",
                "reason": "stale_orphan_run" if workflow_classes[workflow_id] == "safe_disable" else "stale_queued_run",
            })

    source_scan = scan_sources(root, merged)
    return {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "repository": api.repository,
        "default_branch": default_branch,
        "main_sha": main_sha,
        "policy": {
            "recent_merged_prs": RECENT_MERGED_PRS,
            "recent_merged_ttl_days": RECENT_MERGED_TTL_DAYS,
            "closed_unmerged_ttl_days": CLOSED_UNMERGED_TTL_DAYS,
            "keep_full_production_dates": KEEP_FULL_PRODUCTION_DATES,
            "keep_final_production_dates": KEEP_FINAL_PRODUCTION_DATES,
            "orphan_watch_merges": ORPHAN_WATCH_MERGES,
            "orphan_suspect_merges": ORPHAN_SUSPECT_MERGES,
            "stale_queued_after_days": STALE_QUEUED_AFTER_DAYS,
        },
        "recent_merged_prs": [
            {
                "number": int(pr["number"]),
                "merged_at": pr.get("merged_at"),
                "head_branch": pr_branch(pr, api.repository),
                "head_sha": str((pr.get("head") or {}).get("sha") or ""),
                "merge_sha": str(pr.get("merge_commit_sha") or ""),
            }
            for pr in recent
        ],
        "publication_dates": dates,
        "branches": sorted(branch_items, key=lambda item: item["name"]),
        "artifacts": sorted(artifact_items, key=lambda item: (item.get("created_at") or "", item["id"]), reverse=True),
        "workflows": sorted(workflow_items, key=lambda item: (item["path"], item["id"])),
        "workflow_runs": sorted(stale_runs, key=lambda item: (item.get("created_at") or "", item["id"])),
        "sources": source_scan,
    }


def compact_summary(plan):
    def counts(items):
        return dict(sorted(Counter(item["classification"] for item in items).items()))
    return {
        "main_sha": plan["main_sha"],
        "recent_merged_prs": [item["number"] for item in plan["recent_merged_prs"]],
        "publication_dates": plan["publication_dates"][:KEEP_FINAL_PRODUCTION_DATES],
        "branches": counts(plan["branches"]),
        "artifacts": counts(plan["artifacts"]),
        "workflows": counts(plan["workflows"]),
        "workflow_runs": counts(plan["workflow_runs"]),
        "source_watchlist": len(plan["sources"]["watchlist"]),
        "suspected_orphans": len(plan["sources"]["suspected_orphans"]),
    }


def safe_main(api, expected_sha):
    current = api.branch("main")
    current_sha = str(((current or {}).get("commit") or {}).get("sha") or "")
    if current_sha != expected_sha:
        raise RuntimeError(f"main changed after hygiene plan: {expected_sha} -> {current_sha}")


def apply_branches(api, root, plan):
    safe_main(api, plan["main_sha"])
    recent_numbers = {int(item["number"]) for item in plan["recent_merged_prs"]}
    deleted = []
    skipped = []
    for item in plan["branches"]:
        if item["classification"] != "safe_delete":
            continue
        safe_main(api, plan["main_sha"])
        branch = api.branch(item["name"])
        if not branch:
            skipped.append({"name": item["name"], "reason": "already_missing"})
            continue
        open_prs = api.prs("open")
        closed = api.prs("closed", base="main")
        prs = open_prs + closed
        active = {
            str(run.get("head_branch") or "")
            for status in ("queued", "in_progress")
            for run in api.runs(status)
            if live_run(run) and run.get("head_branch")
        }
        cls, reason, related = classify_branch(
            branch,
            repository=api.repository,
            default_branch="main",
            prs=prs,
            recent_numbers=recent_numbers,
            active_branches=active,
            now=dt.datetime.now(dt.timezone.utc),
        )
        current_sha = str((branch.get("commit") or {}).get("sha") or "")
        expected_sha = str(item["sha"])
        if cls != "safe_delete" or current_sha != expected_sha:
            skipped.append({"name": item["name"], "reason": reason if cls != "safe_delete" else "head_changed"})
            continue
        if related and str((related.get("head") or {}).get("sha") or "") != current_sha:
            skipped.append({"name": item["name"], "reason": "pull_request_head_changed"})
            continue
        api.delete_branch(item["name"])
        deleted.append(item["name"])
    return {"deleted": deleted, "skipped": skipped}


def _artifact(api, artifact_id):
    status, data = api.request("GET", f"/repos/{api.repository}/actions/artifacts/{artifact_id}", (200, 404))
    return data if status == 200 else None


def _workflow(api, workflow_id):
    status, data = api.request("GET", f"/repos/{api.repository}/actions/workflows/{workflow_id}", (200, 404))
    return data if status == 200 else None


def production_workflow_id(api):
    for workflow in api.workflows():
        if str(workflow.get("path") or "") == ".github/workflows/daily-production.yml":
            return int(workflow["id"])
    return None


def production_active(api, workflow_id=None):
    workflow_id = workflow_id if workflow_id is not None else production_workflow_id(api)
    if workflow_id is None:
        return False
    return any(live_run(run) for run in api.workflow_runs(workflow_id, limit=20))


def current_ci_protected_shas(api, plan):
    protected = {str(plan["main_sha"])}
    for item in plan["recent_merged_prs"]:
        if item.get("head_sha"):
            protected.add(str(item["head_sha"]))
        if item.get("merge_sha"):
            protected.add(str(item["merge_sha"]))
    for pr in api.prs("open"):
        head_sha = str((pr.get("head") or {}).get("sha") or "")
        if head_sha:
            protected.add(head_sha)
    return protected


def apply_actions(api, root, plan):
    safe_main(api, plan["main_sha"])
    production_id = production_workflow_id(api)
    if production_active(api, production_id):
        return {"skipped": "active_production_run", "artifacts_deleted": [], "workflows_disabled": []}

    # Rebuild once at the start of the destructive phase. Individual objects,
    # main and production activity are then rechecked without rebuilding the
    # whole repository graph before every artifact deletion.
    fresh = build_plan(api, root)
    safe_main(api, plan["main_sha"])
    deleted = []
    skipped = []
    for item in fresh["artifacts"]:
        if item["classification"] != "safe_delete":
            continue
        safe_main(api, plan["main_sha"])
        if production_active(api, production_id):
            return {
                "skipped": "production_started_during_actions_cleanup",
                "artifacts_deleted": deleted,
                "artifact_skipped": skipped,
                "workflows_disabled": [],
            }
        artifact = _artifact(api, item["id"])
        if not artifact or artifact.get("expired"):
            skipped.append({"id": item["id"], "reason": "already_missing_or_expired"})
            continue
        if str(artifact.get("name") or "") != str(item["name"]):
            skipped.append({"id": item["id"], "reason": "artifact_identity_changed"})
            continue
        ci_match = CI_RE.match(str(item["name"]))
        if ci_match and ci_match.group(1) in current_ci_protected_shas(api, fresh):
            skipped.append({"id": item["id"], "reason": "ci_sha_became_protected"})
            continue
        api.delete_artifact(item["id"])
        deleted.append(item["id"])

    disabled = []
    workflow_skipped = []
    fresh = build_plan(api, root)
    safe_main(api, plan["main_sha"])
    for item in fresh["workflows"]:
        if item["classification"] != "safe_disable":
            continue
        safe_main(api, plan["main_sha"])
        if production_active(api, production_id):
            return {
                "skipped": "production_started_during_actions_cleanup",
                "artifacts_deleted": deleted,
                "artifact_skipped": skipped,
                "workflows_disabled": disabled,
                "workflow_skipped": workflow_skipped,
            }
        workflow = _workflow(api, item["id"])
        if not workflow or workflow.get("state") != "active":
            workflow_skipped.append({"id": item["id"], "reason": "already_missing_or_disabled"})
            continue
        runs = api.workflow_runs(item["id"])
        if any(live_run(run) for run in runs):
            workflow_skipped.append({"id": item["id"], "reason": "workflow_has_active_run"})
            continue
        path = str(workflow.get("path") or "")
        if path.startswith("dynamic/pages/") and bool(api.repo().get("has_pages")):
            workflow_skipped.append({"id": item["id"], "reason": "github_pages_enabled"})
            continue
        if runs:
            latest = max(runs, key=lambda run: run.get("created_at") or "")
            latest_branch = str(latest.get("head_branch") or "")
            if latest_branch and any(pr_branch(pr, api.repository) == latest_branch for pr in api.prs("open")):
                workflow_skipped.append({"id": item["id"], "reason": "workflow_branch_has_open_pr"})
                continue
        api.disable_workflow(item["id"])
        disabled.append(item["id"])

    return {
        "artifacts_deleted": deleted,
        "artifact_skipped": skipped,
        "workflows_disabled": disabled,
        "workflow_skipped": workflow_skipped,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "apply"), default="plan")
    parser.add_argument("--scope", choices=("all", "branches", "actions"), default="all")
    parser.add_argument("--report", type=Path, default=Path("automation/preview/repository-hygiene.json"))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    if not token or not repository:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY are required")
    root = Path(__file__).resolve().parents[2]
    api = GitHub(repository, token, api_url)
    plan = build_plan(api, root)
    result = {"plan": plan, "summary": compact_summary(plan)}

    if args.mode == "apply":
        if args.scope in {"all", "branches"}:
            result["branch_apply"] = apply_branches(api, root, plan)
        if args.scope in {"all", "actions"}:
            result["actions_apply"] = apply_actions(api, root, plan)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
