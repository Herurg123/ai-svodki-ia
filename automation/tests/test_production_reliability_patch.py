from __future__ import annotations

import base64
import importlib.util
import json
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


generator = load_module(
    "production_reliability_image_generator",
    SCRIPTS / "generate_image_preview.py",
)


class ProductionImageHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.output = self.root / "output"
        self.source.mkdir()
        self.config = self.root / "image.json"
        self.request = self.root / "request.json"
        self.config.write_text(
            json.dumps(
                {
                    "target_model": "gpt-image-2",
                    "width": 1536,
                    "height": 864,
                    "quality": "high",
                    "output_format": "png",
                    "artifact_filename": "cover.png",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.source / "digest.json").write_text(
            json.dumps(
                {
                    "status": "ok",
                    "date": "2026-07-24",
                    "title": "Test digest",
                    "image_prompt": "A valid production cover prompt",
                    "cover_filename": "ai-svodka-2026-07-24.png",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.source / "artifact-validation.json").write_text(
            json.dumps({"status": "ok", "files": {}}) + "\n",
            encoding="utf-8",
        )
        (self.source / "run-info.json").write_text(
            json.dumps({"status": "ok", "request_id": "production-digest-2026-07-24"})
            + "\n",
            encoding="utf-8",
        )
        self.request.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "mode": "image_api_preview",
                    "source": self.source.as_posix(),
                    "source_manifest": "artifact-validation.json",
                    "publication_date": "2026-07-24",
                    "request_id": "production-image-2026-07-24",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.transport_calls = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fake_transport(self, **kwargs):
        self.transport_calls += 1
        png = b"\x89PNG\r\n\x1a\nproduction-test"
        return {
            "created": 1,
            "data": [{"b64_json": base64.b64encode(png).decode("ascii")}],
        }

    def test_production_manifest_reaches_transport_once(self) -> None:
        result = generator.generate_image_artifact(
            source_dir=self.source,
            output_dir=self.output,
            request_path=self.request,
            config_path=self.config,
            api_key="not-sent",
            model="gpt-image-2",
            transport=self.fake_transport,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.transport_calls, 1)
        image_request = json.loads(
            (self.output / "image-request.json").read_text(encoding="utf-8")
        )
        self.assertEqual(image_request["source_manifest"], "artifact-validation.json")
        self.assertEqual(
            image_request["editorial_request_id"],
            "production-digest-2026-07-24",
        )

    def test_legacy_image_source_remains_supported(self) -> None:
        (self.source / "image-source.json").write_text(
            json.dumps(
                {
                    "status": "ok",
                    "editorial_request_id": "editorial-resume-legacy",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        legacy_request = self.root / "legacy-request.json"
        legacy_request.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "mode": "image_api_preview",
                    "source": self.source.as_posix(),
                    "publication_date": "2026-07-24",
                    "request_id": "legacy-image-request",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        legacy_output = self.root / "legacy-output"
        result = generator.generate_image_artifact(
            source_dir=self.source,
            output_dir=legacy_output,
            request_path=legacy_request,
            config_path=self.config,
            api_key="not-sent",
            model="gpt-image-2",
            transport=self.fake_transport,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.transport_calls, 1)
        image_request = json.loads(
            (legacy_output / "image-request.json").read_text(encoding="utf-8")
        )
        self.assertEqual(image_request["source_manifest"], "image-source.json")
        self.assertEqual(
            image_request["editorial_request_id"],
            "editorial-resume-legacy",
        )

    def test_invalid_manifest_stops_before_transport(self) -> None:
        (self.source / "artifact-validation.json").write_text(
            json.dumps({"status": "error"}) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(generator.ImageGenerationError, "status"):
            generator.generate_image_artifact(
                source_dir=self.source,
                output_dir=self.output,
                request_path=self.request,
                config_path=self.config,
                api_key="not-sent",
                model="gpt-image-2",
                transport=self.fake_transport,
            )
        self.assertEqual(self.transport_calls, 0)

    def test_production_request_builder_sets_manifest(self) -> None:
        output = self.root / "production-request.json"
        subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "create_production_image_request.py"),
                "--source-dir",
                str(self.source),
                "--publication-date",
                "2026-07-24",
                "--request-id",
                "production-image-2026-07-24",
                "--output",
                str(output),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["source_manifest"], "artifact-validation.json")


class ProductionWorkflowReliabilityTests(unittest.TestCase):
    def test_three_crons_gate_and_recovery_are_present(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "daily-production.yml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(workflow.count("cron:"), 3)
        for cron in ("17 3 * * *", "37 3 * * *", "57 3 * * *"):
            self.assertEqual(workflow.count(f'cron: "{cron}"'), 1)
        self.assertIn("Check RSS before paid APIs", workflow)
        self.assertIn("successful no-op", workflow)
        self.assertIn("Redeploy already committed release", workflow)
        self.assertIn("should_deploy", workflow)
        self.assertIn("recovery_run_id", workflow)
        self.assertIn("actions/download-artifact@v8", workflow)
        self.assertIn("if: inputs.recovery_run_id == ''", workflow)
        self.assertIn("rm -rf \"${image_dir}\"", workflow)


if __name__ == "__main__":
    unittest.main()
