from pathlib import Path

# The executor is shared by modern Primary and legacy recovery fixtures. Source
# corroboration must only run when policy.main() explicitly determined that the
# current artifact is a modern Primary artifact with missing agency evidence.
p=Path('automation/scripts/ensure_story_coverage.py')
text=p.read_text(encoding='utf-8')
old='''    existing_candidates: list[Any],\n    archive: dict[str, Any],\n    prior_plan: dict[str, Any] | None = None,\n) -> dict[str, Any]:\n'''
new='''    existing_candidates: list[Any],\n    archive: dict[str, Any],\n    prior_plan: dict[str, Any] | None = None,\n    source_health_rescue_needed: bool = False,\n) -> dict[str, Any]:\n'''
if old not in text: raise SystemExit('execute_audit_plan signature marker missing')
text=text.replace(old,new,1)
old='''        and mandatory_complete\n        and agency_rescue_needed\n        and remaining_calls >= 1\n'''
new='''        and mandatory_complete\n        and source_health_rescue_needed\n        and agency_rescue_needed\n        and remaining_calls >= 1\n'''
if old not in text: raise SystemExit('agency rescue condition marker missing')
text=text.replace(old,new,1)
p.write_text(text,encoding='utf-8')

p=Path('automation/scripts/ensure_story_coverage_policy.py')
text=p.read_text(encoding='utf-8')
old='''                        archive=archive,\n                        prior_plan=prior_report if prior_attempted else None,\n                    )\n'''
new='''                        archive=archive,\n                        prior_plan=prior_report if prior_attempted else None,\n                        source_health_rescue_needed=source_health_rescue_needed,\n                    )\n'''
if old not in text: raise SystemExit('policy execute call marker missing')
text=text.replace(old,new,1)
p.write_text(text,encoding='utf-8')

# Documentation sentence makes the activation boundary explicit.
for path in ('README.md','automation/README.md','AGENTS.md'):
    p=Path(path); text=p.read_text(encoding='utf-8')
    needle='Legacy-выпуски без `primary-recall.json` сохраняют прежнюю recovery-совместимость.'
    replacement=needle+' Исполнитель Coverage получает явный `source_health_rescue_needed` от policy-layer; сам по себе ненулевой legacy/fixture pool никогда не активирует targeted corroboration.'
    if needle not in text: raise SystemExit(f'doc scope marker missing: {path}')
    text=text.replace(needle,replacement,1)
    p.write_text(text,encoding='utf-8')

Path('.github/_tmp_scope_targeted_rescue_v5.py').unlink()
