from __future__ import annotations

import base64
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
FIXTURE = ROOT / "automation" / "fixtures" / "editorial" / "2026-07-11"
CONFIG = ROOT / "automation" / "config" / "image.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


preflight = load_module(
    "image_preflight", SCRIPTS / "validate_image_request_preflight.py"
)
generator = load_module(
    "image_generator", SCRIPTS / "generate_image_preview.py"
)
fixture_builder = load_module(
    "cover_fixture_builder", SCRIPTS / "materialize_cover_fixture.py"
)
cover_validator = load_module(
    "cover_validator", SCRIPTS / "validate_cover_contract.py"
)


class ImageSourceTests(unittest.TestCase):
    def test_repository_editorial_fixture_is_hash_locked(self) -> None:
        report = preflight.validate_source_directory(FIXTURE)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["publication_date"], "2026-07-11")
        self.assertEqual(report["editorial_request_id"], "editorial-resume-004")
        self.assertEqual(len(report["prompt_sha256"]), 64)

    def test_tampered_source_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "source"
            shutil.copytree(FIXTURE, target)
            (target / "digest.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(preflight.PreflightError, "SHA-256"):
                preflight.validate_source_directory(target)

    def test_existing_cover_in_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "source"
            shutil.copytree(FIXTURE, target)
            (target / "cover.png").write_bytes(b"not-a-cover")
            with self.assertRaisesRegex(preflight.PreflightError, "лишние"):
                preflight.validate_source_directory(target)


class ImageRequestGitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-b", "automation-prep")
        self.git("config", "user.name", "CI Test")
        self.git("config", "user.email", "ci@example.invalid")
        source = self.root / "automation/fixtures/editorial/2026-07-11"
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(FIXTURE, source)
        (self.root / "automation/requests").mkdir(parents=True)
        self.write_request("image-preview-000")
        self.commit_all("baseline")
        self.before = self.git("rev-parse", "HEAD").strip()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return completed.stdout

    def request_payload(self, request_id: str) -> dict:
        return {
            "enabled": True,
            "mode": "image_api_preview",
            "source": "automation/fixtures/editorial/2026-07-11",
            "publication_date": "2026-07-11",
            "request_id": request_id,
        }

    def write_request(self, request_id: str) -> None:
        path = self.root / preflight.REQUEST_REL
        path.write_text(
            json.dumps(self.request_payload(request_id), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    def commit_all(self, message: str) -> str:
        self.git("add", ".")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def validate(self, current: str):
        return preflight.validate_preflight(
            repo_root=self.root,
            request_rel=preflight.REQUEST_REL,
            before_sha=self.before,
            current_sha=current,
            expected_ref="refs/heads/automation-prep",
            actual_ref="refs/heads/automation-prep",
        )

    def test_valid_request_only_commit(self) -> None:
        self.write_request("image-preview-001")
        current = self.commit_all("image request only")
        report, request = self.validate(current)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["changed_files"], [preflight.REQUEST_REL.as_posix()])
        self.assertEqual(request.editorial_request_id, "editorial-resume-004")

    def test_mixed_commit_is_rejected(self) -> None:
        self.write_request("image-preview-001")
        (self.root / "README.md").write_text("mixed\n", encoding="utf-8")
        current = self.commit_all("mixed")
        with self.assertRaisesRegex(preflight.PreflightError, "ровно"):
            self.validate(current)

    def test_historical_request_id_cannot_be_reused(self) -> None:
        self.write_request("image-preview-001")
        self.commit_all("first 001")
        self.write_request("image-preview-002")
        self.commit_all("002")
        self.before = self.git("rev-parse", "HEAD").strip()
        self.write_request("image-preview-001")
        current = self.commit_all("reuse 001")
        with self.assertRaisesRegex(preflight.PreflightError, "уже использовался"):
            self.validate(current)

    def test_publication_date_mismatch_is_rejected(self) -> None:
        payload = self.request_payload("image-preview-001")
        payload["publication_date"] = "2026-07-12"
        with self.assertRaisesRegex(preflight.PreflightError, "не совпадает"):
            preflight.validate_request_payload(payload, self.root)


class ImageGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.output = self.root / "output"
        shutil.copytree(FIXTURE, self.source)
        self.request_path = self.root / "image-preview.json"
        self.request_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "mode": "image_api_preview",
                    "source": "automation/fixtures/editorial/2026-07-11",
                    "publication_date": "2026-07-11",
                    "request_id": "image-preview-test-001",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.png = fixture_builder.build_fixture_png(
            int(config["width"]), int(config["height"])
        )
        self.captured_request: dict | None = None

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fake_transport(self, **kwargs):
        self.captured_request = kwargs["request_payload"]
        return {
            "created": 1,
            "background": "opaque",
            "output_format": "png",
            "quality": "high",
            "size": "1536x864",
            "data": [{"b64_json": base64.b64encode(self.png).decode("ascii")}],
        }

    def test_one_shot_generation_matches_cover_contract(self) -> None:
        result = generator.generate_image_artifact(
            source_dir=self.source,
            output_dir=self.output,
            request_path=self.request_path,
            config_path=CONFIG,
            api_key="test-key-not-sent",
            model="gpt-image-2",
            transport=self.fake_transport,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["retry_count"], 0)
        self.assertIsNotNone(self.captured_request)
        assert self.captured_request is not None
        self.assertEqual(self.captured_request["n"], 1)
        self.assertEqual(self.captured_request["size"], "1536x864")
        self.assertEqual(self.captured_request["quality"], "high")
        self.assertEqual(self.captured_request["output_format"], "png")
        self.assertEqual(self.captured_request["background"], "opaque")
        report = cover_validator.validate_contract(self.output, CONFIG)
        self.assertEqual(report["status"], "ok", report["errors"])
        response = json.loads(
            (self.output / "image-api-response.json").read_text(encoding="utf-8")
        )
        self.assertFalse(response["base64_stored"])

    def test_wrong_model_is_rejected_before_transport(self) -> None:
        with self.assertRaisesRegex(generator.ImageGenerationError, "не совпадает"):
            generator.generate_image_artifact(
                source_dir=self.source,
                output_dir=self.output,
                request_path=self.request_path,
                config_path=CONFIG,
                api_key="test-key-not-sent",
                model="wrong-model",
                transport=self.fake_transport,
            )
        self.assertIsNone(self.captured_request)

    def test_invalid_base64_is_rejected(self) -> None:
        def invalid_transport(**kwargs):
            return {"data": [{"b64_json": "***not-base64***"}]}

        with self.assertRaisesRegex(generator.ImageGenerationError, "base64"):
            generator.generate_image_artifact(
                source_dir=self.source,
                output_dir=self.output,
                request_path=self.request_path,
                config_path=CONFIG,
                api_key="test-key-not-sent",
                model="gpt-image-2",
                transport=invalid_transport,
            )


if __name__ == "__main__":
    unittest.main()
