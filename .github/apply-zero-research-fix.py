from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one patch anchor, got {text.count(old)}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "automation/scripts/run_digest_preview.py",
    '''EMPTY_RESEARCH_MARKERS = (\n    "не найдено ни одного",\n    "не осталось ни одного достойного",\n    "пул кандидатов пуст",\n)\n''',
    '''EMPTY_RESEARCH_MARKERS = (\n    "не найдено ни одного",\n    "не осталось ни одного достойного",\n    "не удалось подтвердить ни одного",\n    "пул кандидатов пуст",\n)\n''',
)
replace_once(
    "automation/scripts/recover_digest_artifact.py",
    "TEMPORAL_ANCHOR_VERSION = 1\n\nIMAGE_RECOVERY_REQUIRED = (\n",
    '''TEMPORAL_ANCHOR_VERSION = 1
EMPTY_RESEARCH_MARKERS = (
    "не найдено ни одного",
    "не осталось ни одного достойного",
    "не удалось подтвердить ни одного",
    "пул кандидатов пуст",
)

IMAGE_RECOVERY_REQUIRED = (
''',
)
replace_once(
    "automation/scripts/recover_digest_artifact.py",
    '''def research_is_reusable(source_dir: Path) -> tuple[bool, str | None]:
    run_info = read_json(source_dir / "run-info.json")
    candidates = read_json(source_dir / "candidates.json")
    if not isinstance(run_info, dict):
        return False, "run-info.json должен содержать объект"
    research = run_info.get("research")
    if not isinstance(research, dict) or research.get("status") != "ok":
        return False, "research.status не равен ok"
    if not isinstance(candidates, dict) or not isinstance(candidates.get("candidates"), list):
        return False, "candidates.json не содержит candidates[]"
''',
    '''def completed_empty_research(
    run_info: dict[str, Any],
    candidates: dict[str, Any],
) -> bool:
    if candidates.get("candidates") != []:
        return False
    if not isinstance(candidates.get("coverage"), list):
        return False
    if not isinstance(candidates.get("search_window"), dict):
        return False
    research = run_info.get("research")
    if not isinstance(research, dict):
        return False
    response = research.get("response")
    if not isinstance(response, dict) or response.get("response_status") != "completed":
        return False
    try:
        completed_searches = int(response.get("web_search_calls", 0) or 0)
    except (TypeError, ValueError):
        return False
    if completed_searches < 1:
        return False
    messages = " ".join(
        str(value or "")
        for value in (
            candidates.get("error_message"),
            research.get("error"),
            run_info.get("error"),
        )
    ).casefold()
    return any(marker in messages for marker in EMPTY_RESEARCH_MARKERS)


def normalize_completed_empty_research(target_dir: Path) -> bool:
    run_info_path = target_dir / "run-info.json"
    candidates_path = target_dir / "candidates.json"
    run_info = read_json(run_info_path)
    candidates = read_json(candidates_path)
    if not isinstance(run_info, dict) or not isinstance(candidates, dict):
        return False
    if not completed_empty_research(run_info, candidates):
        return False
    candidates["status"] = "ok"
    candidates["error_message"] = None
    research = run_info.get("research")
    if not isinstance(research, dict):
        return False
    research["status"] = "ok"
    research["error"] = None
    warnings = run_info.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        run_info["warnings"] = warnings
    warning = (
        "Восстановлен завершённый основной Web Search с нулевым пулом; "
        "результат передан обязательному coverage audit без повторного research."
    )
    if warning not in warnings:
        warnings.append(warning)
    write_json(candidates_path, candidates)
    write_json(run_info_path, run_info)
    return True


def research_is_reusable(source_dir: Path) -> tuple[bool, str | None]:
    run_info = read_json(source_dir / "run-info.json")
    candidates = read_json(source_dir / "candidates.json")
    if not isinstance(run_info, dict):
        return False, "run-info.json должен содержать объект"
    if not isinstance(candidates, dict) or not isinstance(candidates.get("candidates"), list):
        return False, "candidates.json не содержит candidates[]"
    research = run_info.get("research")
    if not isinstance(research, dict):
        return False, "run-info.json не содержит research"
    if research.get("status") != "ok" and not completed_empty_research(run_info, candidates):
        return False, "research.status не равен ok и это не завершённый нулевой research"
''',
)
replace_once(
    "automation/scripts/recover_digest_artifact.py",
    '''    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)

    merged_research = restore_merged_coverage_research(
''',
    '''    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    normalized_empty_research = normalize_completed_empty_research(target_dir)

    merged_research = restore_merged_coverage_research(
''',
)
replace_once(
    "automation/scripts/recover_digest_artifact.py",
    '''        "removed_stage_files": removed,
        "merged_coverage_research": merged_research,
''',
    '''        "removed_stage_files": removed,
        "normalized_empty_research": normalized_empty_research,
        "merged_coverage_research": merged_research,
''',
)

