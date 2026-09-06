"""Independent lossless-context replay. Requires offline openai 2.45.0/tiktoken."""
import argparse
import hashlib
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ap = argparse.ArgumentParser()
ap.add_argument('--evidence-root', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
repo = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo / 'automation/scripts'))
import prompt_context as proposed
import generate_digest_preview as editor
import ensure_story_coverage_policy as coverage
import httpx
import openai
import tiktoken

BASE = '03474ed5493a52fce32cca29b72343ba6fc7ed68'
enc = tiktoken.get_encoding('o200k_base')
result = {'status': 'running', 'baseline': BASE, 'checks': [], 'editorial_days': [],
          'production_api_calls': 0, 'limitations': ['Offline token proxy; no live cache or stochastic output comparison.']}

def check(name, ok):
    result['checks'].append({'name': name, 'passed': bool(ok)})
    if not ok:
        raise AssertionError(name)

def region(text, name):
    return re.search(r'=== '+name+r'_BEGIN ===\s*(.*?)\s*=== '+name+r'_END ===', text, re.S).group(1)

def run():
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (repo/'automation/scripts').glob('*.py')}
    for day in range(1, 6):
        date = f'2026-09-{day:02d}'
        source = a.evidence_root / f'audit-work/artifacts/day{day:02d}/{date}/editorial-prompt-input.txt'
        before = source.read_text()
        template = before
        values = {}
        for name in ['ARCHIVE_CONTEXT', 'CANDIDATES_CONTEXT', 'EDITORIAL_POLICY']:
            raw = region(before, name)
            values[name] = json.loads(raw)
            template = template.replace(raw, '{{'+name+'}}', 1)
        after = editor.build_prompt(template, {k: proposed.compact_json(v) for k, v in values.items()})
        check(date+' exact objects, arrays and strings', all(json.loads(region(after,k)) == v for k,v in values.items()))
        strip = lambda s: re.sub(r'(=== (?:ARCHIVE_CONTEXT|CANDIDATES_CONTEXT|EDITORIAL_POLICY)_BEGIN ===).*?(=== (?:ARCHIVE_CONTEXT|CANDIDATES_CONTEXT|EDITORIAL_POLICY)_END ===)', r'\1 DATA \2', s, flags=re.S)
        check(date+' unchanged instructions', strip(before)==strip(after))
        bt, at = len(enc.encode(before)), len(enc.encode(after))
        check(date+' smaller characters and tokens', len(after)<len(before) and at<bt)
        req = proposed.editorial_input(after, 'gpt-5.6-terra')
        blocks = req['input'][0]['content']
        check(date+' exact transport text', ''.join(b['text'] for b in blocks)==after)
        check(date+' prefix excludes candidates', '=== CANDIDATES_CONTEXT_BEGIN ===' not in blocks[0]['text'])
        changed = after.replace(region(after,'CANDIDATES_CONTEXT'), '[]', 1)
        check(date+' stable shared prefix', proposed.editorial_input(changed,'gpt-5.6-terra')['input'][0]['content'][0]==blocks[0])
        result['editorial_days'].append({'date':date,'before_chars':len(before),'after_chars':len(after),
                                       'before_tokens':bt,'after_tokens':at,'token_reduction_percent':round(100*(bt-at)/bt,2)})
        check(date+' source unchanged', source.read_text()==before)

    baseline = {'__file__': str(repo/'automation/scripts/ensure_story_coverage_policy.py'), '__name__':'baseline_coverage'}
    text = subprocess.check_output(['git','show',BASE+':automation/scripts/ensure_story_coverage_policy.py'],cwd=repo,text=True)
    exec(compile(text,'baseline_coverage','exec'),baseline)
    template = (repo/'automation/prompts/coverage_audit.md').read_text()
    cases = 0
    for count in [0,1,3,6,12,25]:
        for geography in ['world','russia','asia']:
            for status in ['include','consider','exclude']:
                rows = [{'title':f'Событие {i}', 'organization':'Same organization', 'geography':geography,
                         'recommendation':status,'published_at':None if i%2 else '2026-09-05T23:30:00-07:00',
                         'primary_source':{'url':'https://example.test/shared','nested':{}},
                         'description':'Пробелы  внутри\nстрок и }} скобки'} for i in range(count)]
                kwargs = dict(publication_date='2026-09-06', search_window={'start_at':'2026-09-04T06:00:00+03:00','end_at':'2026-09-06T06:00:00+03:00'}, missing_total=max(0,7-count),maximum_web_search_calls=7,existing_candidates=rows,archive={'items':[]})
                # The baseline's broad brace guard rejects literal }} even in
                # valid strings; compare baseline on the same otherwise exact rows.
                for row in rows:
                    row['description']='Пробелы  внутри\nстрок'
                before = baseline['build_prompt'](template, **kwargs)
                after = coverage.build_prompt(template, **kwargs)
                for name in ['EXISTING_CANDIDATES','ARCHIVE_INDEX']:
                    check(f'coverage {cases} {name}',json.loads(region(before,name))==json.loads(region(after,name)))
                clean = lambda s: re.sub(r'(=== (?:EXISTING_CANDIDATES|ARCHIVE_INDEX)_BEGIN ===).*?(=== (?:EXISTING_CANDIDATES|ARCHIVE_INDEX)_END ===)',r'\1 DATA \2',s,flags=re.S)
                check(f'coverage {cases} instructions',clean(before)==clean(after))
                cases += 1
    result['coverage_cases'] = cases
    sent = []
    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'resp_offline','object':'response','created_at':0,'status':'completed','model':'gpt-5.6-terra','output':[]})
    client = openai.OpenAI(api_key='offline-stub', max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    prompt = 'same archive === ARCHIVE_CONTEXT_END === different candidates'
    client.responses.create(model='gpt-5.6-terra', **proposed.editorial_input(prompt,'gpt-5.6-terra'), store=False)
    check('production SDK version',openai.__version__=='2.45.0')
    check('one offline wire request',len(sent)==1)
    check('wire full-message caching retained',sent[0]['prompt_cache_options']=={'mode':'implicit'})
    check('wire archive breakpoint retained',sent[0]['input'][0]['content'][0]['prompt_cache_breakpoint']=={'mode':'explicit'})
    check('wire identical text and role',len(sent[0]['input'])==1 and sent[0]['input'][0]['role']=='user' and ''.join(x['text'] for x in sent[0]['input'][0]['content'])==prompt)
    # Same token rates per input token under documented partition accounting.
    # Keeping full implicit caching avoids the explicit-only exact-repeat loss.
    for row in result['editorial_days']:
        for rate,label in [(2.5,'cold writes'),(.2,'exact warm repeats'),(2,'uncached')]:
            check(row['date']+' '+label,row['after_tokens']*rate<row['before_tokens']*rate)
    check('proposal unchanged',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in hashes.items()))
    check('public and recovery code unchanged',not subprocess.check_output(['git','diff','--name-only',BASE,'--','posts','automation/content','automation/scripts/recover_digest_artifact.py','automation/scripts/recover_digest_artifact_v1_base.py'],cwd=repo,text=True).strip())

try:
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
        run()
    result['status']='passed'
except Exception as exc:
    result.update(status='failed', reason=str(exc))
finally:
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
    sys.exit(0 if result['status']=='passed' else 1)
