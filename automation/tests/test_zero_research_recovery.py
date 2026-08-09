from __future__ import annotations

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
