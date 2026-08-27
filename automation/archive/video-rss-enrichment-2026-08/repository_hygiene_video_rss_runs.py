from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import Counter
from pathlib import Path

from repository_hygiene_github import ApiError, GitHub
from repository_hygiene_policy import live_run

VIDEO_RSS_WORKFLOW_PATH = ".github/workflows/video-rss-enrichment.yml"
DAILY_PRODUCTION_WORKFLOW_PATH = ".github/workflows/daily-production.yml"
SUCCESS_RETENTION_DAYS = 3
DIAGNOSTIC_RETENTION_DAYS = 14
KEEP_LATEST_SUCCESS_RUNS = 14


def iso(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def run_activity_at(run):
    candidates = [iso(run.get("created_at")), iso(run.get("updated_at"))]
    candidates = [value for value in candidates if value is not None]
    return max(candidates) if candidates else None


def _run_sort_key(run):
    floor = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return (iso(run.get("created_at")) or floor, int(run.get("id") or 0))


def classify_video_rss_runs(runs, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    successes = sorted(
        (
            run
            for run in runs
            if str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
        ),
        key=_run_sort_key,
        reverse=True,
    )
    success_floor = {
        int(run["id"])
        for run in successes[:KEEP_LATEST_SUCCESS_RUNS]
        if run.get("id") is not None
    }
    success_cutoff = now - dt.timedelta(days=SUCCESS_RETENTION_DAYS)
    diagnostic_cutoff = now - dt.timedelta(days=DIAGNOSTIC_RETENTION_DAYS)
    result = {}
    for run in runs:
        run_id = int(run["id"])
        status = str(run.get("status") or "")
        conclusion = str(run.get("conclusion") or "")
        activity_at = run_activity_at(run)
        if status != "completed":
            result[run_id] = ("protected", "video_rss_run_not_completed")
            continue
        if activity_at is None:
            result[run_id] = ("review_only", "video_rss_run_missing_timestamp")
            continue
        if conclusion == "success":
            if run_id in success_floor:
                result[run_id] = ("protected", "video_rss_success_floor")
            elif activity_at > success_cutoff:
                result[run_id] = ("protected", "recent_video_rss_success")
            else:
                result[run_id] = ("safe_delete", "expired_video_rss_success")
            continue
        if conclusion in {"failure", "cancelled"}:
            if activity_at > diagnostic_cutoff:
                result[run_id] = ("protected", "recent_video_rss_diagnostic")
            else:
                result[run_id] = ("safe_delete", "expired_video_rss_diagnostic")
            continue
        result[run_id] = ("review_only", "unhandled_video_rss_conclusion")
    return result


def workflow_by_path(api: GitHub, path: str):
    matches = [workflow for workflow in api.workflows() if str(workflow.get("path") or "") == path]
    if len(matches) > 1:
        raise RuntimeError(f"multiple workflows found for canonical path: {path}")
    return matches[0] if matches else None


def workflow_runs_all(api: GitHub, workflow_id: int):
    result = []
    page = 1
    while True:
        data = api.request(
            "GET",
            f"/repos/{api.repository}/actions/workflows/{workflow_id}/runs?per_page=100&page={page}",
        )[1]
        batch = list(data.get("workflow_runs", []))
        result.extend(batch)
        if len(batch) < 100:
            return result
        page += 1


def exact_run(api: GitHub, run_id: int):
    status, data = api.request(
        "GET",
        f"/repos/{api.repository}/actions/runs/{run_id}",
        (200, 404),
    )
    return data if status == 200 else None


def safe_main(api: GitHub, expected_sha: str):
    current = api.branch("main")
    current_sha = str(((current or {}).get("commit") or {}).get("sha") or "")
    if current_sha != expected_sha:
        raise RuntimeError(f"main changed after video RSS hygiene plan: {expected_sha} -> {current_sha}")


def production_active(api: GitHub):
    workflow = workflow_by_path(api, DAILY_PRODUCTION_WORKFLOW_PATH)
    if workflow is None:
        return False
    workflow_id = int(workflow["id"])
    for status in ("queued", "in_progress"):
        for run in api.runs(status):
            if int(run.get("workflow_id") or 0) == workflow_id and live_run(run):
                return True
    return False


def _run_record(run, classification, reason):
    return {
        "id": int(run["id"]),
        "status": str(run.get("status") or ""),
        "conclusion": str(run.get("conclusion") or ""),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "classification": classification,
        "reason": reason,
    }


def build_plan(api: GitHub, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    main = api.branch("main")
    if not main:
        raise RuntimeError("default branch is missing")
    main_sha = str((main.get("commit") or {}).get("sha") or "")
    workflow = workflow_by_path(api, VIDEO_RSS_WORKFLOW_PATH)
    if workflow is None:
        runs = []
        workflow_record = None
        state = "canonical_workflow_missing_noop"
    else:
        workflow_id = int(workflow["id"])
        runs = workflow_runs_all(api, workflow_id)
        workflow_record = {
            "id": workflow_id,
            "name": str(workflow.get("name") or ""),
            "path": str(workflow.get("path") or ""),
            "state": str(workflow.get("state") or ""),
        }
        state = "ready"
    classes = classify_video_rss_runs(runs, now)
    items = [
        _run_record(run, *classes[int(run["id"])])
        for run in sorted(runs, key=_run_sort_key, reverse=True)
    ]
    counts = dict(sorted(Counter(item["classification"] for item in items).items()))
    return {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "repository": api.repository,
        "main_sha": main_sha,
        "state": state,
        "workflow": workflow_record,
        "policy": {
            "success_retention_days": SUCCESS_RETENTION_DAYS,
            "diagnostic_retention_days": DIAGNOSTIC_RETENTION_DAYS,
            "keep_latest_success_runs": KEEP_LATEST_SUCCESS_RUNS,
        },
        "runs": items,
        "summary": {
            "total": len(items),
            "protected": counts.get("protected", 0),
            "safe_delete": counts.get("safe_delete", 0),
            "review_only": counts.get("review_only", 0),
        },
    }


def _same_run_identity(current, planned):
    return (
        str(current.get("status") or "") == str(planned.get("status") or "")
        and str(current.get("conclusion") or "") == str(planned.get("conclusion") or "")
        and current.get("created_at") == planned.get("created_at")
        and current.get("updated_at") == planned.get("updated_at")
    )


def apply_plan(api: GitHub, plan):
    expected_sha = str(plan["main_sha"])
    safe_main(api, expected_sha)
    if plan.get("workflow") is None:
        return {"skipped": "canonical_workflow_missing", "deleted": [], "run_skipped": []}
    if production_active(api):
        return {"skipped": "active_production_run", "deleted": [], "run_skipped": []}

    workflow = workflow_by_path(api, VIDEO_RSS_WORKFLOW_PATH)
    planned_workflow = dict(plan.get("workflow") or {})
    if workflow is None or int(workflow.get("id") or 0) != int(planned_workflow.get("id") or 0):
        return {"skipped": "video_rss_workflow_identity_changed", "deleted": [], "run_skipped": []}

    workflow_id = int(workflow["id"])
    fresh_runs = workflow_runs_all(api, workflow_id)
    if any(live_run(run) for run in fresh_runs):
        return {"skipped": "active_video_rss_run", "deleted": [], "run_skipped": []}
    fresh_classes = classify_video_rss_runs(fresh_runs)
    fresh_by_id = {int(run["id"]): run for run in fresh_runs}
    candidates = [
        run
        for run in fresh_runs
        if fresh_classes.get(int(run["id"]), (None, None))[0] == "safe_delete"
    ]
    candidates.sort(key=_run_sort_key)

    deleted = []
    skipped = []
    for run in candidates:
        safe_main(api, expected_sha)
        run_id = int(run["id"])
        current = exact_run(api, run_id)
        if current is None:
            skipped.append({"id": run_id, "reason": "already_missing"})
            continue
        if int(current.get("workflow_id") or 0) != workflow_id:
            skipped.append({"id": run_id, "reason": "workflow_identity_changed"})
            continue
        planned_current = fresh_by_id[run_id]
        if not _same_run_identity(current, planned_current):
            skipped.append({"id": run_id, "reason": "run_identity_changed"})
            continue
        classification, reason = fresh_classes[run_id]
        if classification != "safe_delete":
            skipped.append({"id": run_id, "reason": reason})
            continue
        api.delete_run(run_id)
        deleted.append(run_id)
    return {"deleted": deleted, "run_skipped": skipped}


def render_summary(report):
    plan = dict(report.get("plan") or {})
    summary = dict(plan.get("summary") or {})
    apply = report.get("apply")
    title = "Video RSS run retention: apply" if apply is not None else "Video RSS run retention: plan"
    lines = [
        f"## {title}",
        "",
        f"- Workflow: `{VIDEO_RSS_WORKFLOW_PATH}`",
        f"- Successful runs: keep newest **{KEEP_LATEST_SUCCESS_RUNS}** and all newer than **{SUCCESS_RETENTION_DAYS} days**",
        f"- Failed/cancelled runs: keep for **{DIAGNOSTIC_RETENTION_DAYS} days**",
        "- Queued/in-progress and unhandled conclusions: never auto-delete",
        f"- Runs seen: **{int(summary.get('total') or 0)}**",
        f"- Protected: **{int(summary.get('protected') or 0)}**",
        f"- Safe to delete: **{int(summary.get('safe_delete') or 0)}**",
        f"- Review only: **{int(summary.get('review_only') or 0)}**",
    ]
    if apply is not None:
        apply = dict(apply or {})
        lines.append(f"- Deleted: **{len(apply.get('deleted') or [])}**")
        lines.append(f"- Skipped after recheck: **{len(apply.get('run_skipped') or [])}**")
        if apply.get("skipped"):
            lines.append(f"- Cleanup stopped safely: `{apply['skipped']}`")
    lines.extend([
        "",
        "> Deleting a GitHub Actions workflow run also removes artifacts attached to that run; no tracked files or published content are touched.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "apply"), default="plan")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    if not token or not repository:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY are required")
    api = GitHub(repository, token, api_url)
    plan = build_plan(api)
    report = {"plan": plan}
    if args.mode == "apply":
        report["apply"] = apply_plan(api, plan)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(render_summary(report))
    print(json.dumps({"summary": plan["summary"], "apply": report.get("apply")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
