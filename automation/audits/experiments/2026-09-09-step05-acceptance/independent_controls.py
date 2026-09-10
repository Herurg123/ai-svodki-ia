#!/usr/bin/env python3
"""Independent, offline acceptance controls for Step 5 checkpoint b328d416."""
from __future__ import annotations
import copy, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'automation/preview/source-value-replay/independent_controls_result.json'
OUT.parent.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / 'automation/scripts'))
from source_pulse_value import build_report
from source_value_publication import verify_page
from source_value_period import aggregate

DAY='2026-09-08'; URL='https://vendor.example/news?id=one'
def pulse(disps, accepted, *, day=DAY):
    return {'publication_date': day, 'snapshot': {'sources':[{'source_id':'vendor','status':'ok','parsed_items':2,'window_items':1,'accepted_leads':len(disps)}]}, 'promotion': {'lead_dispositions':disps,'accepted_candidate_urls':accepted}}
def bundle(*, selected=True):
    cand={'id':'cand-1','title':'Pulse title','audit_direction':'source_pulse_v13','primary_source':{'url':URL},'organization':'Vendor','topic':'AI release','event_type':'release','published_date':DAY,'published_at':None,'source_freshness_status':'fresh','event_freshness_status':'unknown','recommendation':'consider'}
    story={k:cand[k] for k in ('organization','topic','event_type','published_date','published_at')}; story.update(candidate_id='cand-1',sources=[{'url':URL}])
    return {'candidates':{'publication_date':DAY,'candidates':[cand]},'editorial':{'status':'ok','digest':{'date':DAY},'selected_candidate_ids':['cand-1'] if selected else [],'excluded_candidate_ids':[] if selected else ['cand-1']},'stories':[story] if selected else []}
def promoted(): return {'source_id':'vendor','promotion_status':'promoted','url':URL,'title':'Pulse title'}
def row(r): return r['sources'][0]
cases=[]
def check(name, predicate, observed): cases.append({'name':name,'passed':bool(predicate),'observed':observed})

# Replay the four saved historical failures: each must now be rejected/unknown.
r=build_report(pulse(['bad'], [])); check('historical_malformed_disposition_no_false_zero', row(r)['confirmed_promoted_count'] is None and not row(r)['promotion_evidence_complete'] and 'promotion_dispositions_missing_or_malformed' in r['evidence_gaps'], {'count':row(r)['confirmed_promoted_count'],'complete':row(r)['promotion_evidence_complete'],'gaps':r['evidence_gaps']})
r=build_report(pulse([promoted(),promoted()],[URL,URL])); check('historical_duplicate_promotion_no_false_positive', row(r)['confirmed_promoted_count'] is None and not row(r)['promotion_evidence_complete'] and {'accepted_candidate_urls_duplicated','promotion_disposition_url_duplicated'} <= set(r['evidence_gaps']), {'count':row(r)['confirmed_promoted_count'],'complete':row(r)['promotion_evidence_complete'],'gaps':r['evidence_gaps']})
b=bundle(); c=b['candidates']['candidates'][0]; s=b['stories'][0]
for k in ('organization','topic','event_type','published_date','published_at'): c[k]=None; s[k]=None
r=build_report(pulse([promoted()],[URL]),b); check('historical_null_identity_no_selected_story', row(r)['editorial_selected'] is None and 'selected_story_identity_conflict' in r['evidence_gaps'], {'selected':row(r)['editorial_selected'],'gaps':r['evidence_gaps']})
stories=[{'headline':'Story A','sources':[{'url':'https://source.example/A'}]},{'headline':'Story B','sources':[{'url':'https://source.example/B'}]}]
try: verify_page(b'<h3>Story A</h3><a href="https://source.example/B">B</a><h3>Story B</h3><a href="https://source.example/A">A</a>',stories); cross=True
except ValueError: cross=False
check('historical_crosswired_h3_rejected', not cross, {'accepted':cross})

# Additional malformed and visibility controls.
r=build_report(pulse([{'source_id':'vendor','promotion_status':'promoted','url':'not-url','title':'Pulse title'}],[URL])); check('invalid_disposition_url_unknown', row(r)['confirmed_promoted_count'] is None and 'promotion_disposition_identity_or_status_invalid' in r['evidence_gaps'], {'count':row(r)['confirmed_promoted_count'],'gaps':r['evidence_gaps']})
r=build_report(pulse([promoted()],['https://vendor.example/other'])); check('accepted_disposition_conflict_unknown', row(r)['confirmed_promoted_count'] is None and 'promotion_and_accepted_urls_conflict' in r['evidence_gaps'], {'count':row(r)['confirmed_promoted_count'],'gaps':r['evidence_gaps']})
for name,page in [('hidden_link',b'<h3>Story A</h3><template><a href="https://source.example/A">A</a></template>'),('neighbor_link',b'<h3>Story A</h3><h3>Story B</h3><a href="https://source.example/A">A</a>')]:
    try: verify_page(page,[stories[0]]); accepted=True
    except ValueError: accepted=False
    check(name+'_not_publication_evidence',not accepted,{'accepted':accepted})

