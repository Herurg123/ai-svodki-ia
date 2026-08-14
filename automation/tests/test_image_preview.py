from __future__ import annotations

import base64
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

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


generator = load_module(
    "image_generator", SCRIPTS / "generate_image_preview.py"
)
fixture_builder = load_module(
    "cover_fixture_builder", SCRIPTS / "materialize_cover_fixture.py"
)
cover_validator = load_module(
    "cover_validator", SCRIPTS / "validate_cover_contract.py"
)


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

        with self.assertRaisesRegex(generator.ImageApiResponseError, "base64"):
            generator.generate_image_artifact(
                source_dir=self.source,
                output_dir=self.output,
                request_path=self.request_path,
                config_path=CONFIG,
                api_key="test-key-not-sent",
                model="gpt-image-2",
                transport=invalid_transport,
            )

    def test_missing_editorial_request_id_does_not_block_image_call(self) -> None:
        for name in ("image-source.json", "run-info.json", "digest.json"):
            path = self.source / name
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("request_id", None)
            payload.pop("editorial_request_id", None)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

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
        self.assertIsNotNone(self.captured_request)
        metadata = json.loads(
            (self.output / "image-request.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["image_request_id"], "image-preview-test-001")
        self.assertIsNone(metadata["source_editorial_request_id"])

    def test_missing_image_request_id_still_fails_before_transport(self) -> None:
        payload = json.loads(self.request_path.read_text(encoding="utf-8"))
        payload["request_id"] = ""
        self.request_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(generator.ImagePreflightError, "request_id"):
            generator.generate_image_artifact(
                source_dir=self.source,
                output_dir=self.output,
                request_path=self.request_path,
                config_path=CONFIG,
                api_key="test-key-not-sent",
                model="gpt-image-2",
                transport=self.fake_transport,
            )
        self.assertIsNone(self.captured_request)

    def test_http_error_preserves_openai_request_id_and_error_code(self) -> None:
        body = json.dumps(
            {
                "error": {
                    "message": "quota exhausted",
                    "type": "insufficient_quota",
                    "code": "insufficient_quota",
                }
            }
        ).encode("utf-8")
        http_error = urllib.error.HTTPError(
            "https://api.openai.com/v1/images/generations",
            429,
            "Too Many Requests",
            {"x-request-id": "req_image_123"},
            io.BytesIO(body),
        )
        with mock.patch.object(
            generator.urllib.request, "urlopen", side_effect=http_error
        ):
            with self.assertRaises(generator.ImageApiHttpError) as caught:
                generator.default_transport(
                    api_url="https://api.openai.com/v1/images/generations",
                    api_key="test-key-not-sent",
                    request_payload={"model": "gpt-image-2", "prompt": "test"},
                    timeout_seconds=10,
                )
        self.assertEqual(caught.exception.http_status, 429)
        self.assertEqual(caught.exception.openai_request_id, "req_image_123")
        self.assertEqual(caught.exception.api_error_code, "insufficient_quota")


if __name__ == "__main__":
    unittest.main()
