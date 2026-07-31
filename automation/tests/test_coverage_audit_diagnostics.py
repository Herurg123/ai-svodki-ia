from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coverage = load_module("story_coverage", SCRIPTS / "story_coverage.py")
audit = load_module("ensure_story_coverage", SCRIPTS / "ensure_story_coverage.py")


class Item:
    type = "web_search_call"


def run_fake_response(response):
    class Responses:
        def create(self, **kwargs):
            return response

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = Responses()

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = FakeOpenAI
    with mock.patch.dict(sys.modules, {"openai": fake_module}):
        return audit.run_audit_request(
            api_key="secret",
            model="gpt-5.6-terra",
            prompt="targeted",
            maximum_web_search_calls=5,
        )


class CoverageAuditDiagnosticsTests(unittest.TestCase):
    def test_incomplete_response_keeps_metadata_and_raw_response(self) -> None:
        class Response:
            status = "incomplete"
            output_text = ""
            output = [Item(), Item()]
            id = "resp_incomplete"
            model = "gpt-5.6-terra"
            usage = {"input_tokens": 12, "output_tokens": 0}

            def model_dump(self):
                return {
                    "id": self.id,
                    "status": self.status,
                    "output": [{"type": "web_search_call"}] * 2,
                }

        result = run_fake_response(Response())

        self.assertIsNone(result.payload)
        self.assertIn("не завершён", result.validation_error or "")
        self.assertEqual(result.metadata["response_id"], "resp_incomplete")
        self.assertEqual(result.metadata["web_search_calls"], 2)
        self.assertEqual(result.metadata["usage"]["input_tokens"], 12)
        self.assertEqual(result.raw_response["status"], "incomplete")

    def test_malformed_json_keeps_output_and_metadata(self) -> None:
        class Response:
            status = "completed"
            output_text = "{broken-json"
            output = [Item()]
            id = "resp_malformed"
            model = "gpt-5.6-terra"
            usage = {"input_tokens": 7, "output_tokens": 2}

            def model_dump(self):
                return {
                    "id": self.id,
                    "status": self.status,
                    "output_text": self.output_text,
                }

        result = run_fake_response(Response())

        self.assertIsNone(result.payload)
        self.assertIn("некорректный JSON", result.validation_error or "")
        self.assertEqual(result.output_text, "{broken-json")
        self.assertEqual(result.metadata["web_search_calls"], 1)
        self.assertEqual(result.raw_response["id"], "resp_malformed")

    def test_main_persists_paid_response_diagnostics_before_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            artifact.mkdir()
            (artifact / "candidates.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "publication_date": "2026-07-31",
                        "search_window": {
                            "start_at": "2026-07-30T06:00:00+03:00",
                            "end_at": "2026-07-31T06:00:00+03:00",
                        },
                        "candidates": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            archive = root / "archive.json"
            archive.write_text('{"items": []}', encoding="utf-8")
            report_path = root / "diagnostics" / "coverage-audit.json"
            result = audit.AuditRequestResult(
                payload=None,
                metadata={
                    "response_id": "resp_empty",
                    "status": "completed",
                    "model": "gpt-5.6-terra",
                    "web_search_calls": 4,
                    "configured_web_search_limit": 5,
                    "observed_web_search_calls": 4,
                    "budget_overrun": False,
                    "usage": {"input_tokens": 20, "output_tokens": 0},
                },
                output_text="",
                raw_response={
                    "id": "resp_empty",
                    "status": "completed",
                    "output": [{"type": "web_search_call"}] * 4,
                },
                validation_error="Coverage audit вернул пустой output_text",
            )
            argv = [
                "ensure_story_coverage.py",
                "--artifact-dir",
                str(artifact),
                "--archive",
                str(archive),
                "--publication-date",
                "2026-07-31",
                "--model",
                "gpt-5.6-terra",
                "--report",
                str(report_path),
            ]

            with mock.patch.object(sys, "argv", argv), mock.patch.dict(
                os.environ, {"OPENAI_API_KEY": "test-key"}
            ), mock.patch.object(audit, "run_audit_request", return_value=result):
                self.assertEqual(audit.main(), 1)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "error")
            self.assertEqual(report["audit_state"], "completed_unusable")
            self.assertEqual(report["error_stage"], "response_validation")
            self.assertTrue(report["web_search_performed"])
            self.assertEqual(report["api"]["response_id"], "resp_empty")
            self.assertEqual(report["api"]["usage"]["input_tokens"], 20)
            self.assertEqual(
                report["validation_error"],
                "Coverage audit вернул пустой output_text",
            )

            output_path = Path(report["api_output_path"])
            response_path = Path(report["api_response_path"])
            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "")
            self.assertTrue(response_path.is_file())
            raw = json.loads(response_path.read_text(encoding="utf-8"))
            self.assertEqual(raw["id"], "resp_empty")
            self.assertEqual(len(raw["output"]), 4)

    def test_only_usable_completed_audit_is_reused(self) -> None:
        metadata = {"status": "completed", "web_search_calls": 4}
        unusable = {
            "status": "error",
            "audit_state": "completed_unusable",
            "web_search_performed": True,
            "api": metadata,
        }
        usable = {
            "status": "ok",
            "audit_state": "completed_usable",
            "web_search_performed": True,
            "api": metadata,
        }
        legacy_usable = {
            "status": "ok",
            "web_search_performed": True,
            "api": metadata,
        }

        self.assertFalse(audit.completed_prior_audit(unusable))
        self.assertTrue(audit.completed_prior_audit(usable))
        self.assertTrue(audit.completed_prior_audit(legacy_usable))


if __name__ == "__main__":
    unittest.main()
