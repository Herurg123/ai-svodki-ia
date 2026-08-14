from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:180]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Coverage wrapper: turn the seventh-slot source-health rescue into targeted
# corroboration of one already-known strong event, rather than another broad
# discovery lottery. Exactly one search remains allowed.
# ---------------------------------------------------------------------------
p = Path("automation/scripts/ensure_story_coverage.py")
text = p.read_text(encoding="utf-8")
text = text.replace("AGENCY_RESCUE_VERSION = 4", "AGENCY_RESCUE_VERSION = 5", 1)

start = text.index("def build_agency_rescue_prompt(\n")
end = text.index("\ndef _existing_agency_rescue(", start)
new_block = r'''def _candidate_id(candidate: Any) -> str | None:
    if not isinstance(candidate, dict):
        return None
    value = candidate.get("id", candidate.get("candidate_id"))
    return str(value) if value is not None else None


def _select_agency_corroboration_target(
    candidates: list[Any],
) -> dict[str, Any] | None:
    """Choose one strong, agency-likely current event for last-mile corroboration."""
    event_priority = {
        "funding": 0,
        "funding_round": 0,
        "acquisition": 0,
        "merger": 0,
        "m&a": 0,
        "investment": 1,
        "data_center": 1,
        "infrastructure": 1,
        "partnership": 2,
    }
    eligible: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        if raw.get("recommendation") not in {"include", "consider"}:
            continue
        if _candidate_id(raw) is None:
            continue
        event_type = str(raw.get("event_type") or "").casefold().strip()
        category = str(raw.get("category") or "").casefold().strip()
        priority = event_priority.get(event_type)
        if priority is None and category in {"investment", "infrastructure", "chips"}:
            priority = 1
        if priority is None:
            continue
        item = copy.deepcopy(raw)
        item["_agency_target_priority"] = priority
        eligible.append(item)
    if not eligible:
        return None
    eligible.sort(
        key=lambda item: (
            int(item.get("_agency_target_priority", 99)),
            0 if item.get("recommendation") == "include" else 1,
            -int(item.get("significance_score", 0) or 0),
            str(item.get("published_date") or ""),
            str(item.get("title") or ""),
        )
    )
    target = eligible[0]
    target.pop("_agency_target_priority", None)
    return target


def _agency_corroboration_query(target: dict[str, Any]) -> str:
    organization = str(target.get("organization") or "").split(";", 1)[0].strip()
    organization = " ".join(organization.split())
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


def _same_event_for_corroboration(
    target: dict[str, Any], candidate: dict[str, Any]
) -> bool:
    """Deterministic guard against attaching an agency story to a different event."""
    return bool(
        str(candidate.get("organization") or "").casefold().strip()
        == str(target.get("organization") or "").casefold().strip()
        and str(candidate.get("event_type") or "").casefold().strip()
        == str(target.get("event_type") or "").casefold().strip()
        and str(candidate.get("published_date") or "")
        == str(target.get("published_date") or "")
    )


def build_agency_rescue_prompt(
    *,
    search_window: dict[str, Any],
    target: dict[str, Any],
    archive: dict[str, Any],
) -> str:
    start_at = str(search_window.get("start_at") or "")
    end_at = str(search_window.get("end_at") or "")
    required_query = _agency_corroboration_query(target)
    compact_target = {
        "id": _candidate_id(target),
        "title": target.get("title"),
        "organization": target.get("organization"),
        "published_date": target.get("published_date"),
        "published_at": target.get("published_at"),
        "event_type": target.get("event_type"),
        "category": target.get("category"),
        "keywords": target.get("keywords"),
        "event_summary": target.get("event_summary"),
        "primary_source": target.get("primary_source"),
    }
    return f"""Ты — last-mile agency corroboration редакции «ИИ-сводки».

Строгое редакционное окно: {start_at} → {end_at}
Авторитетное текущее время: {end_at}.
Идентификатор направления: general_coverage_gaps
Версия rescue: {AGENCY_RESCUE_VERSION}

Primary, Hybrid и шесть обязательных Coverage-проходов уже дали ненулевой пул,
но в нём нет свежего Reuters/AP/Bloomberg/FT primary source. Свободен ровно один,
седьмой Coverage search operation. НЕ ищи новое произвольное событие. Твоя
задача — независимо подтвердить РОВНО ЭТО уже найденное событие сильным agency
источником, предпочтительно Reuters.

Выполни РОВНО ОДИН Web Search. API domain filter намеренно отключён, потому что
live-smoke показал слепоту Reuters allowed_domains. Фактический query должен быть
точно:
`{required_query}`

Верни не больше ОДНОГО кандидата. Он должен описывать то же событие, что target,
а поля `organization`, `event_type` и `published_date` должны ТОЧНО совпадать с
target. `primary_source.url` обязан вести непосредственно на Reuters/AP/
Bloomberg/FT, не на синдикацию, агрегатор или вторичное СМИ. Источник должен быть
внутри editorial window. Если такого подтверждения нет, верни пустой candidates
и status=complete_with_gaps. Не придумывай timestamp или факты.

Target для подтверждения:
{json.dumps(compact_target, ensure_ascii=False, indent=2)}

Недавний архив для контекста:
{json.dumps(_base._compact_recent_archive(archive), ensure_ascii=False, indent=2)}

Для include/consider обязательны verification_status=verified и
freshness_status=new_event/material_update. `direction_id` строго
`general_coverage_gaps`. Верни только JSON по схеме."""


def _normalize_agency_rescue_candidate(
    candidate: dict[str, Any], *, target_id: str
) -> dict[str, Any]:
    normalized = copy.deepcopy(candidate)
    normalized["audit_direction"] = "agency_rescue"
    normalized["corroboration_target_id"] = target_id
    if normalized.get("category") != "legal":
        normalized["legal_scale"] = "not_applicable"
        normalized["legal_scale_reason"] = ""
    return normalized

'''
text = text[:start] + new_block + text[end:]