TEST = r'''from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))

import recover_digest_artifact as recovery
import run_digest_preview as wrapper

AUG9_MESSAGE = (
    "В строгом окне не удалось подтвердить ни одного достойного нового события "
    "по открываемым первичным источникам."
)


def payloads(*, response_status: str = "completed", web_search_calls: int = 6, message: str = AUG9_MESSAGE):
    candidates = {
        "status": "error",
        "error_message": message,
        "publication_date": "2026-08-09",
        "search_window": {
            "start_at": "2026-08-08T02:48:25+03:00",
            "end_at": "2026-08-09T09:37:32+03:00",
        },
        "coverage": [{"area": "world", "status": "gap", "notes": "checked"}],
        "candidates": [],
        "rejected_as_duplicates": [],
        "research_notes": "search complete",
    }
    run_info = {
        "status": "error",
        "error": "RuntimeError: " + message,
        "publication_date": "2026-08-09",
        "finished_at": "2026-08-09T09:38:54+03:00",
        "warnings": [],
        "research": {
            "status": "error",
            "error": "RuntimeError: " + message,
            "temporal_anchor_version": 1,
            "response": {
                "response_status": response_status,
                "web_search_calls": web_search_calls,
            },
        },
    }
    return run_info, candidates


def write_artifact(root: Path, *, response_status: str = "completed", web_search_calls: int = 6, message: str = AUG9_MESSAGE):
    run_info, candidates = payloads(
        response_status=response_status,
        web_search_calls=web_search_calls,
        message=message,
    )
    (root / "run-info.json").write_text(json.dumps(run_info, ensure_ascii=False), encoding="utf-8")
    (root / "candidates.json").write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
    (root / "research-output-raw.json").write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")


class ZeroResearchRecoveryTests(unittest.TestCase):
    def test_aug9_phrase_is_normalized_by_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_artifact(root)
            self.assertTrue(wrapper.normalize_completed_empty_research(root))
            self.assertEqual(json.loads((root / "candidates.json").read_text())["status"], "ok")
            self.assertEqual(json.loads((root / "run-info.json").read_text())["research"]["status"], "ok")

    def test_aug9_paid_research_is_reusable_and_normalized_on_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            recovery_root = Path(temp) / "recovery"
            source = recovery_root / "2026-08-09"
            source.mkdir(parents=True)
            write_artifact(source)
            usable, reason = recovery.research_is_reusable(source)
            self.assertTrue(usable, reason)
            target = Path(temp) / "target"
            report = recovery.recover(
                recovery_root,
                target,
                "2026-08-09",
                Path(temp) / "report.json",
            )
            self.assertEqual(report["recovery_mode"], "research_only")
            self.assertTrue(report["normalized_empty_research"])
            self.assertEqual(json.loads((target / "candidates.json").read_text())["status"], "ok")
            self.assertEqual(json.loads((target / "run-info.json").read_text())["research"]["status"], "ok")

    def test_transport_failure_is_not_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            write_artifact(source, response_status="failed")
            usable, _ = recovery.research_is_reusable(source)
            self.assertFalse(usable)
            self.assertFalse(wrapper.normalize_completed_empty_research(source))

    def test_zero_search_calls_are_not_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            write_artifact(source, web_search_calls=0)
            usable, _ = recovery.research_is_reusable(source)
            self.assertFalse(usable)

    def test_unrelated_model_error_is_not_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            write_artifact(source, message="Внутренняя ошибка анализа источников")
            usable, _ = recovery.research_is_reusable(source)
            self.assertFalse(usable)


if __name__ == "__main__":
    unittest.main()
'''
Path("automation/tests/test_zero_research_recovery.py").write_text(TEST, encoding="utf-8")
