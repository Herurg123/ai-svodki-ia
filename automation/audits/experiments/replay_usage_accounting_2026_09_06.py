"""Frozen-proposal acceptance using prior-audit evidence and separate fault cases."""
import argparse, ast, contextlib, copy, hashlib, io, json, os, socket, subprocess, sys, tempfile
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence-root',type=Path,required=True)
parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3])
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
ROOT=args.evidence_root;REPO=args.repo;OUT=args.output
OUT.mkdir(parents=True,exist_ok=True)
BASE='0e9cc144b5cd8c039eee6be52fb52e4ee072fa31'
sys.path.insert(0,str(REPO/'automation/scripts'))
import usage_ledger, usage_observer
result={'status':'running','baseline':BASE,'branch':'codex/audit-01-accounting-resume','checks':[], 'production_api_calls':0,'network_calls':0}
def check(name,condition,details=None):
 row={'name':name,'passed':bool(condition),'details':details}; result['checks'].append(row)
 if not condition: raise AssertionError(name)
def treehash(roots):
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in roots for p in root.rglob('*.json')}
class Strip(ast.NodeTransformer):
 def visit_AnnAssign(self,n):
  return None if isinstance(n.target,ast.Name) and n.target.id=='usage_metadata' else self.generic_visit(n)
 def visit_Dict(self,n):
  pairs=[(k,v) for k,v in zip(n.keys,n.values) if not(isinstance(k,ast.Constant) and k.value=='usage_attempt_id')]
  n.keys=[k for k,v in pairs];n.values=[v for k,v in pairs]
  return self.generic_visit(n)
 def visit_ImportFrom(self,n):
  return None if n.module=='usage_observer' else n
 def visit_Call(self,n):
  self.generic_visit(n)
  if isinstance(n.func,ast.Name) and n.func.id=='call_with_usage':
   n.func=n.args[1]; n.args=n.args[2:];n.keywords=[k for k in n.keywords if k.arg not in {'usage_model','usage_kind','usage_identity','usage_metadata'}]
  return n