# Replace the broad v4 run body with targeted corroboration.
old = '''    prompt = build_agency_rescue_prompt(\n        search_window=search_window,\n        existing_candidates=existing_candidates,\n        archive=archive,\n    )\n'''
new = '''    target = _select_agency_corroboration_target(existing_candidates)\n    if target is None:\n        _set_last_agency_rescue(\n            {\n                "status": "error",\n                "version": AGENCY_RESCUE_VERSION,\n                "search_strategy": AGENCY_RESCUE_STRATEGY,\n                "error": "no suitable corroboration target in current pool",\n            }\n        )\n        plan["audit_status"] = "partial"\n        budget["stop_reason"] = "agency_corroboration_target_missing"\n        return plan\n    target_id = _candidate_id(target)\n    assert target_id is not None\n    required_query = _agency_corroboration_query(target)\n    prompt = build_agency_rescue_prompt(\n        search_window=search_window,\n        target=target,\n        archive=archive,\n    )\n'''
if old not in text:
    raise SystemExit("old build_agency_rescue_prompt call missing")
text = text.replace(old, new, 1)
old = '''    accepted_for_pass = [\n        _normalize_agency_rescue_candidate(item)\n        for item in raw_candidates\n        if isinstance(item, dict)\n        and _policy._candidate_has_fresh_agency_source(item, search_window)\n    ] if isinstance(raw_candidates, list) else []\n'''
new = '''    accepted_for_pass = [\n        _normalize_agency_rescue_candidate(item, target_id=target_id)\n        for item in raw_candidates\n        if isinstance(item, dict)\n        and _policy._candidate_has_fresh_agency_source(item, search_window)\n        and _same_event_for_corroboration(target, item)\n    ] if isinstance(raw_candidates, list) else []\n    if len(accepted_for_pass) > 1:\n        accepted_for_pass = accepted_for_pass[:1]\n'''
if old not in text:
    raise SystemExit("old agency accepted_for_pass missing")
