"""Isolated zero-network diagnostic A/B; not Terra or independent acceptance.

Usage: python replay_step04_evidence_draft.py BASELINE_SCRIPTS PROPOSED_SCRIPTS
Inputs are synthetic controls using historical instants, not recovered articles.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

cases = []
for code in ('unverified', 'outside_window', 'duplicate'):
    for timestamp in ('2026-09-04T09:21:00-07:00', '2026-09-04T07:47:00-07:00', '2026-09-06T00:00:00+03:00', None):
        cases.append({'title': 'Nvidia OpenAI $3 billion investment', 'reason_code': code,
                      'reason': 'Reuters investment; synthetic disputed-facts control',
                      'url': 'https://example.org/control', 'published_at': timestamp,
                      'time_precision': 'datetime' if timestamp else 'unknown',
                      'date_evidence': timestamp})
window = {'start_at': '2026-09-03T03:58:49+03:00', 'end_at': '2026-09-05T03:57:22+03:00'}
code = '''import json,sys
import primary_recall_search as p
x=json.load(sys.stdin)
r={'directions':[{'direction_id':'control','model_rejections':x['cases']}], 'search_window':x['window']}
print(json.dumps(p._annotate({},r)[1]['unresolved_signals']))
'''
outputs = []
for scripts in sys.argv[1:3]:
    result = subprocess.run([sys.executable, '-c', code], input=json.dumps({'cases':cases,'window':window}),
        text=True, capture_output=True, check=True, env=dict(os.environ, PYTHONPATH=str(Path(scripts).resolve())))
    outputs.append(json.loads(result.stdout))
baseline, proposed = outputs
assert len(baseline) == 4 and len(proposed) == 8
assert all('url' not in row for row in baseline)
assert all(row['url'] == 'https://example.org/control' for row in proposed)
assert all(row['rejection_evidence']['published_at'] == cases[int(row['signal_id'].rsplit('-',1)[1])-1]['published_at'] for row in proposed)
assert sum(row['resolution_required'] for row in baseline) == 4
assert sum(row['resolution_required'] for row in proposed) == 7
assert not any('recommendation' in row for row in proposed)
print(json.dumps({'status':'diagnostic_pass_not_acceptance', 'controlled_inputs':12,
    'baseline_retained':4,'proposed_retained':8,'baseline_urls':0,'proposed_urls':8,
    'baseline_required':4,'proposed_required':7,'paid_calls':0,
    'live_terra_experiment':'not_available','independent_acceptance':'not_completed'},indent=2))
