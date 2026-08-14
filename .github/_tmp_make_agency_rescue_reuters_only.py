from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'marker not found in {path}: {old!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

p=Path('automation/scripts/ensure_story_coverage.py')
text=p.read_text(encoding='utf-8')
repls={
    'AGENCY_RESCUE_VERSION = 2':'AGENCY_RESCUE_VERSION = 3',
    'AGENCY_RESCUE_DOMAINS: tuple[str, ...] = ("reuters.com", "apnews.com")':'AGENCY_RESCUE_DOMAINS: tuple[str, ...] = ("reuters.com",)',
    '"label": "Fresh Reuters/AP source-health rescue v2"':'"label": "Fresh Reuters source-health rescue v3"',
    'ИИ-событий из Reuters/AP, которых НЕТ в текущем пуле. API domain filter уже\nограничен Reuters и AP.':'ИИ-событий из Reuters, которых НЕТ в текущем пуле. API domain filter уже\nограничен Reuters.',
}
for old,new in repls.items():
    if old not in text:
        raise SystemExit(f'ensure_story_coverage marker missing: {old!r}')
    text=text.replace(old,new,1)
p.write_text(text,encoding='utf-8')

replace_once('automation/scripts/ensure_story_coverage_policy.py','SOURCE_HEALTH_CONTRACT_VERSION = 2','SOURCE_HEALTH_CONTRACT_VERSION = 3')

p=Path('automation/tests/test_agency_rescue.py')
text=p.read_text(encoding='utf-8')
text=text.replace('self.assertEqual(tuple(call["allowed_domains"]), runtime.AGENCY_RESCUE_DOMAINS)', 'self.assertEqual(tuple(call["allowed_domains"]), ("reuters.com",))', 1)
p.write_text(text,encoding='utf-8')

for path in ('README.md','automation/README.md','AGENTS.md'):
    p=Path(path)
    text=p.read_text(encoding='utf-8')
    old='с API domain filter только на\nReuters + AP. Bloomberg/FT уже имеют отдельный `major_agencies` шанс в Primary.'
    new='с API domain filter только на\nReuters. AP остаётся допустимой agency evidence, если её находят другие research-слои; Bloomberg/FT уже имеют отдельный `major_agencies` шанс в Primary.'
    if old not in text:
        raise SystemExit(f'doc route marker missing in {path}')
    text=text.replace(old,new,1)
    p.write_text(text,encoding='utf-8')

Path('.github/_tmp_make_agency_rescue_reuters_only.py').unlink()