text = text.replace(old, new, 1)
text = text.replace(
    '"label": "Fresh agency source-health rescue v4",',
    '"label": "Targeted fresh-agency corroboration v5",',
    1,
)
text = text.replace(
    '"allowed_domains": list(AGENCY_RESCUE_DOMAINS),\n        "prompt": prompt,',
    '"allowed_domains": list(AGENCY_RESCUE_DOMAINS),\n        "corroboration_target_id": target_id,\n        "corroboration_target_title": target.get("title"),\n        "required_query": required_query,\n        "prompt": prompt,',
    1,
)
# Save target diagnostics in the top-level rescue summary too.
text = text.replace(
    '"attempt": attempt_number,\n            "actual_queries": record["actual_queries"],',
    '"attempt": attempt_number,\n            "corroboration_target_id": target_id,\n            "corroboration_target_title": target.get("title"),\n            "required_query": required_query,\n            "actual_queries": record["actual_queries"],',
    1,
)
p.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Policy: promote the independently corroborated agency source onto the existing
# event instead of appending a duplicate candidate. This is source repair, not
# story-count inflation.
# ---------------------------------------------------------------------------
p = Path("automation/scripts/ensure_story_coverage_policy.py")
text = p.read_text(encoding="utf-8")
text = text.replace("SOURCE_HEALTH_CONTRACT_VERSION = 4", "SOURCE_HEALTH_CONTRACT_VERSION = 5", 1)
insert_marker = '''def rerun_editorial(\n'''
helper = r'''def apply_agency_corroborations(
    research: dict[str, Any],
    additional_candidates: list[Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Any]]:
    """Promote agency evidence onto an existing event without duplicating it."""
    merged = copy.deepcopy(research)
    candidates = merged.get("candidates")
    if not isinstance(candidates, list):
        raise RuntimeError("candidates.json: candidates должен быть массивом")
    by_id = {
        str(item.get("id")): item
        for item in candidates
        if isinstance(item, dict) and item.get("id") is not None
    }
    details: list[dict[str, Any]] = []
    remaining: list[Any] = []
    for raw in additional_candidates:
        if not isinstance(raw, dict) or not raw.get("corroboration_target_id"):
            remaining.append(raw)
            continue
        target_id = str(raw.get("corroboration_target_id"))
        target = by_id.get(target_id)
        if not isinstance(target, dict):
            remaining.append(raw)
            continue
        agency_primary = raw.get("primary_source")
        old_primary = target.get("primary_source")
        if not isinstance(agency_primary, dict) or not isinstance(old_primary, dict):
            remaining.append(raw)
            continue
        agency_url = str(agency_primary.get("url") or "")
        old_url = str(old_primary.get("url") or "")
        if not agency_url:
            remaining.append(raw)
            continue
        supporting = [
            copy.deepcopy(item)
            for item in target.get("supporting_sources") or []
            if isinstance(item, dict)
        ]
        known_urls = {str(item.get("url") or "") for item in supporting}
        if old_url and old_url != agency_url and old_url not in known_urls:
            supporting.insert(0, copy.deepcopy(old_primary))
        for item in raw.get("supporting_sources") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            if url and url != agency_url and url not in {str(x.get("url") or "") for x in supporting}:
                supporting.append(copy.deepcopy(item))
        target["primary_source"] = copy.deepcopy(agency_primary)
        target["supporting_sources"] = supporting[:2]
        target["source_type"] = str(raw.get("source_type") or "news_agency")
        original_notes = str(target.get("verification_notes") or "").strip()
        agency_publisher = str(agency_primary.get("publisher") or "agency")
        suffix = f"Fresh-agency corroboration: {agency_publisher}."
        target["verification_notes"] = (
            f"{original_notes} {suffix}".strip() if original_notes else suffix
        )
        details.append(
            {
                "target_id": target_id,
                "target_title": target.get("title"),
                "old_primary_source": copy.deepcopy(old_primary),
                "new_primary_source": copy.deepcopy(agency_primary),
                "audit_direction": raw.get("audit_direction"),
            }
        )
    return merged, details, remaining


'''
if insert_marker not in text:
    raise SystemExit("rerun_editorial marker missing")
text = text.replace(insert_marker, helper + insert_marker, 1)
# Add report fields.
text = text.replace(
    '"audit_added_candidates": 0,\n        "editorial_rerun_required": False,',
    '"audit_added_candidates": 0,\n        "source_corroboration_count": 0,\n        "source_corroborations": [],\n        "editorial_rerun_required": False,',
    1,
)
# Replace merge stage.
old = '''        if additional_candidates:\n            merged, accepted, rejected = merge_candidates(\n                research,\n                additional_candidates,\n                maximum_candidates=args.maximum_candidates,\n            )\n        else:\n            merged = copy.deepcopy(research)\n            accepted = []\n            rejected = []\n'''
new = '''        corroborated_research, source_corroborations, remaining_candidates = (\n            apply_agency_corroborations(research, additional_candidates)\n        )\n        report["source_corroborations"] = source_corroborations\n        report["source_corroboration_count"] = len(source_corroborations)\n        if remaining_candidates:\n            merged, accepted, rejected = merge_candidates(\n                corroborated_research,\n                remaining_candidates,\n                maximum_candidates=args.maximum_candidates,\n            )\n        else:\n            merged = copy.deepcopy(corroborated_research)\n            accepted = []\n            rejected = []\n'''
if old not in text:
    raise SystemExit("merge stage marker missing")
