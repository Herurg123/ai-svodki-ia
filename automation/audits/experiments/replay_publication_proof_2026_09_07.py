"""Independent baseline/proposal evidence replay with network forbidden."""
import argparse
import copy
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ap=argparse.ArgumentParser()
ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--full-yandex-html',type=Path)
args=ap.parse_args()
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'automation/scripts'))
import source_freshness as proposed
from publication_evidence_adapters import github_release_api_url
F=json.loads((ROOT/'automation/fixtures/recall/publication-proof-2026-09-05.json').read_text())
HTML=(ROOT/'automation/fixtures/recall/yandex-date-proof-2026-09-04.html').read_text()
START=datetime.fromisoformat(F['window']['start_at']);END=datetime.fromisoformat(F['window']['end_at'])
BASE='4fc0c164dd5159522047b7b457add1bac0a91f0c'
result={'status':'running','baseline':BASE,'checks':[],'network_calls':0,'paid_api_calls':0}

def check(name,condition):
    result['checks'].append({'name':name,'passed':bool(condition)})
    if not condition:raise AssertionError(name)

def run(baseline):
    def gate(module,index=0,body=HTML,release=None,end=END,candidate=None,redirect=None):
        c=copy.deepcopy(candidate or F['candidates'][index]);url=c['primary_source']['url'];calls=[]
        def fetch(target):
            calls.append(target)
            if target==url:return body,redirect or url,200
            if target==github_release_api_url(url):return json.dumps(release or F['release']),target,200
            raise AssertionError('Unexpected fetch: '+target)
        r=module.verify_candidate(c,start_at=START,end_at=end,fetcher=fetch)
        return c,r,calls
    for i,body in [(0,HTML),(1,'')]:
        old=gate(baseline,i,body);new=gate(proposed,i,body)
        check(f'saved case {i}: baseline loss',old[1]['status']=='excluded_unverified_freshness')
        check(f'saved case {i}: restored date eligibility',new[1]['status']=='verified_fresh' and new[0]['recommendation']=='consider')
        check(f'saved case {i}: bounded requests',len(new[2])==i+1)
        check(f'saved case {i}: deterministic saved-input replay',gate(proposed,i,body)==new)
    if args.full_yandex_html:
        full=args.full_yandex_html.read_text()
        check('full original page baseline loss',gate(baseline,body=full)[1]['status']=='excluded_unverified_freshness')
        check('full original page proposed eligibility',gate(proposed,body=full)[1]['status']=='verified_fresh')
        result['full_html_bytes']=args.full_yandex_html.stat().st_size
    for label,body in [('fresh','<meta property="article:published_time" content="2026-09-04T12:00:00Z">'),('stale','<meta property="article:published_time" content="2026-08-01T12:00:00Z">')]:
        for i in [0,1]:
            check(f'generic {label} {i} exact behavior',gate(baseline,i,body)==gate(proposed,i,body))
    for body,redirect in [('<h1>No date</h1>',None),('<h1>3 сентября 2026</h1>',None),(HTML,'https://example.org/other'),(HTML,F['yandex_url']+'&another=1')]:
        check('no borrowed Yandex proof '+str(redirect)+body[:20],gate(proposed,body=body,redirect=redirect)[1]['status']=='excluded_unverified_freshness')
    for modification in [{'draft':True},{'tag_name':'wrong'},{'html_url':'https://github.com/wrong/repo/releases/tag/x'},{'published_at':None},{'published_at':'2026-09-04T12:00:00'},{'published_at':'invalid'}]:
        check('invalid GitHub '+str(modification),gate(proposed,1,'',release={**F['release'],**modification})[1]['status']=='excluded_unverified_freshness')
    for i in [0,1]:
        stale=copy.deepcopy(F['candidates'][i]);stale.update(event_date='2026-08-25',event_at='2026-08-25T12:00:00Z',event_time_precision='datetime',event_origin_url=stale['primary_source']['url'],event_evidence_kind='official_announcement',event_date_evidence='Original 2026-08-25')
        old=gate(baseline,i,candidate=stale);new=gate(proposed,i,candidate=stale)
        check(f'stale event {i} exact behavior and no fetch',old==new and not new[2] and new[1]['status']=='excluded_event_freshness_stale')
    check('partial date cutoff rejected',gate(proposed,end=datetime.fromisoformat('2026-09-04T03:57:22+03:00'))[1]['status']=='excluded_outside_window')
    check('GitHub exact cutoff accepted',gate(proposed,1,'',release={**F['release'],'published_at':END.isoformat()})[1]['status']=='verified_fresh')
    check('GitHub future rejected',gate(proposed,1,'',release={**F['release'],'published_at':'2026-09-05T01:00:00Z'})[1]['status']=='excluded_outside_window')
    matrix=0
    for count in [0,1,3,6,12,25]:
        for region in ['world','russia','asia']:
            for stale_source in [False,True]:
                rows=[]
                for n in range(count):
                    row=copy.deepcopy(F['candidates'][0]);row.update(id=str(n),geography=region,recommendation=['include','consider','exclude'][n%3])
                    row['primary_source']['url']='https://example.org/shared'
                    rows.append(row)
                payload={'search_window':F['window'],'candidates':rows}
                body='<meta property="article:published_time" content="'+('2026-08-01' if stale_source else '2026-09-04')+'T12:00:00Z">'
                fetch=lambda url:(body,url,200)
                old=baseline.verify_research_payload(payload,fetcher=fetch)
                new=proposed.verify_research_payload(payload,fetcher=fetch)
                check(f'matrix {count}/{region}/{stale_source}: exact complete payload',old==new)
                matrix+=1
    result['matrix_cases']=matrix
    untouched=['.github/workflows','automation/scripts/event_freshness.py','automation/scripts/story_coverage.py','automation/scripts/primary_recall_search_v2.py','automation/scripts/hybrid_search_completeness.py','automation/scripts/ensure_story_coverage_policy.py','automation/scripts/recover_digest_artifact.py','automation/scripts/recover_digest_artifact_v1_base.py','posts','automation/content']
    check('budget ordering recovery public boundaries unchanged',not subprocess.check_output(['git','diff','--name-only',BASE,'--',*untouched],cwd=ROOT,text=True).strip())

try:
    with tempfile.TemporaryDirectory() as tmp:
        directory=Path(tmp)
        for name in ['source_freshness.py','source_freshness_v1.py','event_freshness.py']:
            (directory/name).write_bytes(subprocess.check_output(['git','show',BASE+':automation/scripts/'+name],cwd=ROOT))
        spec=importlib.util.spec_from_file_location('baseline_step03',directory/'source_freshness.py')
        baseline=importlib.util.module_from_spec(spec);sys.modules[spec.name]=baseline;spec.loader.exec_module(baseline)
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')):
            run(baseline)
    result['status']='passed'
except Exception as exc:
    result.update(status='failed',reason=str(exc),error_type=type(exc).__name__)
finally:
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
    sys.exit(0 if result['status']=='passed' else 1)