def run():
 proposal={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (REPO/'automation/scripts').glob('*.py')}
 result['proposal_sha256']=proposal
 oracle=json.loads((ROOT/'audit-work/usage-ledger.json').read_text())
 pricing={r['day']:r for r in json.loads((ROOT/'audit-work/recomputed-spend.json').read_text())}
 for n in [2,4,5]:
  date=f'2026-09-{n:02d}'; roots=[ROOT/f'audit-work/artifacts/day{n:02d}',ROOT/'ai-svodki-ia/automation/content'/date]
  before=treehash(roots); actual=usage_ledger.build_ledger(roots,date)
  old={r['response_id']:r for r in oracle if r['day']==date}
  now={r['response_id']:r for r in actual['records'] if r['kind']=='text'}
  check(f'{date}: response IDs and token evidence',old.keys()==now.keys() and all(now[k]['usage']==old[k]['usage'] for k in old), {'responses':len(now),'total_tokens':sum(r['usage']['total_tokens'] for r in now.values())})
  text_cost=sum(r['model_cost_estimate_usd'] for r in now.values())
  check(f'{date}: independent text price',abs(text_cost-pricing[date]['text_standard_short_estimate_USD'])<.000001, {'expected':pricing[date]['text_standard_short_estimate_USD'],'observed':round(text_cost,6)})
  check(f'{date}: complete observed records',actual['accounting_status']=='observed',actual['accounting_gaps'])
  again=usage_ledger.build_ledger(roots+roots,date)
  check(f'{date}: recovery copies unchanged',actual['unique_calls']==again['unique_calls'] and actual['estimated_observed_usd']==again['estimated_observed_usd'])
  check(f'{date}: inputs byte identical',before==treehash(roots),{'files':len(before)})
  (OUT/f'replay-{date}.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2))
 files=['primary_recall_search_v2.py','hybrid_search_completeness_v1.py','agency_discovery_rescue.py','ensure_story_coverage_policy.py','ensure_story_coverage_runtime_base.py','generate_digest_preview.py','generate_image_preview.py']
 for name in files:
  path='automation/scripts/'+name; previous=subprocess.check_output(['git','show',BASE+':'+path],cwd=REPO,text=True)
  check(name+': transport AST unchanged',ast.dump(ast.parse(previous))==ast.dump(Strip().visit(ast.parse((REPO/path).read_text()))))
 diff=subprocess.check_output(['git','diff','--name-only',BASE,'--','posts/','automation/content/'],cwd=REPO,text=True)
 check('Public content unchanged',not diff.strip())
 with tempfile.TemporaryDirectory(dir=OUT) as tmp:
  seen=[]; response={'id':'resp_check','model':'gpt-5.6-terra','usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}},'output':[]}
  def callback(**kwargs):seen.append(copy.deepcopy(kwargs)); return response
  kwargs={'model':'gpt-5.6-terra','input':'SENSITIVE TEST INPUT','store':False}
  with patch.dict(os.environ,{'AI_DIGEST_USAGE_DIR':tmp+'/usage-events','AI_DIGEST_PUBLICATION_DATE':'2026-09-05','GITHUB_RUN_ID':'offline-1'}):
   got=usage_observer.call_with_usage('editorial',callback,**kwargs)
   check('Transport arguments, identity and count',got is response and seen==[kwargs])
   try: json.loads('post-response invalid JSON')
   except ValueError: pass
   saved=usage_ledger.build_ledger([Path(tmp)],'2026-09-05')
   check('Usage survives late parsing error',saved['unique_calls']==1 and saved['stages']['editorial']['tokens_observed']['input_tokens']==100)
   error=TimeoutError('PRIVATE ERROR'); calls=[]
   def failed(**kw):calls.append(kw);raise error
   try:usage_observer.call_with_usage('hybrid',failed,model='gpt-5.6-terra')
   except TimeoutError as caught: check('Exception identity and no retry',caught is error and len(calls)==1)
   saved=usage_ledger.build_ledger([Path(tmp)],'2026-09-05')
   check('Timeout is an unknown charge',any('api_outcome_unknown' in r['accounting_gaps'] for r in saved['records']))
   (Path(tmp)/'coverage-audit.json').write_text('{truncated')
   check('Truncated evidence stays partial',usage_ledger.build_ledger([Path(tmp)],'2026-09-05')['accounting_status']=='partial')
   bad=Path(tmp)/'not-a-directory';bad.write_text('x')
   with patch.dict(os.environ,{'AI_DIGEST_USAGE_DIR':str(bad)}),contextlib.redirect_stderr(io.StringIO()):
    check('Unwritable accounting preserves paid response',usage_observer.call_with_usage('editorial',callback,**kwargs) is response)
 # Artificial resilience boundary, NOT the normal production generation path:
 # two distinct calls sharing a release identifier.
 # Missing provider IDs are allowed by the existing Images transport contract.
 with tempfile.TemporaryDirectory(dir=OUT) as tmp:
  calls=[]
  def image_callback(**kwargs):
   calls.append(kwargs)
   return {'created':1000+len(calls),'usage':{'input_tokens':20,'output_tokens':100,'total_tokens':120,'input_tokens_details':{'text_tokens':20,'image_tokens':0}}}
  with patch.dict(os.environ,{'AI_DIGEST_USAGE_DIR':tmp+'/usage-events','AI_DIGEST_PUBLICATION_DATE':'2026-09-05'}):
   for run_id in ['offline-first','offline-second']:
    with patch.dict(os.environ,{'GITHUB_RUN_ID':run_id}):
     usage_observer.call_with_usage('image',image_callback,usage_model='gpt-image-2',usage_kind='image',usage_identity='production-image-2026-09-05')
  saved=usage_ledger.build_ledger([Path(tmp)],'2026-09-05')
  journal=[json.loads(p.read_text()) for p in (Path(tmp)/'usage-events').glob('*.json')]
  details={'physical_stub_calls':len(calls),'journal_files':len(journal),'different_attempt_ids':len({r['attempt_id'] for r in journal}),'unique_image_calls':saved['stages']['image']['unique_calls'],'expected_image_estimate_usd':(20*5+100*30)/1000000*2,'observed_image_estimate_usd':saved['stages']['image']['estimated_observed_usd'],'image_accounting_status':saved['stages']['image']['accounting_status'],'accounting_gaps':[r['accounting_gaps'] for r in saved['records']]}
  (OUT/'image-two-attempts-evidence.json').write_text(json.dumps({'input_journal':journal,'output_ledger':saved,'comparison':details},ensure_ascii=False,indent=2))
  check('Separate image attempts never collapse into one charge',saved['stages']['image']['unique_calls']==2 and abs(saved['stages']['image']['estimated_observed_usd']-.0062)<1e-9,details)
 # Exercise the actual one-cover generator and actual saved-cover recovery.
 import base64, shutil
 import generate_image_preview as image_generator
 from materialize_cover_fixture import build_fixture_png
 from validate_cover_contract import validate_contract
 from recover_digest_artifact_v1_base import choose_reusable_image_source
 with tempfile.TemporaryDirectory(dir=OUT) as tmp:
  root=Path(tmp);date='2026-07-11';source=root/'source';output=root/'production-daily/image'/date
  shutil.copytree(REPO/'automation/fixtures/editorial'/date,source)
  config=REPO/'automation/config/image.json';cfg=json.loads(config.read_text())
  png=build_fixture_png(cfg['width'],cfg['height']);calls=[]
  def one_image(**kwargs):
   calls.append(kwargs)
   return {'created':1000,'usage':{'input_tokens':20,'output_tokens':100,'total_tokens':120,'input_tokens_details':{'text_tokens':20,'image_tokens':0}},'data':[{'b64_json':base64.b64encode(png).decode()}]}
  request=root/'request.json';request.write_text(json.dumps({'enabled':True,'mode':'image_api_preview','source':str(source),'publication_date':date,'request_id':'one-production-cover'}))
  with patch.dict(os.environ,{'AI_DIGEST_USAGE_DIR':str(root/'usage-events'),'AI_DIGEST_PUBLICATION_DATE':date}):
   image_generator.generate_image_artifact(source_dir=source,output_dir=output,request_path=request,config_path=config,api_key='offline-only',model='gpt-image-2',transport=one_image)
  check('Actual image generator: one call and n=1',len(calls)==1 and calls[0]['request_payload']['n']==1)
  validation=validate_contract(output,config)
  (output/'cover-validation.json').write_text(json.dumps(validation))
  check('Generated cover contract unchanged',validation['status']=='ok',validation.get('errors'))
  first=usage_ledger.build_ledger([root],date)
  check('Actual image journal plus report counted once',first['stages']['image']['unique_calls']==1 and abs(first['stages']['image']['estimated_observed_usd']-.0031)<1e-9)
  recovered,diagnostics=choose_reusable_image_source(root,date)
  check('Actual recovery selects paid cover without another call',recovered==output and len(calls)==1,diagnostics)
  shutil.copytree(output,root/'recovery-copy'/date)
  (root/'usage-ledger.json').write_text(json.dumps(first))
  second=usage_ledger.build_ledger([root],date)
  check('Recovered cover and saved ledger do not add a charge',second['stages']['image']['unique_calls']==1 and second['stages']['image']['estimated_observed_usd']==first['stages']['image']['estimated_observed_usd'])
  result['normal_cover_experiment']={'physical_stub_calls':len(calls),'n':calls[0]['request_payload']['n'],'image_calls_in_ledger':second['stages']['image']['unique_calls'],'recovery_found':recovered is not None}
 check('Proposal unchanged during acceptance',proposal=={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (REPO/'automation/scripts').glob('*.py')})
try:
 with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')):run()
 result['status']='passed'
except Exception as exc:
 result['status']='failed';result['stop_reason']=str(exc);result['error_type']=type(exc).__name__
finally:
 (OUT/'independent-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k!='proposal_sha256'},ensure_ascii=False,indent=2))
 sys.exit(0 if result['status']=='passed' else 1)
