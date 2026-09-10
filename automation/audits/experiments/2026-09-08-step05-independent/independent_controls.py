#!/usr/bin/env python3
"""Independent offline controls for Step 5 evidence attribution.

Imports the implementation read-only and writes a machine-readable result beside
this script. The controls deliberately use malformed or ambiguous saved
artifacts; they are not copies of repository unit tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path('/workspace/scratch/b0ff9bbd56a1/ai-svodki-step05')
sys.path.insert(0, str(REPO / 'automation/scripts'))
from source_pulse_value import build_report  # noqa: E402
from source_value_publication import verify_page  # noqa: E402

OUT = Path(__file__).with_name('independent_controls_result.json')
DATE = '2026-09-08'
URL = 'https://vendor.example/news?id=one'

def pulse(dispositions, accepted):
    return {
        'publication_date': DATE,
        'snapshot': {'sources': [{'source_id': 'vendor', 'status': 'ok'}]},
        'promotion': {'accepted_candidate_urls': accepted, 'lead_dispositions': dispositions},
    }

def bundle_with_null_identity():
    candidate = {
        'id': 'recycled', 'title': 'Pulse title', 'audit_direction': 'source_pulse_v12',
        'primary_source': {'url': URL}, 'organization': None, 'topic': None,
        'event_type': None, 'published_date': None, 'published_at': None,
        'source_freshness_status': 'fresh', 'event_freshness_status': 'unknown',
    }
    story = {
        'candidate_id': 'recycled', 'organization': None, 'topic': None,
        'event_type': None, 'published_date': None, 'published_at': None,
        'sources': [{'url': URL}],
    }
    return {
        'candidates': {'publication_date': DATE, 'candidates': [candidate]},
        'editorial': {'status': 'ok', 'digest': {'date': DATE},
                      'selected_candidate_ids': ['recycled'], 'excluded_candidate_ids': []},
        'stories': [story],
    }

cases = []
# 1. A malformed row is silently discarded although the artifact announces a
# complete disposition list. This converts unknown evidence into a downstream 0.
r = build_report(pulse(['not-a-disposition-object'], []))
row = r['sources'][0]
cases.append({
    'name': 'malformed_disposition_becomes_confirmed_zero',
    'observed': {'confirmed_promoted_count': row['confirmed_promoted_count'],
                 'promotion_evidence_complete': row['promotion_evidence_complete'],
                 'evidence_gaps': r['evidence_gaps']},
    'fails_control': row['confirmed_promoted_count'] == 0 and row['promotion_evidence_complete'] is True and not r['evidence_gaps'],
})
# 2. Duplicate accepted URLs and duplicate promoted dispositions are collapsed
# by set() and treated as complete source->candidate evidence.
r = build_report(pulse([
    {'source_id': 'vendor', 'promotion_status': 'promoted', 'url': URL},
    {'source_id': 'vendor', 'promotion_status': 'promoted', 'url': URL},
], [URL, URL]))
row = r['sources'][0]
cases.append({
    'name': 'duplicate_promotion_artifacts_are_accepted',
    'observed': {'confirmed_promoted_count': row['confirmed_promoted_count'],
                 'promotion_evidence_complete': row['promotion_evidence_complete'],
                 'evidence_gaps': r['evidence_gaps']},
    'fails_control': row['confirmed_promoted_count'] == 1 and row['promotion_evidence_complete'] is True and not r['evidence_gaps'],
})
# 3. A selected story with every identity field present-but-null is accepted as
# an exact story identity, hence assigns selection/assembly to the source.
p = pulse([{'source_id': 'vendor', 'promotion_status': 'promoted', 'url': URL, 'title': 'Pulse title'}], [URL])
r = build_report(p, bundle_with_null_identity())
row = r['sources'][0]
cases.append({
    'name': 'null_story_identity_is_counted_as_selected',
    'observed': {'editorial_selected': row['editorial_selected'], 'assembled_stories': row.get('assembled_stories'),
                 'candidate_trace': row['candidate_trace'], 'evidence_gaps': r['evidence_gaps']},
    'fails_control': row['editorial_selected'] == 1 and row.get('assembled_stories') == 1 and not r['evidence_gaps'],
})
# 4. Page validation accepts cross-wired headline/link pairs. It does not prove
# that each story's exact URL occurs in that story's committed content block.
stories = [
    {'headline': 'Story A', 'sources': [{'url': 'https://source.example/A'}]},
    {'headline': 'Story B', 'sources': [{'url': 'https://source.example/B'}]},
]
page = b'<h2>Story A</h2><a href="https://source.example/B">wrong A link</a><h2>Story B</h2><a href="https://source.example/A">wrong B link</a>'
try:
    verify_page(page, stories)
    accepted = True
except ValueError:
    accepted = False
cases.append({'name': 'page_story_source_association_is_not_verified', 'observed': {'cross_wired_page_accepted': accepted}, 'fails_control': accepted})

result = {'scope': 'offline independent controls only', 'cases': cases,
          'failed_controls': [c['name'] for c in cases if c['fails_control']]}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
