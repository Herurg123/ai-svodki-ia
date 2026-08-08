from __future__ import annotations

import datetime as dt
import re
import subprocess
from pathlib import Path

RECENT_MERGED_PRS = 5
KEEP_FULL_PRODUCTION_DATES = 2
KEEP_FINAL_PRODUCTION_DATES = 5
ORPHAN_WATCH_MERGES = 5
ORPHAN_SUSPECT_MERGES = 10
STALE_QUEUED_AFTER_DAYS = 14
PRODUCTION_RE = re.compile(r"^daily-production-(\d{4}-\d{2}-\d{2})$")
CI_RE = re.compile(r"^main-ci-([0-9a-f]{40})$")
SCAN_ROOTS = ("automation/scripts", "automation/config", "automation/prompts", "automation/specs")
CORPUS_ROOTS = (".github", "automation", "README.md", "AGENTS.md")
TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".json", ".md", ".txt", ".toml", ".ini", ".cfg", ".html", ".xml", ".sh"}


def iso(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def pr_branch(pr, repository):
    head = pr.get("head") or {}
    repo = head.get("repo") or {}
    return head.get("ref") if repo.get("full_name") == repository else None


def merged_sorted(prs):
    return sorted((pr for pr in prs if pr.get("merged_at")), key=lambda pr: iso(pr["merged_at"]), reverse=True)


def latest_pr_for_branch(name, prs, repository):
    related = [pr for pr in prs if pr_branch(pr, repository) == name]
    if not related:
        return None
    floor = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return max(related, key=lambda pr: iso(pr.get("updated_at")) or iso(pr.get("created_at")) or floor)


def branch_history_class(name, prs, repository, recent_numbers):
    related = [pr for pr in prs if pr_branch(pr, repository) == name]
    if any(pr.get("state") == "open" for pr in related):
        return "protected"
    latest = latest_pr_for_branch(name, prs, repository)
    if not latest or not latest.get("merged_at"):
        return "review_only"
    return "protected" if int(latest["number"]) in recent_numbers else "safe_delete"


def classify_branch(branch, *, repository, default_branch, prs, recent_numbers, active_branches=frozenset()):
    name = str(branch.get("name") or "")
    if name == default_branch:
        return "protected", "default_branch", None
    if branch.get("protected"):
        return "protected", "github_protected_branch", None
    if name in active_branches:
        return "protected", "active_actions_run", None
    related = [pr for pr in prs if pr_branch(pr, repository) == name]
    if any(pr.get("state") == "open" for pr in related):
        return "protected", "open_pull_request", None
    latest = latest_pr_for_branch(name, prs, repository)
    if not latest:
        return "review_only", "branch_has_no_pull_request", None
    if not latest.get("merged_at"):
        return "review_only", "latest_pull_request_not_merged", latest
    if int(latest["number"]) in recent_numbers:
        return "protected", "recent_merged_pull_request", latest
    if (latest.get("head") or {}).get("sha") != (branch.get("commit") or {}).get("sha"):
        return "review_only", "branch_diverged_after_merge", latest
    return "safe_delete", "old_merged_pull_request", latest


def publication_dates(rss_text: str):
    return sorted(set(re.findall(r"/posts/(\d{4}-\d{2}-\d{2})/", rss_text)), reverse=True)


def has_publish_step(jobs):
    return any(
        step.get("name") == "Commit production release" and step.get("conclusion") == "success"
        for job in jobs for step in (job.get("steps") or [])
    )


def classify_production(groups, dates, final_runs):
    positions = {date: index for index, date in enumerate(dates)}
    latest = dates[0] if dates else None
    result = {}
    for date, artifacts in groups.items():
        position = positions.get(date)
        if position is None:
            classification = "protected" if latest is None or date >= latest else "review_only"
            reason = "unpublished_current_or_future" if classification == "protected" else "unpublished_historical"
            for artifact in artifacts:
                result[int(artifact["id"])] = (classification, reason)
            continue
        if position < KEEP_FULL_PRODUCTION_DATES:
            for artifact in artifacts:
                result[int(artifact["id"])] = ("protected", "recent_publication_full_chain")
            continue
        if position < KEEP_FINAL_PRODUCTION_DATES:
            finals = [a for a in artifacts if int((a.get("workflow_run") or {}).get("id") or -1) in final_runs]
            keep_id = int(max(finals, key=lambda a: a.get("created_at") or "")["id"]) if finals else None
            for artifact in artifacts:
                artifact_id = int(artifact["id"])
                if artifact_id == keep_id:
                    result[artifact_id] = ("protected", "final_publish_artifact")
                elif keep_id is None:
                    result[artifact_id] = ("review_only", "published_without_identified_final_artifact")
                else:
                    result[artifact_id] = ("safe_delete", "superseded_published_artifact")
            continue
        for artifact in artifacts:
            result[int(artifact["id"])] = ("safe_delete", "published_outside_recovery_window")
    return result


def classify_ci(artifact, protected_shas, branch_classes, history_classes):
    match = CI_RE.match(str(artifact.get("name") or ""))
    if not match:
        return "review_only", "not_ci_artifact"
    if match.group(1) in protected_shas:
        return "protected", "recent_final_ci"
    branch = str((artifact.get("workflow_run") or {}).get("head_branch") or "")
    branch_class = branch_classes.get(branch, history_classes.get(branch))
    if branch_class == "review_only":
        return "review_only", "review_only_branch"
    if branch_class is None:
        return "review_only", "unknown_ci_branch"
    return "safe_delete", "superseded_ci_artifact"


def live_run(run, now=None):
    if run.get("status") == "in_progress":
        return True
    if run.get("status") != "queued":
        return False
    created = iso(run.get("created_at"))
    if not created:
        return True
    now = now or dt.datetime.now(dt.timezone.utc)
    return created >= now - dt.timedelta(days=STALE_QUEUED_AFTER_DAYS)


def classify_workflow(workflow, canonical_paths, has_pages, branch_classes, history_classes, runs):
    path = str(workflow.get("path") or "")
    if path in canonical_paths:
        return "protected", "canonical_workflow"
    if any(live_run(run) for run in runs):
        return "protected", "workflow_has_active_run"
    if path.startswith("dynamic/pages/"):
        return ("protected", "github_pages_enabled") if has_pages else ("safe_disable", "github_pages_disabled")
    if not runs:
        return "review_only", "orphan_workflow_without_runs"
    latest = max(runs, key=lambda run: run.get("created_at") or "")
    branch = str(latest.get("head_branch") or "")
    branch_class = branch_classes.get(branch, history_classes.get(branch, "review_only"))
    if branch_class in {"protected", "review_only"}:
        return "protected", "workflow_tied_to_retained_branch"
    return "safe_disable", "orphan_workflow_from_old_merged_branch"


def _text_corpus(root: Path):
    result = {}
    for raw in CORPUS_ROOTS:
        path = root / raw
        candidates = [path] if path.is_file() else list(path.rglob("*")) if path.is_dir() else []
        for candidate in candidates:
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in TEXT_SUFFIXES and candidate.name not in {"README.md", "AGENTS.md"}:
                continue
            try:
                result[candidate.relative_to(root)] = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                pass
    return result


def scan_sources(root: Path, merged_prs):
    corpus = _text_corpus(root)
    merge_times = [iso(pr.get("merged_at")) for pr in merged_prs if pr.get("merged_at")]
    result = {"watchlist": [], "suspected_orphans": []}
    for raw in SCAN_ROOTS:
        base = root / raw
        if not base.is_dir():
            continue
        candidates = (p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES)
        for path in candidates:
            relative = path.relative_to(root)
            keys = {str(relative), relative.name, relative.stem if relative.suffix == ".py" else ""}
            referenced = any(
                other != relative and any(key and key in text for key in keys)
                for other, text in corpus.items()
            )
            if referenced:
                continue
            try:
                stamp = subprocess.check_output(
                    ["git", "log", "-1", "--format=%ct", "--", str(relative)],
                    cwd=root, text=True, stderr=subprocess.DEVNULL,
                ).strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
            if not stamp.isdigit():
                continue
            changed = dt.datetime.fromtimestamp(int(stamp), tz=dt.timezone.utc)
            merges_since = sum(1 for merged_at in merge_times if merged_at and merged_at > changed)
            record = {"path": str(relative), "merges_since_last_change": merges_since, "last_change_at": changed.isoformat()}
            if merges_since >= ORPHAN_SUSPECT_MERGES:
                result["suspected_orphans"].append(record)
            elif merges_since >= ORPHAN_WATCH_MERGES:
                result["watchlist"].append(record)
    for records in result.values():
        records.sort(key=lambda item: item["path"])
    return result
