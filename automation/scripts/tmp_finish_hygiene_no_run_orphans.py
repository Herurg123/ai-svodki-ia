from pathlib import Path


def rep(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


rep(
    "automation/scripts/repository_hygiene_policy.py",
    '''    if not runs:\n        return "review_only", "orphan_workflow_without_runs"\n''',
    '''    if not runs:\n        if str(workflow.get("state") or "") == "active":\n            return "safe_disable", "orphan_workflow_removed_without_runs"\n        return "review_only", "orphan_workflow_already_disabled_without_runs"\n''',
)

rep(
    "automation/tests/test_repository_hygiene.py",
    '''        orphan = {"id":3, "path":".github/workflows/temporary.yml"}\n        main_runs = [{"head_branch":"main", "created_at":"2026-08-01T00:00:00Z"}]\n''',
    '''        orphan = {"id":3, "path":".github/workflows/temporary.yml", "state":"active"}\n        self.assertEqual(\n            rh.classify_workflow(orphan, canonical, False, {}, {}, []),\n            ("safe_disable", "orphan_workflow_removed_without_runs"),\n        )\n        disabled_orphan = {"id":4, "path":".github/workflows/old.yml", "state":"disabled_manually"}\n        self.assertEqual(\n            rh.classify_workflow(disabled_orphan, canonical, False, {}, {}, []),\n            ("review_only", "orphan_workflow_already_disabled_without_runs"),\n        )\n        main_runs = [{"head_branch":"main", "created_at":"2026-08-01T00:00:00Z"}]\n''',
)

rep(
    "README.md",
    '''  другой ветке, действует классификация этой ветки и её grace/TTL. Динамический\n  GitHub Pages workflow является платформенным объектом GitHub: при\n''',
    '''  другой ветке, действует классификация этой ветки и её grace/TTL. Активный\n  orphan workflow вообще без runs также безопасно отключается, поскольку его\n  файла уже нет в текущем `main`; уже отключённый объект без runs остаётся\n  только диагностической записью. Динамический GitHub Pages workflow является\n  платформенным объектом GitHub: при\n''',
)

rep(
    "automation/README.md",
    '''последним run на другой ветке действует lifecycle этой ветки; canonical workflow\nи любой workflow с живым run защищён. Для динамического GitHub Pages workflow\n''',
    '''последним run на другой ветке действует lifecycle этой ветки; canonical workflow\nи любой workflow с живым run защищён. Активный orphan workflow без единого run\nтоже отключается, если его файла уже нет в текущем `main`; уже отключённый\nобъект без runs остаётся только диагностическим. Для динамического GitHub Pages workflow\n''',
)

rep(
    "AGENTS.md",
    '''default branch may be disabled once it has no live run; absence from current\n`main` is the canonical proof that the workflow was removed. GitHub-managed\n''',
    '''default branch may be disabled once it has no live run; absence from current\n`main` is the canonical proof that the workflow was removed. An active orphan\nworkflow with no runs may also be disabled on the same canonical-absence proof;\nalready-disabled no-run workflow metadata is report-only. GitHub-managed\n''',
)
