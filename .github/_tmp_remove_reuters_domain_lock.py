from pathlib import Path

QUERY_OLD='latest artificial intelligence funding acquisition models chips data centers cybersecurity'
QUERY_NEW='Reuters latest artificial intelligence funding acquisition models chips data centers cybersecurity'

p=Path('automation/scripts/ensure_story_coverage.py')
text=p.read_text(encoding='utf-8')
repls={
 'AGENCY_RESCUE_VERSION = 3':'AGENCY_RESCUE_VERSION = 4',
 'AGENCY_RESCUE_DOMAINS: tuple[str, ...] = ("reuters.com",)':'AGENCY_RESCUE_DOMAINS: tuple[str, ...] = ()',
 f'required_query = "{QUERY_OLD}"':f'required_query = "{QUERY_NEW}"',
 '"label": "Fresh Reuters source-health rescue v3"':'"label": "Fresh agency source-health rescue v4"',
 'ИИ-событий из Reuters, которых НЕТ в текущем пуле. API domain filter уже\nограничен Reuters.':'ИИ-событий из Reuters или другого допустимого high-signal agency-домена, которых НЕТ в текущем пуле. API domain filter намеренно отключён: слово Reuters используется как ranking hint, а домен и свежесть проверяются кодом после retrieval.',
}
for old,new in repls.items():
 if old not in text: raise SystemExit(f'missing marker: {old!r}')
 text=text.replace(old,new,1)
# Accept only verified in-window agency-host candidates even though retrieval is unfiltered.
old='''    accepted_for_pass = [\n        _normalize_agency_rescue_candidate(item)\n        for item in raw_candidates\n        if isinstance(item, dict)\n    ] if isinstance(raw_candidates, list) else []\n'''
new='''    accepted_for_pass = [\n        _normalize_agency_rescue_candidate(item)\n        for item in raw_candidates\n        if isinstance(item, dict)\n        and _policy._candidate_has_fresh_agency_source(item, search_window)\n    ] if isinstance(raw_candidates, list) else []\n'''
if old not in text: raise SystemExit('accepted_for_pass marker missing')
text=text.replace(old,new,1)
p.write_text(text,encoding='utf-8')

p=Path('automation/scripts/ensure_story_coverage_policy.py')
text=p.read_text(encoding='utf-8')
if 'SOURCE_HEALTH_CONTRACT_VERSION = 3' not in text: raise SystemExit('contract v3 missing')
text=text.replace('SOURCE_HEALTH_CONTRACT_VERSION = 3','SOURCE_HEALTH_CONTRACT_VERSION = 4',1)
p.write_text(text,encoding='utf-8')

p=Path('automation/tests/test_agency_rescue.py')
text=p.read_text(encoding='utf-8')
text=text.replace(f'metadata("{QUERY_OLD}")',f'metadata("{QUERY_NEW}")',1)
text=text.replace('self.assertEqual(tuple(call["allowed_domains"]), ("reuters.com",))','self.assertEqual(tuple(call["allowed_domains"]), ())',1)
text=text.replace(f'self.assertIn("{QUERY_OLD}", call["prompt"])',f'self.assertIn("{QUERY_NEW}", call["prompt"])',1)
# Add rejection regression for non-agency candidate from unfiltered retrieval.
marker='''    def test_fresh_agency_candidate_does_not_spend_seventh_slot(self):\n'''
insert='''    def test_unfiltered_rescue_drops_non_agency_candidate(self):\n        existing = [candidate(publisher="TechCrunch", url="https://techcrunch.com/2026/08/13/existing/")]\n        non_agency = candidate(publisher="Example", url="https://example.com/fresh-ai-story")\n        def fake_request(**kwargs):\n            return ({"status":"complete","error_message":None,"direction_id":"general_coverage_gaps","candidates":[non_agency],"rejections":[],"notes":"test"}, metadata("Reuters latest artificial intelligence funding acquisition models chips data centers cybersecurity"))\n        with mock.patch.object(runtime, "_BASE_EXECUTE_AUDIT_PLAN", return_value=complete_plan()), mock.patch.object(runtime, "run_audit_request", side_effect=fake_request):\n            result = runtime.execute_audit_plan(api_key="secret", model="gpt-5.6-terra", template="unused", publication_date="2026-08-14", search_window=SEARCH_WINDOW, missing_total=0, maximum_web_search_calls=7, existing_candidates=existing, archive={"items": []})\n        rescue=result["attempts"][-1]\n        self.assertEqual(rescue["candidate_count"],0)\n\n'''
if marker not in text: raise SystemExit('test insertion marker missing')
text=text.replace(marker,insert+marker,1)
p.write_text(text,encoding='utf-8')

for path in ('README.md','automation/README.md','AGENTS.md'):
 p=Path(path); text=p.read_text(encoding='utf-8')
 old=f'''используется как bounded `fresh_agency_rescue`: один date-free запрос\n`{QUERY_OLD}` с API domain filter только на\nReuters. AP остаётся допустимой agency evidence, если её находят другие research-слои; Bloomberg/FT уже имеют отдельный `major_agencies` шанс в Primary.'''
 new=f'''используется как bounded `fresh_agency_rescue`: один date-free запрос\n`{QUERY_NEW}` без API domain filter. `Reuters` в query служит ranking hint; после retrieval код принимает только кандидаты с фактическим primary URL Reuters/AP/Bloomberg/FT и датой внутри effective window. Это обходит подтверждённую live-smoke слепоту Reuters `allowed_domains`, не ослабляя source-health acceptance.'''
 if old not in text: raise SystemExit(f'doc marker missing {path}')
 text=text.replace(old,new,1); p.write_text(text,encoding='utf-8')
Path('.github/_tmp_remove_reuters_domain_lock.py').unlink()
