from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


materialize = load_module(
    "materialize_cover_fixture_test", SCRIPTS / "materialize_cover_fixture.py"
)
validator = load_module(
    "validate_cover_contract_test", SCRIPTS / "validate_cover_contract.py"
)


class CoverContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifact = self.root / "artifact"
        self.artifact.mkdir()
        self.config_path = ROOT / "automation" / "config" / "image.json"
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.title = "ИИ-Сводка на 11 июля 2026"
        self.prompt = (
            "Изображение 16:9: современная редакционная обложка с единственным "
            f"точным заголовком «{self.title}».\n\n"
            "Главные визуальные темы: безопасный поток данных и RSS.\n\n"
            "Композиция: плотная сцена без пустой половины кадра.\n\n"
            "Стиль: без логотипов, без дополнительного текста, без водяных знаков, "
            "без мелких интерфейсных надписей, без узнаваемых лиц, "
            "без стокового корпоративного клипарта."
        )
        self.digest = {
            "date": "2026-07-11",
            "title": self.title,
            "cover_filename": "ai-svodka-2026-07-11.png",
            "image_prompt": self.prompt,
        }
        self._write_json("digest.json", self.digest)
        self._write_valid_image_files()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_json(self, name: str, payload: dict) -> None:
        (self.artifact / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_valid_image_files(self, png: bytes | None = None) -> None:
        width = int(self.config["width"])
        height = int(self.config["height"])
        png = png or materialize.build_fixture_png(width, height)
        (self.artifact / "cover.png").write_bytes(png)
        prompt_sha = hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()
        cover_sha = hashlib.sha256(png).hexdigest()
        request = {
            "status": "ok",
            "mode": "offline_fixture",
            "target_model": self.config["target_model"],
            "requested_size": f"{width}x{height}",
            "quality": self.config["quality"],
            "output_format": self.config["output_format"],
            "publication_date": self.digest["date"],
            "title": self.title,
            "prompt_sha256": prompt_sha,
            "artifact_filename": "cover.png",
            "publish_filename": self.digest["cover_filename"],
            "network_used": False,
            "openai_used": False,
        }
        manifest = {
            "status": "ok",
            "mode": "offline_fixture",
            "source": "deterministic_python_fixture",
            "artifact_filename": "cover.png",
            "publish_filename": self.digest["cover_filename"],
            "format": "png",
            "width": width,
            "height": height,
            "bytes": len(png),
            "sha256": cover_sha,
            "prompt_sha256": prompt_sha,
            "network_used": False,
            "openai_used": False,
            "visual_semantics_validated": False,
            "rendered_title_validated": False,
        }
        self._write_json("image-request.json", request)
        self._write_json("image-manifest.json", manifest)

    def _report(self):
        return validator.validate_contract(self.artifact, self.config_path)

    def _codes(self, report):
        return {item["code"] for item in report["errors"]}

    def test_valid_offline_fixture_passes(self) -> None:
        report = self._report()
        self.assertEqual(report["status"], "ok", report["errors"])
        self.assertFalse(report["visual_semantics_validated"])
        self.assertFalse(report["rendered_title_validated"])
        self.assertEqual(report["png"]["width"], 1536)
        self.assertEqual(report["png"]["height"], 864)

    def test_wrong_dimensions_are_rejected(self) -> None:
        png = materialize.build_fixture_png(1280, 720)
        self._write_valid_image_files(png)
        report = self._report()
        self.assertIn("png_width", self._codes(report))
        self.assertIn("png_height", self._codes(report))

    def test_bad_crc_is_rejected(self) -> None:
        path = self.artifact / "cover.png"
        payload = bytearray(path.read_bytes())
        idat = payload.index(b"IDAT")
        payload[idat + 8] ^= 1
        self._write_valid_image_files(bytes(payload))
        report = self._report()
        self.assertIn("png_crc", self._codes(report))

    def test_text_metadata_chunk_is_rejected(self) -> None:
        png = (self.artifact / "cover.png").read_bytes()
        iend = png.rfind(b"\x00\x00\x00\x00IEND")
        text = materialize.png_chunk(b"tEXt", b"Comment\x00fixture")
        patched = png[:iend] + text + png[iend:]
        self._write_valid_image_files(patched)
        report = self._report()
        self.assertIn("png_text_chunks", self._codes(report))

    def test_missing_exact_title_in_prompt_is_rejected(self) -> None:
        self.prompt = self.prompt.replace(self.title, "Другой заголовок")
        self.digest["image_prompt"] = self.prompt
        self._write_json("digest.json", self.digest)
        self._write_valid_image_files()
        report = self._report()
        self.assertIn("prompt_title", self._codes(report))

    def test_request_model_mismatch_is_rejected(self) -> None:
        request = json.loads((self.artifact / "image-request.json").read_text())
        request["target_model"] = "wrong-model"
        self._write_json("image-request.json", request)
        report = self._report()
        self.assertIn("request_target_model", self._codes(report))

    def test_manifest_hash_mismatch_is_rejected(self) -> None:
        manifest = json.loads((self.artifact / "image-manifest.json").read_text())
        manifest["sha256"] = "0" * 64
        self._write_json("image-manifest.json", manifest)
        report = self._report()
        self.assertIn("manifest_sha256", self._codes(report))

    def test_repository_digest_fixture_prompt_matches_contract(self) -> None:
        fixture_path = (
            ROOT
            / "automation"
            / "fixtures"
            / "digest-preview"
            / "2026-07-11"
            / "digest.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.title = str(fixture["title"])
        self.prompt = str(fixture["image_prompt"])
        self.digest = {
            "date": str(fixture["date"]),
            "title": self.title,
            "cover_filename": str(fixture["cover_filename"]),
            "image_prompt": self.prompt,
        }
        self._write_json("digest.json", self.digest)
        self._write_valid_image_files()
        report = self._report()
        self.assertEqual(report["status"], "ok", report["errors"])

    def test_offline_fixture_cannot_claim_api_usage(self) -> None:
        request = json.loads((self.artifact / "image-request.json").read_text())
        manifest = json.loads((self.artifact / "image-manifest.json").read_text())
        request["openai_used"] = True
        manifest["openai_used"] = True
        self._write_json("image-request.json", request)
        self._write_json("image-manifest.json", manifest)
        report = self._report()
        self.assertIn("request_fixture_flags", self._codes(report))


if __name__ == "__main__":
    unittest.main()
