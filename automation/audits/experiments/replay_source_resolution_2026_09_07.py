"""Isolated baseline/proposal replay; known-alternative control is not live search."""
import argparse
import copy
import hashlib
import json
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'automation/fixtures/recall/source-resolution-daybreak-2026-09-05.json'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def worker(root):
    sys.path.insert(0, str(root / 'automation/scripts'))
    import source_freshness as source
    import ensure_story_coverage as coverage
    import primary_recall_search as primary
    fixture = json.loads(FIXTURE.read_text())
    window = fixture['primary']['search_window']
    start, end = (datetime.fromisoformat(window[key]) for key in ('start_at', 'end_at'))
    result = {'matrix': {}, 'network_calls': 0, 'paid_api_calls': 0}
    with tempfile.TemporaryDirectory() as raw:
        temporary = Path(raw)
        diag = temporary / 'automation/preview/production-daily'; diag.mkdir(parents=True)
        (diag / 'primary-recall-2026-09-05.json').write_text(json.dumps(fixture['primary']))
        (diag / 'source-freshness-2026-09-05.json').write_text(json.dumps(fixture['source_freshness']))
        with patch.object(coverage, 'REPOSITORY_ROOT', temporary):
            leads = coverage._required_signals('2026-09-05')
        result['required_titles'] = [item['title'] for item in leads]
        result['source_url_preserved'] = bool(leads and fixture['daybreak']['primary_source']['url'] in coverage.build_resolution_prompt(search_window=window, cluster=leads, archive={}))
    candidate = copy.deepcopy(fixture['daybreak'])
    def blocked(url): raise source.SourceFreshnessError('HTTP Error 403: Forbidden')
    record = source.verify_candidate(candidate, start_at=start, end_at=end, fetcher=blocked)
    result['original_403'] = {'candidate': candidate, 'status': record['status']}
    alternative = copy.deepcopy(fixture['daybreak'])
    alternative['primary_source'] = {'publisher': 'OpenAI', 'title': 'Daybreak for Frontline Defenders', 'url': fixture['official_url']}
    calls = []
    def official(url):
        calls.append(url)
        if url == fixture['official_url']:
            return fixture['official_proof']['html_extract'], url, 200
        if url == 'https://openai.com/news/rss.xml':
            return fixture['official_proof']['rss_extract'], url, 200
        raise AssertionError('unexpected source: ' + url)
    record = source.verify_candidate(alternative, start_at=start, end_at=end, fetcher=official)
    result['known_alternative'] = {'status': record['status'], 'recommendation': alternative['recommendation'],
                                  'published_at': alternative['published_at'], 'calls': calls}
    for count in (0, 1, 3, 6, 12, 25):
        for region in ('world', 'russia', 'asia'):
            for state in ('fresh', 'stale', 'undated', 'blocked'):
                for reverse in (False, True):
                    rows = []
                    for index in range(count):
                        item = copy.deepcopy(fixture['daybreak'])
                        item.update(id=str(index), geography=region, recommendation=('include', 'consider', 'exclude')[index % 3])
                        item['primary_source']['url'] = 'https://example.org/shared-' + str(index % 2)
                        if index % 5 == 4:
                            item.update(event_date='2026-08-01', event_at='2026-08-01T12:00:00Z', event_time_precision='datetime')
                        rows.append(item)
                    if reverse: rows.reverse()
                    fetches = []
                    def fetch(url):
                        fetches.append(url)
                        if state == 'blocked': raise source.SourceFreshnessError('HTTP 403')
                        html = '<h1>No date</h1>' if state == 'undated' else '<meta property="article:published_time" content="' + ('2026-09-04' if state == 'fresh' else '2026-08-01') + 'T12:00:00Z">'
                        return html, url, 200
                    output, report = source.verify_research_payload({'search_window': window, 'candidates': rows}, fetcher=fetch)
                    for item in report['candidates']: item.pop('candidate_evidence', None)
                    key = f'{count}/{region}/{state}/{reverse}'
                    result['matrix'][key] = fingerprint([output, report, fetches])
    attempts = [{'direction_id': direction, 'attempt': 1, 'status': 'checked',
                 'api': {'status': 'completed', 'web_search_calls_completed': 1, 'web_search_call_items_total': 1}}
                for direction in coverage.AUDIT_DIRECTION_IDS]
    attempts.append({'direction_id': 'general_coverage_gaps', 'attempt': 2, 'status': 'checked',
                     'search_strategy': coverage.AGENCY_RESCUE_STRATEGY,
                     'api': {'status': 'completed', 'web_search_calls_completed': 1}})
    prior = {'attempts': attempts, 'directions': attempts[:6], 'checked_directions': list(coverage.AUDIT_DIRECTION_IDS),
             'search_budget': {'maximum_calls': 7, 'completed_calls': 7, 'remaining_calls': 0}}
    prepared = coverage._prepare_prior_for_quality(prior)
    result['migration'] = {'attempts': len(prepared['attempts']), 'budget': prepared['search_budget']}
    result['regions'] = {}
    for asia, russia in ((0, 0), (0, 1), (1, 0), (1, 1)):
        lanes = [{'direction_id': key, 'status': 'complete', 'accepted_count': value}
                 for key, value in [('china_asia_models', asia), ('china_asia_integrations', asia), ('russia', russia)]]
        result['regions'][f'{asia}/{russia}'] = primary.regional_health(lanes)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--baseline-root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.worker:
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
            print(json.dumps(worker(args.worker.resolve()), ensure_ascii=False))
        return
    baseline_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.baseline_root, text=True).strip()
    if baseline_sha != 'b474b06bc00f365b9737ece4dd0912c1892489e7': raise RuntimeError('wrong baseline')
    outputs = [json.loads(subprocess.check_output([sys.executable, __file__, '--worker', str(root)], text=True))
               for root in (args.baseline_root, ROOT)]
    old, new = outputs
    checks = []
    def check(name, passed): checks.append({'name': name, 'passed': bool(passed)})
    check('original Axios 403 stays excluded with identical candidate payload', old['original_403'] == new['original_403'] and new['original_403']['status'] == 'excluded_unverified_freshness')
    check('baseline has no required Daybreak signal', old['required_titles'] == [])
    check('proposal has exactly Daybreak, not obsolete May news', len(new['required_titles']) == 1 and 'Daybreak' in new['required_titles'][0] and new['source_url_preserved'])
    check('known alternative fails old parser', old['known_alternative']['status'] == 'excluded_unverified_freshness')
    check('known alternative gains exact source proof', new['known_alternative']['status'] == 'verified_fresh' and new['known_alternative']['published_at'] == '2026-09-03T13:15:00+00:00')
    check('one extra public RSS fetch, zero paid operations', len(new['known_alternative']['calls']) == 2 and old['paid_api_calls'] == new['paid_api_calls'] == 0)
    for key, value in old['matrix'].items(): check('unchanged source matrix ' + key, new['matrix'][key] == value)
    for key, value in old['regions'].items(): check('unchanged regional health ' + key, new['regions'][key] == value)
    check('migration no longer erases an already paid slot', old['migration']['attempts'] == 6 and new['migration']['attempts'] == 7 and new['migration']['budget']['remaining_calls'] == 0)
    result = {'status': 'passed' if all(item['passed'] for item in checks) else 'failed',
              'baseline': baseline_sha, 'checks': checks, 'count': len(checks), 'matrix_cases': len(new['matrix']),
              'network_calls_during_replay': 0, 'paid_api_calls': 0,
              'limitation': 'Known-alternative control is manually supplied. Terra discovery/selection and final independent architecture acceptance are not performed.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'checks'}, ensure_ascii=False))
    if result['status'] != 'passed': raise SystemExit(1)


if __name__ == '__main__': main()
