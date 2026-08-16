from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


normalize = "automation/scripts/normalize_digest_artifact.py"
replace_once(
    normalize,
    'def validate_primary_source_health(artifact_dir: Path) -> None:\n    """Fail closed when a completed fresh primary searched mostly junk/empty sources."""',
    'def validate_primary_source_health(artifact_dir: Path) -> str | None:\n    """Validate mandatory agency retrieval and warn on a healthy zero-result outcome."""',
)
replace_once(
    normalize,
    '''        if not (primary_has_fresh_agency or final_pool_has_fresh_agency):\n            raise NormalizationError(\n                "Primary Recall source-health degraded: ни Primary diagnostics, ни "\n                "финальный validated candidate pool после mandatory Coverage не "\n                "подтвердили свежий Reuters/AP/Bloomberg/FT материал в effective "\n                "window; служебные, author и старые newsletter URL не считаются "\n                "доказательством свежего agency retrieval."\n            )\n''',
    '''        if not (primary_has_fresh_agency or final_pool_has_fresh_agency):\n            return (\n                "Primary Recall source-health warning: обязательный major_agencies pass "\n                "и последующий Coverage/rescue завершились технически, но validated "\n                "candidate pool не подтвердил свежий Reuters/AP/Bloomberg/FT материал "\n                "в effective window. Нулевая выдача после успешно выполненного "\n                "ограниченного поиска считается недетерминированным retrieval outcome, "\n                "а не самостоятельной причиной блокировки публикации."\n            )\n    return None\n''',
)
replace_once(
    normalize,
    '''        "changed_files": [],\n        "changes": [],\n    }''',
    '''        "changed_files": [],\n        "changes": [],\n        "warnings": [],\n    }''',
)
replace_once(
    normalize,
    '''    normalize_fresh_primary_metadata(artifact_dir, report)\n    validate_primary_source_health(artifact_dir)\n''',
    '''    normalize_fresh_primary_metadata(artifact_dir, report)\n    source_health_warning = validate_primary_source_health(artifact_dir)\n    if source_health_warning:\n        report["warnings"].append(source_health_warning)\n''',
)

coverage = "automation/scripts/ensure_story_coverage_policy.py"
replace_once(
    coverage,
    '''\ndef snapshot_artifact(artifact_dir: Path) -> dict[Path, bytes]:\n''',
    '''\ndef _format_exception_with_output(exc: Exception) -> str:\n    message = f"{type(exc).__name__}: {exc}"\n    output = getattr(exc, "output", None)\n    if isinstance(output, str) and output.strip():\n        message += "\\n" + output.strip()\n    return message\n\n\ndef snapshot_artifact(artifact_dir: Path) -> dict[Path, bytes]:\n''',
)
replace_once(
    coverage,
    '''                report["editorial_repair_error"] = (\n                    f"{type(exc).__name__}: {exc}"\n                )''',
    '''                report["editorial_repair_error"] = (\n                    _format_exception_with_output(exc)\n                )''',
)
replace_once(
    coverage,
    '''        report["status"] = "error"\n        report["error"] = f"{type(exc).__name__}: {exc}"\n        write_json(args.report, report)''',
    '''        report["status"] = "error"\n        report["error"] = _format_exception_with_output(exc)\n        write_json(args.report, report)''',
)

status = "automation/scripts/summarize_production_status.py"
replace_once(
    status,
    '''def locate_reason(publication_date: str) -> tuple[str, str]:\n    candidates = [\n''',
    '''def locate_reason(publication_date: str) -> tuple[str, str]:\n    publication_dir = find_publication_dir(publication_date)\n    candidates = []\n    if publication_dir:\n        candidates.extend(\n            [\n                (\n                    "Нормализация editorial artifact",\n                    publication_dir / "artifact-normalization.json",\n                ),\n                (\n                    "Проверка editorial artifact",\n                    publication_dir / "artifact-validation.json",\n                ),\n            ]\n        )\n    candidates.extend([\n''',
)
replace_once(
    status,
    '''        (\n            "Проверка файлов перед commit",\n            REPORT_ROOT / "publish-changes.json",\n        ),\n    ]\n\n    publication_dir = find_publication_dir(publication_date)\n    if publication_dir:\n        candidates.extend(\n            [\n                (\n                    "Research/editorial",\n                    publication_dir / "run-info.json",\n                ),\n                (\n                    "Проверка editorial artifact",\n                    publication_dir / "artifact-validation.json",\n                ),\n            ]\n        )\n''',
    '''        (\n            "Проверка файлов перед commit",\n            REPORT_ROOT / "publish-changes.json",\n        ),\n    ])\n\n    if publication_dir:\n        candidates.append(\n            (\n                "Research/editorial",\n                publication_dir / "run-info.json",\n            )\n        )\n''',
)