# Known preserved releases.
fixture=json.loads((ROOT/'automation/fixtures/recall/source-value-trace-2026-09.json').read_text())
for case in fixture['cases']:
    r=build_report(case['pulse'],case['bundle']); got=next(x for x in r['sources'] if x['source_id']==case['source_id'])['editorial_selected']
    check('saved_fixture_'+case['date'],got==case['expected_editorial_selected'],{'source':case['source_id'],'got':got,'expected':case['expected_editorial_selected']})
yandex=build_report(json.loads((ROOT/'automation/fixtures/recall/source-value-2026-09-08.json').read_text()))
yrow=next(x for x in yandex['sources'] if x['source_id']=='yandex_ir')
check('saved_yandex_sep6_negative_keeps_confirmed_zero', yrow['confirmed_promoted_count']==0 and yrow['promotion_evidence_complete'] is True, {'count':yrow['confirmed_promoted_count'],'complete':yrow['promotion_evidence_complete'],'gaps':yandex['evidence_gaps']})

# Observation-aware period controls.
first=build_report(pulse([promoted()],[URL]),bundle())
recovered=copy.deepcopy(first); recovered['snapshot_reused']=True
period=aggregate([first,copy.deepcopy(first),recovered]); m=period['sources'][0]['metrics']['editorial_selected']
check('same_day_exact_copy_and_recovery_not_double_counted',period['release_count']==1 and m['observed_total']==1 and m['complete_total']==1,{'duplicates':period['exact_duplicate_reports_ignored'],'metric':m})
conflict=copy.deepcopy(first); conflict['sources'][0]['parsed_items']=99; conflict['source_observation_id']='a'*64
period=aggregate([first,conflict]); m=period['sources'][0]['metrics']['confirmed_promoted_count']
check('conflicting_snapshots_preserve_unknown',m['observed_total'] is None and m['complete_total'] is None and 'source_observation_conflict_or_missing_identity' in period['days'][0]['evidence_gaps'],{'metric':m,'gaps':period['days'][0]['evidence_gaps']})
trace_conflict=copy.deepcopy(first); trace_conflict['trace_observation_id']='b'*64; trace_conflict['sources'][0]['editorial_selected']=0
period=aggregate([first,trace_conflict]); m=period['sources'][0]['metrics']['editorial_selected']
check('conflicting_traces_preserve_unknown',m['observed_total'] is None and m['complete_total'] is None and 'final_trace_conflict_or_missing_identity' in period['days'][0]['evidence_gaps'],{'metric':m,'gaps':period['days'][0]['evidence_gaps']})
# Valid committed evidence is selected over a conflicting draft trace for late metrics.
published=copy.deepcopy(first); published['input_sha256']='c'*64; published['repository_publication_evidence']={'scope':'repository_publication_on_origin_main','commit':'d'*40,'main_ref_commit':'e'*40,'post_sha256':'f'*64,'main_ref':'refs/remotes/origin/main','publication_date':DAY,'post_path':f'posts/{DAY}/index.html','input_sha256':{'pulse':'c'*64,'candidates':'1'*64,'editorial':'2'*64,'stories':'3'*64}}; published['sources'][0]['repository_published']=1
local=copy.deepcopy(first); local['trace_observation_id']='9'*64; local['sources'][0]['repository_published']=0; local['sources'][0]['editorial_selected']=0
period=aggregate([published,local]); s=period['sources'][0]
check('committed_publication_priority_over_local_draft',s['metrics']['repository_published']['observed_total']==1 and s['metrics']['editorial_selected']['observed_total']==1 and period['days'][0]['trace_selection']=='committed_repository_bundle',{'source':s,'selection':period['days'][0]['trace_selection']})
unknown=build_report(pulse([promoted()],[URL]))
period=aggregate([unknown]); m=period['sources'][0]['metrics']['editorial_selected']
check('null_not_zero_for_unobserved_total',m=={'observed_total':None,'observed_releases':0,'unknown_releases':1,'complete_total':None},{'metric':m})
result={'checkpoint':'b328d4169d719f3367b1c0e15daafe3d58175329','scope':'independent offline controls; no network/API/git mutation','cases':cases,'failed_controls':[x['name'] for x in cases if not x['passed']]}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
