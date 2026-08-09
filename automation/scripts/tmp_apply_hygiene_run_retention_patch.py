from pathlib import Path


def rep(path, old, new):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise SystemExit(f"missing marker in {path}: {old[:100]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


policy = "automation/scripts/repository_hygiene_policy.py"
rep(
    policy,
    "CLOSED_UNMERGED_TTL_DAYS = 14\nKEEP_FULL_PRODUCTION_DATES = 2\n",
    "CLOSED_UNMERGED_TTL_DAYS = 14\nORPHAN_WORKFLOW_RUN_RETENTION_DAYS = 14\nKEEP_FULL_PRODUCTION_DATES = 2\n",
)
rep(
    policy,
    "\ndef _text_corpus(root: Path):\n",
    '''\ndef classify_orphan_workflow_run(run, workflow_classification, now=None):
    if workflow_classification != "safe_disable":
        return "review_only", "workflow_not_safe_to_disable"
    if str(run.get("status") or "") != "completed":
        return "review_only", "workflow_run_not_completed"
    created = iso(run.get("created_at"))
    if not created:
        return "review_only", "workflow_run_missing_created_at"
    now = now or dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=ORPHAN_WORKFLOW_RUN_RETENTION_DAYS)
    if created > cutoff:
        return "protected", "recent_orphan_workflow_run"
    return "safe_delete", "expired_orphan_workflow_run"


def _text_corpus(root: Path):
''',
)

runtime = "automation/scripts/repository_hygiene.py"
rep(
    runtime,
    "    CLOSED_UNMERGED_TTL_DAYS,\n    STALE_QUEUED_AFTER_DAYS,\n",
    "    CLOSED_UNMERGED_TTL_DAYS,\n    ORPHAN_WORKFLOW_RUN_RETENTION_DAYS,\n    STALE_QUEUED_AFTER_DAYS,\n",
)
rep(
    runtime,
    "    classify_production,\n    classify_workflow,\n",
    "    classify_production,\n    classify_workflow,\n    classify_orphan_workflow_run,\n",
)
old_runs = '''    stale_runs = []
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
'''
new_runs = '''    stale_runs = []
    workflow_classes = {item["id"]: item["classification"] for item in workflow_items}
    for workflow in workflows:
        workflow_id = int(workflow["id"])
        workflow_class = workflow_classes[workflow_id]
        for run in workflow_runs[workflow_id]:
            status = str(run.get("status") or "")
            if status == "queued" and not live_run(run, now):
                stale_runs.append({
                    "id": int(run["id"]),
                    "workflow_id": workflow_id,
                    "workflow": str(workflow.get("name") or ""),
                    "head_branch": str(run.get("head_branch") or ""),
                    "created_at": run.get("created_at"),
                    "classification": "review_only",
                    "reason": "stale_orphan_run" if workflow_class == "safe_disable" else "stale_queued_run",
                })
                continue
            if status != "completed" or workflow_class != "safe_disable":
                continue
            cls, reason = classify_orphan_workflow_run(run, workflow_class, now)
            stale_runs.append({
                "id": int(run["id"]),
                "workflow_id": workflow_id,
                "workflow": str(workflow.get("name") or ""),
                "head_branch": str(run.get("head_branch") or ""),
                "created_at": run.get("created_at"),
                "classification": cls,
                "reason": reason,
            })
'''
rep(runtime, old_runs, new_runs)
rep(
    runtime,
    '            "closed_unmerged_ttl_days": CLOSED_UNMERGED_TTL_DAYS,\n            "keep_full_production_dates": KEEP_FULL_PRODUCTION_DATES,\n',
    '            "closed_unmerged_ttl_days": CLOSED_UNMERGED_TTL_DAYS,\n            "orphan_workflow_run_retention_days": ORPHAN_WORKFLOW_RUN_RETENTION_DAYS,\n            "keep_full_production_dates": KEEP_FULL_PRODUCTION_DATES,\n',
)
old_return = '''        api.disable_workflow(item["id"])
        disabled.append(item["id"])

    return {
        "artifacts_deleted": deleted,
        "artifact_skipped": skipped,
        "workflows_disabled": disabled,
        "workflow_skipped": workflow_skipped,
    }
'''
new_return = '''        api.disable_workflow(item["id"])
        disabled.append(item["id"])

    run_deleted = []
    run_skipped = []
    fresh = build_plan(api, root)
    safe_main(api, plan["main_sha"])
    workflow_classes = {int(item["id"]): item["classification"] for item in fresh["workflows"]}
    for item in fresh["workflow_runs"]:
        if item["classification"] != "safe_delete":
            continue
        safe_main(api, plan["main_sha"])
        if production_active(api, production_id):
            return {
                "skipped": "production_started_during_actions_cleanup",
                "artifacts_deleted": deleted,
                "artifact_skipped": skipped,
                "workflows_disabled": disabled,
                "workflow_skipped": workflow_skipped,
                "workflow_runs_deleted": run_deleted,
                "workflow_run_skipped": run_skipped,
            }
        workflow_id = int(item["workflow_id"])
        if workflow_classes.get(workflow_id) != "safe_disable":
            run_skipped.append({"id": item["id"], "reason": "workflow_no_longer_safe"})
            continue
        current_runs = api.workflow_runs(workflow_id)
        current = next(
            (run for run in current_runs if int(run.get("id") or 0) == int(item["id"])),
            None,
        )
        if current is None:
            run_skipped.append({"id": item["id"], "reason": "already_missing"})
            continue
        cls, reason = classify_orphan_workflow_run(
            current, "safe_disable", dt.datetime.now(dt.timezone.utc)
        )
        if cls != "safe_delete":
            run_skipped.append({"id": item["id"], "reason": reason})
            continue
        api.delete_run(int(item["id"]))
        run_deleted.append(int(item["id"]))

    return {
        "artifacts_deleted": deleted,
        "artifact_skipped": skipped,
        "workflows_disabled": disabled,
        "workflow_skipped": workflow_skipped,
        "workflow_runs_deleted": run_deleted,
        "workflow_run_skipped": run_skipped,
    }
'''
rep(runtime, old_return, new_return)

client = "automation/scripts/repository_hygiene_github.py"
rep(
    client,
    '''    def workflow_runs(self, workflow_id: int):
        data = self.request("GET", f"/repos/{self.repository}/actions/workflows/{workflow_id}/runs?per_page=100")[1]
        return data.get("workflow_runs", [])
''',
    '''    def workflow_runs(self, workflow_id: int, limit: int = 100):
        limit = max(1, min(int(limit), 100))
        data = self.request(
            "GET",
            f"/repos/{self.repository}/actions/workflows/{workflow_id}/runs?per_page={limit}",
        )[1]
        return list(data.get("workflow_runs", []))[:limit]
''',
)
rep(
    client,
    '''    def disable_workflow(self, workflow_id: int):
        self.request("PUT", f"/repos/{self.repository}/actions/workflows/{workflow_id}/disable", (204,))
''',
    '''    def disable_workflow(self, workflow_id: int):
        self.request("PUT", f"/repos/{self.repository}/actions/workflows/{workflow_id}/disable", (204,))

    def delete_run(self, run_id: int):
        self.request("DELETE", f"/repos/{self.repository}/actions/runs/{run_id}", (204,))
''',
)

renderer = "automation/scripts/render_repository_hygiene_summary.py"
rep(
    renderer,
    '        workflow_skipped = list(actions_apply.get("workflow_skipped") or [])\n',
    '        workflow_skipped = list(actions_apply.get("workflow_skipped") or [])\n        run_deleted_ids = [int(value) for value in actions_apply.get("workflow_runs_deleted") or []]\n        run_skipped = list(actions_apply.get("workflow_run_skipped") or [])\n',
)
rep(
    renderer,
    '                f"- Отключено orphaned workflows: **{len(disabled_ids)}**",\n                f"- Пропущено artifacts после повторной проверки: **{len(artifact_skipped)}**",\n',
    '                f"- Отключено orphaned workflows: **{len(disabled_ids)}**",\n                f"- Удалено просроченных runs доказанных orphan-workflows: **{len(run_deleted_ids)}**",\n                f"- Пропущено artifacts после повторной проверки: **{len(artifact_skipped)}**",\n',
)
rep(
    renderer,
    '                f"- Пропущено workflows после повторной проверки: **{len(workflow_skipped)}**",\n',
    '                f"- Пропущено workflows после повторной проверки: **{len(workflow_skipped)}**",\n                f"- Пропущено workflow runs после повторной проверки: **{len(run_skipped)}**",\n',
)
rep(
    renderer,
    '''        lines.extend(
            _details(
                "Отключённые workflows",
                [f"`{workflow_names.get(item_id, item_id)}` (id {item_id})" for item_id in disabled_ids],
            )
        )
''',
    '''        lines.extend(
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
''',
)

tests = "automation/tests/test_repository_hygiene.py"
rep(
    tests,
    "    def test_production_artifact_windows(self):\n",
    '''    def test_completed_orphan_workflow_runs_expire_after_retention(self):
        now = rh.dt.datetime(2026, 8, 20, tzinfo=rh.dt.timezone.utc)
        old_run = {"id": 100, "status": "completed", "created_at": "2026-08-01T00:00:00Z"}
        fresh_run = {"id": 101, "status": "completed", "created_at": "2026-08-10T00:00:00Z"}
        self.assertEqual(
            rh.classify_orphan_workflow_run(old_run, "safe_disable", now),
            ("safe_delete", "expired_orphan_workflow_run"),
        )
        self.assertEqual(
            rh.classify_orphan_workflow_run(fresh_run, "safe_disable", now),
            ("protected", "recent_orphan_workflow_run"),
        )
        self.assertEqual(
            rh.classify_orphan_workflow_run(old_run, "protected", now),
            ("review_only", "workflow_not_safe_to_disable"),
        )

    def test_production_artifact_windows(self):
''',
)
summary_test = "automation/tests/test_repository_hygiene_summary.py"
rep(
    summary_test,
    '            "workflow_skipped": [],\n',
    '            "workflow_skipped": [],\n            "workflow_runs_deleted": [30],\n            "workflow_run_skipped": [],\n',
)
rep(
    summary_test,
    '        self.assertIn("`Old patch` (id 20)", text)\n',
    '        self.assertIn("`Old patch` (id 20)", text)\n        self.assertIn("Удалено просроченных runs доказанных orphan-workflows: **1**", text)\n        self.assertIn("run id 30", text)\n',
)

rep(
    "README.md",
    '''- Старые workflow runs не удаляются автоматически. Зависшие runs orphaned
  workflows и подозрительно неиспользуемые scripts/config/prompts/specs лишь
  попадают в отчёт. Source scanner начинает watchlist после пяти merge и
''',
    '''- Завершённые runs workflow, уже доказанно классифицированного как orphan
  (`safe_disable`), хранятся ещё 14 суток, после чего ежедневная hygiene удаляет
  их с повторной проверкой workflow, статуса и возраста. Runs canonical,
  protected и review-only workflows не затрагиваются; stale queued runs остаются
  report-only. Source scanner начинает watchlist после пяти merge и
''',
)
rep(
    "automation/README.md",
    '''`in_progress` всегда живой. `queued` старше 14 дней считается зависшим и не
может навечно защищать orphan-workflow. Такие stale runs попадают в отчёт, но
первая версия hygiene их не удаляет.
''',
    '''`in_progress` всегда живой. `queued` старше 14 дней считается зависшим и не
может навечно защищать orphan-workflow; такие stale queued runs остаются
report-only. Завершённый run удаляется автоматически только после 14 суток и
только если его workflow при повторном плане всё ещё доказанно `safe_disable`.
Canonical, protected и review-only workflows этим механизмом не затрагиваются.
''',
)
rep(
    "AGENTS.md",
    '''ephemeral GitHub objects: old merged branch refs, safe Actions artifacts, and
the enabled state of orphaned Actions workflows. It must not edit tracked
''',
    '''ephemeral GitHub objects: old merged branch refs, safe Actions artifacts, the
enabled state of orphaned Actions workflows, and completed runs older than 14
days only when their workflow is independently classified `safe_disable`. It
must not edit tracked
''',
)