tests = Path("automation/tests/test_aug16_terminal_source_health.py")
tests.write_text(r'''from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


normalizer = load_module("normalize_aug16_terminal", SCRIPTS / "normalize_digest_artifact.py")
coverage = load_module("coverage_policy_aug16_terminal", SCRIPTS / "ensure_story_coverage_policy.py")
status = load_module("status_aug16_terminal", SCRIPTS / "summarize_production_status.py")


def primary_report(*, completed: int = 1) -> dict:
    return {
        "search_window": {
            "start_at": "2026-08-14T06:48:32+03:00",
            "end_at": "2026-08-16T02:34:19+03:00",
        },
        "directions": [
            {
                "direction_id": "major_agencies",
                "web_search_calls_completed": completed,
                "api": {"consulted_sources": [{"url": "https://www.bloomberg.com/ai"}]},
            },
            {
                "direction_id": "business",
                "web_search_calls_completed": 1,
                "api": {"consulted_sources": [{"url": "https://techcrunch.com/example"}]},
            },
        ],
    }


class Aug16TerminalSourceHealthTests(unittest.TestCase):
    def test_completed_agency_route_without_fresh_candidate_warns_not_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir)
            (artifact / "primary-recall.json").write_text(
                json.dumps(primary_report(), ensure_ascii=False), encoding="utf-8"
            )
            warning = normalizer.validate_primary_source_health(artifact)
            self.assertIsInstance(warning, str)
            self.assertIn("source-health warning", warning)
            self.assertIn("не самостоятельной причиной блокировки", warning)

    def test_incomplete_major_agencies_route_remains_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir)
            (artifact / "primary-recall.json").write_text(
                json.dumps(primary_report(completed=0), ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaises(normalizer.NormalizationError):
                normalizer.validate_primary_source_health(artifact)

    def test_editorial_rerun_error_keeps_captured_child_output(self) -> None:
        exc = subprocess.CalledProcessError(
            1,
            ["python", "run_digest_preview.py"],
            output="Пустой раздел «Китайские лидеры ИИ» не должен присутствовать",
        )
        rendered = coverage._format_exception_with_output(exc)
        self.assertIn("CalledProcessError", rendered)
        self.assertIn("Китайские лидеры ИИ", rendered)

    def test_terminal_normalization_reason_beats_old_recovery_error(self) -> None:
        previous_cwd = Path.cwd()
        previous_root = status.REPORT_ROOT
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                daily = root / "automation" / "preview" / "production-daily"
                publication = root / "automation" / "preview" / "2026-08-16"
                daily.mkdir(parents=True)
                publication.mkdir(parents=True)
                (daily / "recovery.json").write_text(
                    json.dumps({"status": "error", "error": "old recovery error"}), encoding="utf-8"
                )
                (publication / "artifact-normalization.json").write_text(
                    json.dumps({"status": "error", "error": "terminal normalization error"}), encoding="utf-8"
                )
                os.chdir(root)
                status.REPORT_ROOT = Path("automation/preview/production-daily")
                stage, reason = status.locate_reason("2026-08-16")
                self.assertEqual(stage, "Нормализация editorial artifact")
                self.assertEqual(reason, "terminal normalization error")
        finally:
            os.chdir(previous_cwd)
            status.REPORT_ROOT = previous_root


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

docs = {
    "README.md": r'''

### Source-health при недетерминированной agency-выдаче

Обязательный `major_agencies` Primary pass и bounded same-event agency rescue остаются частью fail-closed поискового контура и не увеличивают бюджет: максимум по-прежнему 12 Primary + до 4 Hybrid + до 7 Coverage searches. Технически незавершённый обязательный маршрут, отсутствие search operation или деградация общего source-health по-прежнему блокируют выпуск. Если же обязательные маршруты корректно завершились, но Terra не вернула подтверждённый свежий Reuters/AP/Bloomberg/FT материал, сам нулевой ranking-result больше не считается достаточной причиной аварии: normalization сохраняет явное `source-health warning`, а остальные editorial/validation gates продолжают работать. Любой найденный agency-материал всё так же обязан пройти точную проверку effective window.
''',
    "automation/README.md": r'''

### Terminal source-health contract

Agency retrieval остаётся обязательным: `major_agencies` должен выполнить свой search, а при необходимости Coverage использует один bounded same-event Reuters/AP/Bloomberg/FT rescue. Нулевой результат после технически успешного обязательного поиска теперь записывается как warning, а не как самостоятельный fatal error, потому что ranking Terra недетерминирован. Ошибка/неполнота обязательного маршрута остаётся fatal. Search budget и точная временная валидация agency evidence не изменены. Production status при нескольких сохранённых ошибках отдаёт приоритет фактически достигнутому terminal stage (`artifact-normalization.json`/`artifact-validation.json`), а recovery-ошибка используется только как более ранняя диагностика.
''',
    "AGENTS.md": r'''

## Regression rule: terminal agency source-health (2026-08-16)

Не превращать отсутствие свежего Reuters/AP/Bloomberg/FT кандидата в самостоятельный fatal gate, если обязательный `major_agencies` pass и bounded Coverage/rescue технически завершились. Terra/web-search ranking недетерминирован: такой zero-result должен сохраняться как заметный source-health warning, после чего решение о публикации принимают обычные editorial/validation gates. При этом незавершённый обязательный agency search, сломанный search contract, неполный Coverage audit и невалидная временная привязка найденного evidence остаются fail-closed. Не увеличивать search budget ради компенсации ranking-недетерминизма без отдельного проверенного архитектурного решения. В pipeline diagnostics приоритет имеет наиболее поздний фактически достигнутый terminal stage; recovery не должна маскировать последующую normalization/validation ошибку. Для subprocess editorial rerun всегда сохранять captured child output в JSON diagnostics.
''',
}
for path, addition in docs.items():
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    marker = addition.strip().splitlines()[0]
    if marker not in text:
        target.write_text(text.rstrip() + "\n" + addition, encoding="utf-8")
