"""Offline independent replay and adjacent controls for run 34298397080."""
import copy
import hashlib
import importlib.util
import json
import sys
import types
import subprocess
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TEMP = tempfile.TemporaryDirectory(prefix='editorial-regional-control-')
EVIDENCE = Path(TEMP.name)
FIXTURE = REPO / 'automation/fixtures/recall/2026-09-09-editorial-regional-stop.json'
BASE_SHA = 'd3ed784ec8a9f3450d723e2565b3ab1509d0facf'
BASELINE_SOURCE = EVIDENCE / 'generate_digest_preview_baseline.py'
BASELINE_SOURCE.write_bytes(subprocess.check_output(['git', 'show', BASE_SHA + ':automation/scripts/generate_digest_preview.py'], cwd=REPO))
sys.path.insert(0, str(REPO / 'automation/scripts'))
if 'openai' not in sys.modules:
    stub = types.ModuleType('openai')
    stub.OpenAI = object
    sys.modules['openai'] = stub

import generate_digest_preview as candidate  # noqa: E402
from editorial_policy_runtime import patch_editorial_policy, patch_editorial_source_validation  # noqa: E402


def load_baseline():
    spec = importlib.util.spec_from_file_location('baseline_preview_independent', BASELINE_SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest_sha(editorial):
    return hashlib.sha256(canonical(editorial['digest']).encode()).hexdigest()


saved = json.loads(FIXTURE.read_text(encoding='utf-8'))
policy = json.loads((REPO / 'automation/config/editorial.json').read_text(encoding='utf-8'))
archive_bytes = subprocess.check_output(['git', 'show', BASE_SHA + ':automation/archive/index.json'], cwd=REPO)
assert hashlib.sha256(archive_bytes).hexdigest() == saved['provenance']['original_input_sha256']['archive']
full_archive = json.loads(archive_bytes)

patch_editorial_policy(candidate)
patch_editorial_source_validation(candidate)
baseline = load_baseline()
patch_editorial_policy(baseline)
patch_editorial_source_validation(baseline)


def validate(module, research, editorial, archive=None):
    return module.validate_editorial(
        editorial, research, date(2026, 9, 9), saved['site_config'],
        saved['archive'] if archive is None else archive, policy, 7, 12,
    )

results = {}
# Exact saved production input, with the full baseline archive and production hour override.
for name, module in [('baseline', baseline), ('candidate', candidate)]:
    research = copy.deepcopy(saved['research'])
    editorial = copy.deepcopy(saved['editorial'])
    before = canonical([research, editorial])
    errors, warnings, stories = validate(module, research, editorial, full_archive)
    results[f'{name}_exact_replay'] = {
        'errors': errors, 'warnings': warnings, 'story_count': len(stories),
        'inputs_unchanged': canonical([research, editorial]) == before,
        'digest_sha256': digest_sha(editorial),
    }
assert results['baseline_exact_replay']['errors'] == [
    'В пуле есть достойные российские кандидаты, но ни один не выбран.'
]
assert results['candidate_exact_replay']['errors'] == []
assert any('cand-008' in item for item in results['candidate_exact_replay']['warnings'])
assert results['candidate_exact_replay']['story_count'] == 7
assert results['candidate_exact_replay']['inputs_unchanged']
assert results['baseline_exact_replay']['digest_sha256'] == results['candidate_exact_replay']['digest_sha256']

# Selected regional story: keep all normal validation invariants, while the regional condition must not warn.
research = copy.deepcopy(saved['research']); editorial = copy.deepcopy(saved['editorial'])
research['candidates'][0]['geography'] = 'russia'
research['candidates'][-1]['geography'] = 'world'
editorial['digest']['article_html'] = editorial['digest']['article_html'].replace(
    '<h3>Cognition привлекла более $2 млрд при оценке $48 млрд</h3>',
    '<h2>Российские лидеры ИИ</h2><h3>Cognition привлекла более $2 млрд при оценке $48 млрд</h3>', 1,
)
errors, warnings, stories = validate(candidate, research, editorial)
results['selected_regional'] = {'errors': errors, 'warnings': warnings, 'story_count': len(stories)}
assert errors == [] and not any('региональная квота' in item for item in warnings)

# Excluded high-score regional lead remains a non-blocking diagnostic with the exact ID.
research = copy.deepcopy(saved['research']); editorial = copy.deepcopy(saved['editorial'])
errors, warnings, stories = validate(candidate, research, editorial)
results['excluded_high_score_regional'] = {'errors': errors, 'warnings': warnings, 'story_count': len(stories)}
assert errors == [] and any('cand-008' in item for item in warnings)

# Weak and stale/excluded regional candidates produce no quota diagnostic and do not change selection.
for name, patch in [
    ('weak_regional', {'recommendation': 'consider', 'significance_score': 2}),
    ('stale_excluded_regional', {'recommendation': 'exclude', 'significance_score': 3, 'freshness_status': 'stale'}),
]:
    research = copy.deepcopy(saved['research']); editorial = copy.deepcopy(saved['editorial'])
    research['candidates'][-1].update(patch)
    errors, warnings, stories = validate(candidate, research, editorial)
    results[name] = {'errors': errors, 'warnings': warnings, 'story_count': len(stories)}
    assert errors == [] and not any('региональная квота' in item for item in warnings)

# Existing hard validation remains intact: all candidates excluded, unknown IDs, diversity and HTML provenance.
research = copy.deepcopy(saved['research']); editorial = copy.deepcopy(saved['editorial'])
editorial['selected_candidate_ids'] = []
editorial['excluded_candidate_ids'] = [row['id'] for row in research['candidates']]
errors, warnings, stories = validate(candidate, research, editorial)
results['all_excluded'] = {'errors': errors, 'warnings': warnings, 'story_count': len(stories)}
assert any('ни одного достойного сюжета' in item for item in errors)

research = copy.deepcopy(saved['research']); editorial = copy.deepcopy(saved['editorial'])
editorial['selected_candidate_ids'].append('unknown')
errors, warnings, stories = validate(candidate, research, editorial)
results['unknown_id'] = {'errors': errors, 'warnings': warnings, 'story_count': len(stories)}
assert any('неизвестные candidate ID' in item for item in errors)

research = copy.deepcopy(saved['research']); editorial = copy.deepcopy(saved['editorial'])
editorial['diversity_overrides'] = []
errors, warnings, stories = validate(candidate, research, editorial)
results['diversity_unchanged'] = {'errors': errors, 'warnings': warnings, 'story_count': len(stories)}
assert any('diversity override' in item for item in errors)

research = copy.deepcopy(saved['research']); editorial = copy.deepcopy(saved['editorial'])
editorial['digest']['article_html'] = editorial['digest']['article_html'].replace(
    'https://cognition.com/blog/series-e', 'https://unrelated.example/not-a-source', 1,
)
errors, warnings, stories = validate(candidate, research, editorial)
results['html_provenance_unchanged'] = {'errors': errors, 'warnings': warnings, 'story_count': len(stories)}
assert errors

results['provenance'] = {
    'run_id': saved['provenance']['run_id'],
    'base_sha': saved['provenance']['head_sha'],
    'fixture_zip_sha256': saved['provenance']['zip_sha256'],
    'fixture_research_sha256': saved['provenance']['original_input_sha256']['research'],
    'fixture_editorial_sha256': saved['provenance']['original_input_sha256']['editorial'],
    'full_archive_sha256': hashlib.sha256(archive_bytes).hexdigest(),
}
print(json.dumps(results, ensure_ascii=False, indent=2))
