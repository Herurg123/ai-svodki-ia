from pathlib import Path

p=Path('automation/scripts/ensure_story_coverage.py')
text=p.read_text(encoding='utf-8')
text=text.replace('AGENCY_RESCUE_VERSION = 6','AGENCY_RESCUE_VERSION = 7',1)
old='''    if anchors:\n        return " ".join(["Reuters", organization, *anchors]).strip()\n'''
new='''    if anchors:\n        # Exact monetary anchors are stronger retrieval signals than a publisher\n        # name; live Aug-14 recovery showed that the Reuters hint biased ranking\n        # toward an older syndicated $188B story. Acceptance remains agency-only.\n        return " ".join([organization, *anchors]).strip()\n'''
if old not in text: raise SystemExit('money query marker missing')
text=text.replace(old,new,1)
p.write_text(text,encoding='utf-8')

p=Path('automation/scripts/ensure_story_coverage_policy.py')
text=p.read_text(encoding='utf-8').replace('SOURCE_HEALTH_CONTRACT_VERSION = 6','SOURCE_HEALTH_CONTRACT_VERSION = 7',1)
p.write_text(text,encoding='utf-8')

p=Path('automation/tests/test_agency_corroboration.py')
text=p.read_text(encoding='utf-8').replace('"Reuters Databricks $5 billion $190 billion"','"Databricks $5 billion $190 billion"',1)
p.write_text(text,encoding='utf-8')

for path in ('README.md','automation/README.md','AGENTS.md'):
 p=Path(path); text=p.read_text(encoding='utf-8')
 text=text.replace('`fresh_agency_rescue` **v6**','`fresh_agency_rescue` **v7**',1)
 old='строит короткий date-free query с `Reuters` как ranking hint; для денежных событий он прежде всего использует отличительные monetary anchors прямо из заголовка (`organization + сумма + valuation`), а при их отсутствии откатывается к `organization + event_type + keyword`'
 new='строит короткий date-free query; для денежных событий он прежде всего использует отличительные monetary anchors прямо из заголовка (`organization + сумма + valuation`) без publisher-hint, а при их отсутствии откатывается к `Reuters + organization + event_type + keyword`. Прямой agency-домен всё равно обязателен на acceptance-этапе'
 if old not in text: raise SystemExit(f'doc v6 marker missing {path}')
 text=text.replace(old,new,1); p.write_text(text,encoding='utf-8')
Path('.github/_tmp_anchor_query_v7.py').unlink()