text = text.replace(old, new, 1)
text = text.replace(
    'report["editorial_rerun_required"] = bool(accepted)',
    'report["editorial_rerun_required"] = bool(accepted or source_corroborations)',
    1,
)
text = text.replace(
    'and not accepted\n        ):',
    'and not accepted\n            and not source_corroborations\n        ):',
    1,
)
# Do not restore the source-unhealthy old snapshot if source corroboration was
# required but the editorial rerun fails or becomes empty.
text = text.replace(
    'if initial_snapshot and before["publication_allowed"]:\n                restore_artifact(args.artifact_dir, initial_snapshot)',
    'if initial_snapshot and before["publication_allowed"] and not source_corroborations:\n                restore_artifact(args.artifact_dir, initial_snapshot)',
    1,
)
text = text.replace(
    'if initial_snapshot and before["publication_allowed"]:\n                restore_artifact(args.artifact_dir, initial_snapshot)',
    'if initial_snapshot and before["publication_allowed"] and not source_corroborations:\n                restore_artifact(args.artifact_dir, initial_snapshot)',
    1,
)
text = text.replace(
    'report["editorial_rerun_performed"] = bool(accepted)',
    'report["editorial_rerun_performed"] = bool(accepted or source_corroborations)',
    1,
)
p.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Tests: target selection, generated query, same-event guard, source promotion,
# no duplicate event, and no broad-domain filter dependency.
# ---------------------------------------------------------------------------
Path("automation/tests/test_agency_corroboration.py").write_text(r'''from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_module("agency_corroboration_runtime", SCRIPTS / "ensure_story_coverage.py")
policy = runtime._policy


def candidate(
    cid: str,
    organization: str,
    event_type: str,
    score: int,
    *,
    category: str = "investment",
    primary_url: str = "https://techcrunch.com/2026/08/13/example/",
    keywords: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": cid,
        "title": f"{organization} event",
        "organization": organization,
        "published_date": "2026-08-13",
        "published_at": "2026-08-13T12:00:00+00:00",
        "time_precision": "datetime",
        "topic": "AI",
        "event_type": event_type,
        "keywords": keywords or [organization, event_type, "valuation"],
        "geography": "world",
        "category": category,
        "source_type": "technology_media",
        "primary_source": {"title": "Original", "publisher": "TechCrunch", "url": primary_url},
        "supporting_sources": [],
        "event_summary": "Fresh event.",
        "verified_facts": ["Fact one.", "Fact two."],
        "significance": "Major event.",
        "significance_score": score,
        "limitations": "",
        "archive_status": "none",
        "archive_reason": "Not in archive.",
        "recommendation": "include",
        "verification_status": "verified",
        "verification_notes": "Initial verification.",
        "freshness_status": "new_event",
        "freshness_reason": "Inside window.",
        "legal_scale": "not_applicable",
        "legal_scale_reason": "",
        "curiosity_eligible": False,
        "curiosity_verification": "",
    }


class AgencyCorroborationTests(unittest.TestCase):
    def test_target_selection_prefers_high_score_funding_over_partnership(self):
        pool = [
            candidate("cand-001", "Anthropic", "research publication", 5, category="security"),
            candidate("cand-003", "Databricks", "funding", 5),
            candidate("cand-004", "IBM; OpenAI", "partnership", 5, category="enterprise"),
            candidate("cand-005", "Thrive Holdings", "funding", 4),
        ]
        target = runtime._select_agency_corroboration_target(pool)
        self.assertIsNotNone(target)
        self.assertEqual(target["id"], "cand-003")

    def test_databricks_query_is_short_date_free_and_adaptive(self):
        target = candidate(
            "cand-003",
            "Databricks",
            "funding",
            5,
            keywords=["Databricks", "funding", "valuation", "enterprise AI"],
        )
        self.assertEqual(
            runtime._agency_corroboration_query(target),
            "Reuters Databricks funding valuation latest",
        )
        self.assertNotIn("2026", runtime._agency_corroboration_query(target))

    def test_same_event_guard_requires_org_event_and_date(self):
        target = candidate("cand-003", "Databricks", "funding", 5)
        confirmed = copy.deepcopy(target)
        confirmed["primary_source"] = {
            "title": "Reuters confirmation",
            "publisher": "Reuters",
            "url": "https://www.reuters.com/business/databricks-funding-2026-08-13/",
        }
        self.assertTrue(runtime._same_event_for_corroboration(target, confirmed))
        wrong = copy.deepcopy(confirmed)
        wrong["organization"] = "Another Company"
        self.assertFalse(runtime._same_event_for_corroboration(target, wrong))
        wrong = copy.deepcopy(confirmed)
        wrong["published_date"] = "2026-08-12"
        self.assertFalse(runtime._same_event_for_corroboration(target, wrong))

    def test_source_promotion_replaces_primary_without_duplicating_event(self):
        target = candidate("cand-003", "Databricks", "funding", 5)
        research = {"search_window": {}, "candidates": [target]}
        corroboration = copy.deepcopy(target)
        corroboration["corroboration_target_id"] = "cand-003"
        corroboration["audit_direction"] = "agency_rescue"
        corroboration["source_type"] = "news_agency"
        corroboration["primary_source"] = {
            "title": "Databricks raises $5 billion",
            "publisher": "Reuters",
            "url": "https://www.reuters.com/technology/databricks-raises-5-billion-2026-08-13/",
        }
        merged, details, remaining = policy.apply_agency_corroborations(
            research, [corroboration]
        )
        self.assertEqual(len(merged["candidates"]), 1)
        promoted = merged["candidates"][0]
        self.assertEqual(promoted["id"], "cand-003")
        self.assertEqual(promoted["primary_source"]["publisher"], "Reuters")
        self.assertEqual(promoted["supporting_sources"][0]["publisher"], "TechCrunch")
        self.assertEqual(promoted["source_type"], "news_agency")
        self.assertEqual(len(details), 1)
        self.assertEqual(remaining, [])

    def test_non_corroboration_candidate_is_left_for_normal_merge(self):
        research = {"candidates": [candidate("cand-003", "Databricks", "funding", 5)]}
        ordinary = candidate("", "Other", "funding", 4)
        ordinary.pop("id")
        merged, details, remaining = policy.apply_agency_corroborations(research, [ordinary])
        self.assertEqual(len(merged["candidates"]), 1)
        self.assertEqual(details, [])
        self.assertEqual(remaining, [ordinary])


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

# Retire the earlier broad-rescue tests: their premise is intentionally replaced
# by targeted corroboration v5. Keep one contract assertion in the new file.
old_test = Path("automation/tests/test_agency_rescue.py")
if old_test.exists():
    old_test.unlink()

# ---------------------------------------------------------------------------
# Docs: describe targeted corroboration, not broad seventh-slot discovery.
# ---------------------------------------------------------------------------
for path in ("README.md", "automation/README.md", "AGENTS.md"):
    p = Path(path)
    value = p.read_text(encoding="utf-8")
    heading = "### Fresh-agency source-health rescue"
    start = value.find(heading)
    if start < 0:
        raise SystemExit(f"source-health rescue heading missing in {path}")
    next_heading = value.find("\n### ", start + len(heading))
    end = next_heading if next_heading >= 0 else len(value)
    replacement = r'''### Fresh-agency source-health rescue

Ненулевой candidate pool не считается автоматически здоровым только потому, что
он содержит достаточно сюжетов. Если после Primary/Hybrid и шести обязательных
Coverage-направлений в current validated pool нет ни одного свежего
Reuters/AP/Bloomberg/FT primary source, свободный **седьмой** Coverage search
operation используется как bounded `fresh_agency_rescue` **v5** для targeted
corroboration уже найденного сильного события.

Rescue детерминированно выбирает наиболее agency-likely high-significance
кандидат (сначала funding/M&A, затем investment/infrastructure, затем
partnership), строит короткий date-free query из `organization + event_type +
keyword` с `Reuters` как ranking hint и выполняет ровно один Web Search **без API
domain filter**. Отказ от `allowed_domains` здесь намеренный: live recovery-smoke
14 августа показал, что Reuters domain-lock способен вернуть пустую выдачу, хотя
тот же индекс без lock видит актуальный Reuters материал.

После retrieval acceptance остаётся жёстким: corroboration должен иметь прямой
primary URL Reuters/AP/Bloomberg/FT, находиться внутри effective window и точно
совпадать с target по `organization`, `event_type` и `published_date`. Успешное
подтверждение **не добавляет второй сюжет**: agency source повышается до
`primary_source` существующего candidate, прежний primary переезжает в
`supporting_sources`, после чего editorial rerun пересобирает ссылки выпуска.
Если корректного подтверждения нет, source-health остаётся fail-closed.

Для нулевого пула тот же седьмой слот по-прежнему занят source-neutral recall
sentinel v8. Режимы взаимоисключающие, поэтому общий worst-case budget не растёт:
**12 Primary + до 4 Hybrid + до 7 Coverage = максимум 23 search operations**.
Legacy-выпуски без `primary-recall.json` сохраняют прежнюю recovery-совместимость.
'''
    value = value[:start] + replacement.rstrip() + "\n" + value[end:]
    p.write_text(value, encoding="utf-8")

Path(".github/_tmp_apply_targeted_corroboration_v5.py").unlink()
