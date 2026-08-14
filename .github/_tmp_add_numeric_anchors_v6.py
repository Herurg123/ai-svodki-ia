from pathlib import Path

p=Path('automation/scripts/ensure_story_coverage.py')
text=p.read_text(encoding='utf-8')
text=text.replace('import copy\nimport json\n', 'import copy\nimport json\nimport re\n',1)
text=text.replace('AGENCY_RESCUE_VERSION = 5','AGENCY_RESCUE_VERSION = 6',1)
old='''def _agency_corroboration_query(target: dict[str, Any]) -> str:\n    organization = str(target.get("organization") or "").split(";", 1)[0].strip()\n    organization = " ".join(organization.split())\n    event_type = " ".join(str(target.get("event_type") or "").split())\n    organization_cf = organization.casefold()\n    event_cf = event_type.casefold()\n    keyword = ""\n    for raw_keyword in target.get("keywords") or []:\n        candidate = " ".join(str(raw_keyword).split())\n        if not candidate:\n            continue\n        candidate_cf = candidate.casefold()\n        if candidate_cf == organization_cf or candidate_cf == event_cf:\n            continue\n        if candidate_cf in organization_cf or candidate_cf in event_cf:\n            continue\n        keyword = candidate\n        break\n    parts = ["Reuters", organization, event_type]\n    if keyword:\n        parts.append(keyword)\n    parts.append("latest")\n    return " ".join(part for part in parts if part).strip()\n'''
new=r'''def _money_anchors(target: dict[str, Any]) -> list[str]:
    """Extract distinctive monetary facts from the event title before generic terms."""
    title = str(target.get("title") or "")
    anchors: list[str] = []
    patterns = (
        (r"\$\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:млрд|billion)\b", "billion"),
        (r"\$\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:млн|million)\b", "million"),
        (r"\$\s*([0-9]+(?:[.,][0-9]+)?)\s*B\b", "billion"),
        (r"\$\s*([0-9]+(?:[.,][0-9]+)?)\s*M\b", "million"),
    )
    for pattern, unit in patterns:
        for match in re.finditer(pattern, title, flags=re.IGNORECASE):
            value = match.group(1).replace(",", ".")
            rendered = f"${value} {unit}"
            if rendered not in anchors:
                anchors.append(rendered)
    return anchors[:2]


def _agency_corroboration_query(target: dict[str, Any]) -> str:
    organization = str(target.get("organization") or "").split(";", 1)[0].strip()
    organization = " ".join(organization.split())
    anchors = _money_anchors(target)
    if anchors:
        return " ".join(["Reuters", organization, *anchors]).strip()

    event_type = " ".join(str(target.get("event_type") or "").split())
    organization_cf = organization.casefold()
    event_cf = event_type.casefold()
    keyword = ""
    for raw_keyword in target.get("keywords") or []:
        candidate = " ".join(str(raw_keyword).split())
        if not candidate:
            continue
        candidate_cf = candidate.casefold()
        if candidate_cf == organization_cf or candidate_cf == event_cf:
            continue
        if candidate_cf in organization_cf or candidate_cf in event_cf:
            continue
        keyword = candidate
        break
    parts = ["Reuters", organization, event_type]
    if keyword:
        parts.append(keyword)
    parts.append("latest")
    return " ".join(part for part in parts if part).strip()
'''
if old not in text: raise SystemExit('query function marker missing')
text=text.replace(old,new,1)
p.write_text(text,encoding='utf-8')

p=Path('automation/scripts/ensure_story_coverage_policy.py')
text=p.read_text(encoding='utf-8').replace('SOURCE_HEALTH_CONTRACT_VERSION = 5','SOURCE_HEALTH_CONTRACT_VERSION = 6',1)
p.write_text(text,encoding='utf-8')

p=Path('automation/tests/test_agency_corroboration.py')
text=p.read_text(encoding='utf-8')
text=text.replace('''            keywords=["Databricks", "funding", "valuation", "enterprise AI"],\n        )\n        self.assertEqual(\n            runtime._agency_corroboration_query(target),\n            "Reuters Databricks funding valuation latest",\n        )\n''','''            keywords=["Databricks", "funding", "valuation", "enterprise AI"],\n        )\n        target["title"] = "Databricks раскрыла раунд на $5 млрд при оценке $190 млрд"\n        self.assertEqual(runtime._money_anchors(target), ["$5 billion", "$190 billion"])\n        self.assertEqual(\n            runtime._agency_corroboration_query(target),\n            "Reuters Databricks $5 billion $190 billion",\n        )\n''',1)
p.write_text(text,encoding='utf-8')

for path in ('README.md','automation/README.md','AGENTS.md'):
 p=Path(path); text=p.read_text(encoding='utf-8')
 text=text.replace('`fresh_agency_rescue` **v5**','`fresh_agency_rescue` **v6**',1)
 old='строит короткий date-free query из `organization + event_type +\nkeyword` с `Reuters` как ranking hint'
 new='строит короткий date-free query с `Reuters` как ranking hint; для денежных событий он прежде всего использует отличительные monetary anchors прямо из заголовка (`organization + сумма + valuation`), а при их отсутствии откатывается к `organization + event_type + keyword`'
 if old not in text: raise SystemExit(f'doc marker missing {path}')
 text=text.replace(old,new,1)
 p.write_text(text,encoding='utf-8')
Path('.github/_tmp_add_numeric_anchors_v6.py').unlink()
