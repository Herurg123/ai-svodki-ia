#!/usr/bin/env python3
"""Inert baseline probes. No network or paid SDK calls; not a repaired-runtime test.

Inputs are immutable committed Sep11 content and the exact saved Coverage report.
Only Coverage's already-returned plan and editorial child are stubbed. Production
policy, merge/dedupe, snapshot rollback and merged-research restore execute locally.
Run against a baseline checkout; outputs describe bugs, not acceptance of a fix.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

BASE = '5d15b0f0a220f55a6753412b6e712fd2cd96b06a'
HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, default=HERE.parents[3])
parser.add_argument('--output', type=Path)
args = parser.parse_args()
ROOT = args.repo.resolve()
sys.path.insert(0, str(ROOT / 'automation/scripts'))
import ensure_story_coverage_policy as policy
import recover_digest_artifact_v1_base as recovery
import event_freshness
import source_pulse
import source_pulse_supplement_v12 as pulse12
import agency_discovery_rescue as agency
import agency_discovery_rescue_v5 as agency5
import primary_recall_search as primary


def committed(path):
    return subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT, stderr=subprocess.PIPE)


def read_content(name, day='2026-09-11'):
    return json.loads(committed(f'automation/content/{day}/{name}'))


saved = json.loads((HERE / 'saved-coverage-final.json').read_text())
plan = copy.deepcopy(saved)
plan['candidates'] = [copy.deepcopy(c) for d in saved['directions'] for c in d.get('candidates', [])]
result = {'baseline': BASE, 'scope': 'offline baseline diagnostics; no fix acceptance', 'paid_calls': 0, 'network_calls': 0}


def coverage_probe():
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        artifact = temp / 'artifact'
        artifact.mkdir()
        for name in ['candidates.json', 'stories.json', 'digest.json', 'meta.json', 'editorial-output.json', 'editorial-output-raw.json', 'run-info.json', 'primary-recall.json']:
            (artifact / name).write_bytes(committed('automation/content/2026-09-11/' + name))
        archive = temp / 'archive.json'
        archive.write_bytes(committed('automation/archive/index.json'))
        report = temp / 'production-daily/coverage-audit.json'
        original = (artifact / 'editorial-output-raw.json').read_bytes()
        child_calls = []

        def fail_after_response(**kwargs):
            child_calls.append(str(kwargs['merged_research_path']))
            (artifact / 'editorial-output-raw.json').write_text('{"simulated_paid_response": true}')
            raise RuntimeError('offline simulated validation failure after a response')

        argv = ['coverage', '--artifact-dir', str(artifact), '--archive', str(archive), '--publication-date', '2026-09-11', '--model', 'gpt-5.6-terra', '--report', str(report)]
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(policy, 'RUNTIME_RESEARCH_ROOT', temp / 'runtime'))
            stack.enter_context(mock.patch.object(policy, 'PERSISTED_RESEARCH_ROOT', report.parent))
            stack.enter_context(mock.patch.object(policy, 'execute_audit_plan', side_effect=lambda **kw: copy.deepcopy(plan)))
            stack.enter_context(mock.patch.object(policy, 'rerun_editorial', side_effect=fail_after_response))
            stack.enter_context(mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-unused'}))
            stack.enter_context(mock.patch.object(sys, 'argv', argv))
            stack.enter_context(mock.patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            first_rc = policy.main()
            first = json.loads(report.read_text())
            paid_response_replaced_by_old = (artifact / 'editorial-output-raw.json').read_bytes() == original
            restored = recovery.restore_merged_coverage_research(temp, artifact, '2026-09-11')
            before_second = len(child_calls)
            second_rc = policy.main()
            second = json.loads(report.read_text())
        return {
            'first': {'rc': first_rc, **{k: first.get(k) for k in ['status', 'mode', 'audit_added_candidates', 'editorial_rerun_required', 'editorial_rerun_performed']}},
            'simulated_new_response_lost_to_rollback': paid_response_replaced_by_old,
            'merged_research_restored': restored is not None,
            'second': {'rc': second_rc, 'new_editorial_child_calls': len(child_calls)-before_second, **{k: second.get(k) for k in ['status', 'mode', 'audit_added_candidates', 'editorial_rerun_required', 'editorial_rerun_performed']}},
            'scope': 'actual policy + merge + restore; saved completed plan injected; child validation failure simulated, no model invoked',
        }


result['coverage'] = coverage_probe()

# A fixed-feed snapshot with no parsed rows is incorrectly marked complete.
src = source_pulse.SourceDefinition('probe_official', 'A', 'global', 'official', 'html', 'https://example.com/news', ('example.com',))
start = datetime.fromisoformat('2026-09-10T01:04:18+00:00')
end = datetime.fromisoformat('2026-09-11T01:05:09+00:00')
snap = pulse12.run_source_pulse_v12(registry=[src], start_at=start, end_at=end, fetcher=lambda u,h: source_pulse.FetchOutcome(u,u,'ok',200,'<html><div id="app"></div></html>',None,0), fetched_at=end)
result['empty_parser_health'] = {'summary': snap['summary'], 'source': snap['sources'][0]}

# Generic RSS parser conflates updated and published. Such leads are not a proof.
xml = '<feed><entry><title>Old AI article</title><id>https://example.com/old</id><updated>2026-09-10T12:00:00Z</updated></entry></feed>'
item = source_pulse.parse_rss(xml, 'https://example.com/feed')[0]
result['updated_only_feed'] = {'published_at': item.published_at.isoformat(), 'source_item_id': item.source_item_id}

p = read_content('primary-recall.json')
china = next(c for d in p['directions'] for c in d.get('raw_candidates', []) if 'AP датирует реакцию Китая средой' in str(c.get('event_date_evidence')))
window = read_content('candidates.json')['search_window']
event = event_freshness.evaluate_candidate(china, start_at=datetime.fromisoformat(window['start_at']), end_at=datetime.fromisoformat(window['end_at']))
result['weekday_conflict'] = {'event_date': china['event_date'], 'calendar_weekday': datetime.fromisoformat(china['event_date']).strftime('%A'), 'evidence': china['event_date_evidence'], 'baseline_status': event.status}
weak = [{'direction_id': d['direction_id'], 'model_rejections': [c for c in d.get('model_rejections', []) if c.get('reason_code')=='weak_source' and 'deepseek' in str(c).lower()]} for d in p['directions']]
result['weak_source_signal'] = {'rejections': [c for d in weak for c in d['model_rejections']], 'unresolved_signals': primary.collect_unresolved_signals(weak)}

# Capture real transport kwargs with an SDK-shaped fake. This proves construction
# and extraction only; provider behavior and recall cannot be inferred from it.
class Obj(SimpleNamespace):
    def model_dump(self):
        return {k: v.model_dump() if hasattr(v, 'model_dump') else v for k,v in vars(self).items()}

request_rows=[]
for sources in [None, [], [{'url':'https://www.reuters.com/example', 'title':'Example'}]]:
    response = Obj(id='offline', status='completed', model='gpt-5.6-terra', usage=None, error=None, incomplete_details=None, output=[Obj(type='web_search_call', id='ws-offline', status='completed', action=Obj(type='search', query=agency.AGENCY_DISCOVERY_RESCUE_QUERY, sources=sources))], output_text=json.dumps({'direction_id': agency.AGENCY_DISCOVERY_RESCUE_DIRECTION, 'status':'complete_with_gaps', 'candidates':[], 'rejections':[]}))
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return response
    sdk = SimpleNamespace(OpenAI=lambda **kw: SimpleNamespace(responses=SimpleNamespace(create=create)))
    with mock.patch.dict(sys.modules, {'openai': sdk}), mock.patch.object(agency, 'call_with_usage', side_effect=lambda stage, fn, **kw: fn(**kw)):
        _, metadata = agency.run_search_request(api_key='offline', model='gpt-5.6-terra', prompt='offline')
    request_rows.append({'input_sources': sources, 'include':captured['include'], 'tools':captured['tools'], 'max_tool_calls':captured['max_tool_calls'], 'metadata':agency5.source_metadata_state(metadata), 'consulted_sources':metadata['consulted_sources']})
result['agency_wire_and_metadata'] = request_rows
result['agency_history'] = []
for day in range(6,12):
    date = f'2026-09-{day:02}'
    try:
        a = read_content('agency-discovery-rescue.json',date)
    except subprocess.CalledProcessError:
        result['agency_history'].append({'date':date,'availability':'missing_committed_report'})
        continue
    result['agency_history'].append({'date':date, **{k:a.get(k) for k in ['state','raw_count','validated_count','added_count','source_metadata_available']}})
text = json.dumps(result,ensure_ascii=False,indent=2)+'\n'
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
print(text)
