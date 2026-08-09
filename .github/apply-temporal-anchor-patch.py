from pathlib import Path

ROOT = Path('.')


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'missing patch anchor in {path}: {old[:120]!r}')
    if text.count(old) != 1:
        raise SystemExit(f'non-unique patch anchor in {path}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


def append_once(path: str, marker: str, block: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if marker in text:
        return
    p.write_text(text.rstrip() + '\n\n' + block.strip() + '\n', encoding='utf-8')


replace_once(
    'automation/prompts/research_candidates.md',
    'Дата выпуска: {{CURRENT_DATE}}\nТочное редакционное окно: {{SEARCH_WINDOW_START_AT}} → {{SEARCH_WINDOW_END_AT}}\n',
    'Дата выпуска: {{CURRENT_DATE}}\nТочное редакционное окно: {{SEARCH_WINDOW_START_AT}} → {{SEARCH_WINDOW_END_AT}}\n'
    'Авторитетное текущее время этой исследовательской задачи: {{SEARCH_WINDOW_END_AT}}.\n'
    'Считай эту отметку фактическим «сейчас» независимо от системной даты модели,\n'
    'UTC-даты запуска API или календарной даты среды исполнения. Любой timestamp,\n'
    'который не позже {{SEARCH_WINDOW_END_AT}}, не является будущим. Не ищи события\n'
    'позже этой границы.\n',
)
replace_once(
    'automation/prompts/coverage_audit.md',
    'Дата выпуска: {{PUBLICATION_DATE}}\nСтрогое редакционное окно: {{SEARCH_WINDOW_START_AT}} → {{SEARCH_WINDOW_END_AT}}\n',
    'Дата выпуска: {{PUBLICATION_DATE}}\nСтрогое редакционное окно: {{SEARCH_WINDOW_START_AT}} → {{SEARCH_WINDOW_END_AT}}\n'
    'Авторитетное текущее время этого audit-прохода: {{SEARCH_WINDOW_END_AT}}.\n'
    'Считай эту отметку фактическим «сейчас» независимо от системной даты модели,\n'
    'UTC-даты запуска API или календарной даты среды исполнения. Любой timestamp,\n'
    'который не позже {{SEARCH_WINDOW_END_AT}}, не является будущим. Не ищи события\n'
    'позже этой границы.\n',
)

replace_once(
    'automation/scripts/generate_digest_preview.py',
    'DEFAULT_MAXIMUM_RESEARCH_WEB_SEARCH_CALLS = 12\n',
    'DEFAULT_MAXIMUM_RESEARCH_WEB_SEARCH_CALLS = 12\nTEMPORAL_ANCHOR_VERSION = 1\n',
)
replace_once(
    'automation/scripts/generate_digest_preview.py',
    '        run_info["research"]["prompt_sha256"] = sha256_text(research_prompt)\n',
    '        run_info["research"]["temporal_anchor_version"] = TEMPORAL_ANCHOR_VERSION\n'
    '        run_info["research"]["prompt_sha256"] = sha256_text(research_prompt)\n',
)

replace_once(
    'automation/scripts/recover_digest_artifact.py',
    'from datetime import datetime\n',
    'from datetime import datetime, timezone\n',
)
replace_once(
    'automation/scripts/recover_digest_artifact.py',
    'IMAGE_RECOVERY_REQUIRED = (\n',
    'TEMPORAL_ANCHOR_VERSION = 1\n\nIMAGE_RECOVERY_REQUIRED = (\n',
)
replace_once(
    'automation/scripts/recover_digest_artifact.py',
    'def research_is_reusable(source_dir: Path) -> tuple[bool, str | None]:\n',
    '''def _legacy_cross_midnight_research(candidates: dict[str, Any]) -> bool:
    search_window = candidates.get("search_window")
    if not isinstance(search_window, dict):
        return False
    end_at = search_window.get("end_at")
    if not isinstance(end_at, str) or not end_at.strip():
        return False
    try:
        parsed = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    return parsed.date() > parsed.astimezone(timezone.utc).date()


def research_is_reusable(source_dir: Path) -> tuple[bool, str | None]:
''',
)
replace_once(
    'automation/scripts/recover_digest_artifact.py',
    '''    if not isinstance(candidates, dict) or not isinstance(candidates.get("candidates"), list):
        return False, "candidates.json не содержит candidates[]"
    return True, None
''',
    '''    if not isinstance(candidates, dict) or not isinstance(candidates.get("candidates"), list):
        return False, "candidates.json не содержит candidates[]"
    temporal_version = research.get("temporal_anchor_version")
    if (
        temporal_version != TEMPORAL_ANCHOR_VERSION
        and _legacy_cross_midnight_research(candidates)
    ):
        return (
            False,
            "legacy cross-midnight research не содержит авторитетный temporal anchor",
        )
    return True, None
''',
)

replace_once(
    'automation/scripts/ensure_story_coverage.py',
    'RECALL_SENTINEL_VERSION = 6\n',
    'TEMPORAL_ANCHOR_VERSION = 1\nRECALL_SENTINEL_VERSION = 7\n',
)
replace_once(
    'automation/scripts/ensure_story_coverage.py',
    'def _prepare_prior_plan(prior_plan: dict[str, Any] | None) -> dict[str, Any] | None:\n',
    '''def _legacy_cross_midnight_window(search_window: dict[str, Any] | None) -> bool:
    if not isinstance(search_window, dict):
        return False
    end_at = search_window.get("end_at")
    if not isinstance(end_at, str) or not end_at.strip():
        return False
    try:
        parsed = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    return parsed.date() > parsed.astimezone(timezone.utc).date()


def _prepare_prior_plan(
    prior_plan: dict[str, Any] | None,
    search_window: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
''',
)
replace_once(
    'automation/scripts/ensure_story_coverage.py',
    '''    if not isinstance(prior_plan, dict):
        return prior_plan

    prepared = copy.deepcopy(prior_plan)
''',
    '''    if not isinstance(prior_plan, dict):
        return prior_plan
    if (
        prior_plan.get("temporal_anchor_version") != TEMPORAL_ANCHOR_VERSION
        and _legacy_cross_midnight_window(search_window)
    ):
        return None

    prepared = copy.deepcopy(prior_plan)
''',
)
replace_once(
    'automation/scripts/ensure_story_coverage.py',
    '    prepared_prior = _prepare_prior_plan(prior_plan)\n',
    '    prepared_prior = _prepare_prior_plan(prior_plan, search_window)\n',
)
replace_once(
    'automation/scripts/ensure_story_coverage.py',
    '''    plan = globals()["_BASE_EXECUTE_AUDIT_PLAN"](
        api_key=api_key,
        model=model,
        template=template,
        publication_date=publication_date,
        search_window=search_window,
        missing_total=missing_total,
        maximum_web_search_calls=maximum_web_search_calls,
        existing_candidates=existing_candidates,
        archive=archive,
        prior_plan=prepared_prior,
    )

    existing_sentinel = _existing_recall_sentinel(plan)
''',
    '''    plan = globals()["_BASE_EXECUTE_AUDIT_PLAN"](
        api_key=api_key,
        model=model,
        template=template,
        publication_date=publication_date,
        search_window=search_window,
        missing_total=missing_total,
        maximum_web_search_calls=maximum_web_search_calls,
        existing_candidates=existing_candidates,
        archive=archive,
        prior_plan=prepared_prior,
    )
    plan["temporal_anchor_version"] = TEMPORAL_ANCHOR_VERSION

    existing_sentinel = _existing_recall_sentinel(plan)
''',
)
replace_once(
    'automation/scripts/ensure_story_coverage.py',
    'Строгое редакционное окно: {start_at} → {end_at}\nИдентификатор направления: general_coverage_gaps\n',
    'Строгое редакционное окно: {start_at} → {end_at}\n'
    'Авторитетное текущее время этого sentinel-прохода: {end_at}.\n'
    'Считай эту отметку фактическим «сейчас» независимо от системной даты модели,\n'
    'UTC-даты запуска API или календарной даты среды исполнения. Любой timestamp,\n'
    'который не позже {end_at}, не является будущим. Не ищи события позже этой границы.\n'
    'Идентификатор направления: general_coverage_gaps\n',
)

replace_once(
    'automation/scripts/ensure_story_coverage_policy.py',
    '''                        "attempts",
                        "search_budget",
                        "time_precision_warnings",
                        "api",
''',
    '''                        "attempts",
                        "search_budget",
                        "time_precision_warnings",
                        "api",
                        "temporal_anchor_version",
''',
)
replace_once(
    'automation/scripts/ensure_story_coverage_policy.py',
    '''        elif report["audit_needed"] and prior_complete:
            report["prior_audit_reused"] = True
''',
    '''        elif report["audit_needed"] and prior_complete:
            report["prior_audit_reused"] = True
            report["temporal_anchor_version"] = (prior_report or {}).get(
                "temporal_anchor_version"
            )
''',
)

replace_once(
    '.github/workflows/daily-production.yml',
    '''          terminal = (
              data.get("status") == "error"
''',
    '''          temporal_anchor_current = (
              data.get("temporal_anchor_version") == 1
              and (data.get("recall_sentinel") or {}).get("version") == 7
          )
          terminal = (
              temporal_anchor_current
              and data.get("status") == "error"
''',
)

append_once(
    'README.md',
    '## Временной контракт research и recovery',
    '''## Временной контракт research и recovery

Ночные запуски происходят около 02:17 МСК, когда в UTC ещё может быть предыдущий
календарный день. Поэтому `search_window.end_at` является авторитетным текущим
временем задачи для основного research, всех coverage-проходов и recall sentinel.
Модель обязана считать всё до этой отметки не будущим независимо от собственной
системной даты или UTC-даты API-запуска.

Контракт версионируется. Recovery не переиспользует legacy research без текущей
версии temporal anchor, если локальная дата конца окна уже опережает UTC-дату.
Для такого кросс-полуночного legacy artifact основной research выполняется заново.
Coverage audit версии до temporal anchor также не считается окончательной
нулевой остановкой в таком окне; обязательные проходы выполняются заново, а
recall sentinel использует текущую версию 7. Это сознательно допускает повторную
оплату только для доказанно ненадёжного временного класса artifact, сохраняя
обычный recovery для остальных случаев.''',
)
append_once(
    'automation/README.md',
    '## Temporal anchor ночного production',
    '''## Temporal anchor ночного production

`SEARCH_WINDOW_END_AT` — авторитетное `now` для main research, targeted coverage
audit и recall sentinel. Это защищает запуск около полуночи UTC от ложного вывода,
что московская часть окна следующего календарного дня находится в будущем.

Текущая версия temporal contract — `1`, текущая версия recall sentinel — `7`.
`run-info.json` сохраняет `research.temporal_anchor_version`; coverage report
сохраняет `temporal_anchor_version`. Legacy кросс-полуночный research без этой
версии не считается reusable. Старый zero-pool terminal stop также не может
обойти новый temporal contract до recovery.''',
)
append_once(
    'AGENTS.md',
    '## Temporal contract for nightly research',
    '''## Temporal contract for nightly research

For nightly production, the exact `search_window.end_at` timestamp is the
authoritative current time for research, every coverage pass, and the recall
sentinel. Do not let model/system calendar dates override that timestamp.
Legacy recovery data from a cross-midnight local/UTC window must not be reused
as final research or a terminal zero-pool stop unless it carries the current
temporal-anchor contract version.''',
)

TEST = '''from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

import ensure_story_coverage as coverage
import recover_digest_artifact as recovery

CROSS_MIDNIGHT = {
    "start_at": "2026-08-08T02:48:25+03:00",
    "end_at": "2026-08-09T02:44:13+03:00",
}
SAME_UTC_DATE = {
    "start_at": "2026-08-08T02:48:25+03:00",
    "end_at": "2026-08-08T20:44:13+03:00",
}


class TemporalAnchorContractTests(unittest.TestCase):
    def test_research_prompt_declares_authoritative_now(self) -> None:
        text = (ROOT / "automation/prompts/research_candidates.md").read_text(encoding="utf-8")
        self.assertIn("Авторитетное текущее время этой исследовательской задачи", text)
        self.assertIn("{{SEARCH_WINDOW_END_AT}}", text)
        self.assertIn("не является будущим", text)

    def test_coverage_prompt_declares_authoritative_now(self) -> None:
        text = (ROOT / "automation/prompts/coverage_audit.md").read_text(encoding="utf-8")
        self.assertIn("Авторитетное текущее время этого audit-прохода", text)
        self.assertIn("не является будущим", text)

    def test_versions_are_current(self) -> None:
        self.assertEqual(coverage.TEMPORAL_ANCHOR_VERSION, 1)
        self.assertEqual(coverage.RECALL_SENTINEL_VERSION, 7)
        self.assertEqual(recovery.TEMPORAL_ANCHOR_VERSION, 1)

    def _write_research(self, root: Path, *, version: int | None, window: dict) -> None:
        research = {"status": "ok"}
        if version is not None:
            research["temporal_anchor_version"] = version
        (root / "run-info.json").write_text(json.dumps({"research": research}), encoding="utf-8")
        (root / "candidates.json").write_text(
            json.dumps({"candidates": [], "search_window": window}), encoding="utf-8"
        )

    def test_legacy_cross_midnight_research_is_not_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_research(root, version=None, window=CROSS_MIDNIGHT)
            usable, reason = recovery.research_is_reusable(root)
            self.assertFalse(usable)
            self.assertIn("temporal anchor", reason or "")

    def test_current_cross_midnight_research_is_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_research(root, version=1, window=CROSS_MIDNIGHT)
            usable, reason = recovery.research_is_reusable(root)
            self.assertTrue(usable)
            self.assertIsNone(reason)

    def test_legacy_same_utc_date_research_remains_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_research(root, version=None, window=SAME_UTC_DATE)
            usable, reason = recovery.research_is_reusable(root)
            self.assertTrue(usable)
            self.assertIsNone(reason)

    def test_legacy_cross_midnight_coverage_plan_is_discarded(self) -> None:
        plan = {"attempts": [], "search_budget": {"maximum_calls": 7}}
        self.assertIsNone(coverage._prepare_prior_plan(plan, CROSS_MIDNIGHT))

    def test_current_cross_midnight_coverage_plan_can_be_reused(self) -> None:
        plan = {
            "temporal_anchor_version": 1,
            "attempts": [],
            "search_budget": {"maximum_calls": 7},
        }
        prepared = coverage._prepare_prior_plan(plan, CROSS_MIDNIGHT)
        self.assertIsInstance(prepared, dict)
        self.assertEqual(prepared.get("temporal_anchor_version"), 1)

    def test_sentinel_prompt_uses_authoritative_now(self) -> None:
        prompt = coverage.build_recall_sentinel_prompt(
            publication_date="2026-08-09",
            search_window=CROSS_MIDNIGHT,
            existing_candidates=[],
            archive={"items": []},
        )
        self.assertIn("Авторитетное текущее время этого sentinel-прохода", prompt)
        self.assertIn(CROSS_MIDNIGHT["end_at"], prompt)
        self.assertIn("не является будущим", prompt)

    def test_workflow_refuses_legacy_terminal_stop(self) -> None:
        workflow = (ROOT / ".github/workflows/daily-production.yml").read_text(encoding="utf-8")
        self.assertIn('data.get("temporal_anchor_version") == 1', workflow)
        self.assertIn('(data.get("recall_sentinel") or {}).get("version") == 7', workflow)

    def test_main_research_persists_temporal_version(self) -> None:
        source = (ROOT / "automation/scripts/generate_digest_preview.py").read_text(encoding="utf-8")
        self.assertIn('TEMPORAL_ANCHOR_VERSION = 1', source)
        self.assertIn('run_info["research"]["temporal_anchor_version"]', source)


if __name__ == "__main__":
    unittest.main()
'''
(ROOT / 'automation/tests/test_temporal_anchor_contract.py').write_text(TEST, encoding='utf-8')
