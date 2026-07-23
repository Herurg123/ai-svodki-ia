from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"


def load(name: str):
    path = SCRIPT_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = load("daily_orchestrator_common")
materializer = load("materialize_daily_orchestrator_replay")
finalizer = load("finalize_daily_orchestrator_replay")
validator = load("validate_daily_orchestrator_replay")


class ReplayFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original_roots = {}
        for module in (common, materializer, finalizer, validator):
            self.original_roots[module] = module.ROOT
            module.ROOT = self.root

        self.config_dir = self.root / "automation/config"
        self.research_dir = self.root / "automation/fixtures/research/2026-07-11"
        self.editorial_dir = self.root / "automation/fixtures/editorial/2026-07-11"
        self.release_dir = self.root / "automation/fixtures/release/2026-07-11"
        self.replay_dir = self.root / "automation/fixtures/daily-orchestrator/2026-07-11"
        self.output = self.root / "automation/preview/daily-orchestrator/2026-07-11"
        for path in (
            self.config_dir,
            self.research_dir,
            self.editorial_dir,
            self.release_dir,
            self.replay_dir,
            self.output.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)

        self.write_json(
            self.research_dir / "candidates.json",
            {
                "status": "ok",
                "publication_date": "2026-07-11",
                "candidates": [
                    {"id": "cand-001", "geography": "world"},
                    {"id": "cand-002", "geography": "russia"},
                ],
            },
        )
        self.write_json(
            self.editorial_dir / "digest.json",
            {
                "status": "ok",
                "date": "2026-07-11",
                "cover_filename": "ai-svodka-2026-07-11.png",
            },
        )
        self.write_json(
            self.editorial_dir / "run-info.json",
            {
                "status": "ok",
                "pipeline": "editorial_from_saved_research",
                "request_id": "editorial-resume-test",
                "publication_date": "2026-07-11",
                "research": {
                    "response": {"response_status": "reused", "web_search_calls": 0}
                },
                "total_usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "web_search_calls": 0},
            },
        )
        self.write_json(
            self.editorial_dir / "selection.json",
            {
                "status": "ok",
                "selected_candidate_ids": ["cand-001", "cand-002"],
            },
        )
        (self.editorial_dir / "image-prompt.txt").write_text("prompt", encoding="utf-8")
        self.write_json(self.editorial_dir / "image-source.json", {"status": "ok"})
        (self.editorial_dir / "article.html").write_text("<p>test</p>", encoding="utf-8")

        cover = b"synthetic-png-fixture"
        (self.release_dir / "cover.png").write_bytes(cover)
        self.write_json(
            self.release_dir / "image-manifest.json",
            {
                "status": "ok",
                "request_id": "image-preview-test",
                "width": 1536,
                "height": 864,
            },
        )
        self.write_json(
            self.release_dir / "visual-review.json",
            {"status": "accepted"},
        )
        image_files = {
            name: common.sha256_file(self.release_dir / name)
            for name in ("cover.png", "image-manifest.json", "visual-review.json")
        }
        cover_sha = common.sha256_file(self.release_dir / "cover.png")
        self.write_json(
            self.release_dir / "release-source.json",
            {
                "status": "ok",
                "production_eligible": False,
                "publication_date": "2026-07-11",
                "image_request_id": "image-preview-test",
                "image_model": "gpt-image-2",
                "cover_sha256": cover_sha,
                "image_files": image_files,
            },
        )

        self.config = {
            "schema_version": 1,
            "enabled": True,
            "mode": "recorded_fixture_replay",
            "publication_date": "2026-07-11",
            "preview_branch": "automation-prep",
            "output_root": "automation/preview/daily-orchestrator",
            "replay_source": "automation/fixtures/daily-orchestrator/2026-07-11/replay-source.json",
            "research_fixture": "automation/fixtures/research/2026-07-11/candidates.json",
            "editorial_fixture": "automation/fixtures/editorial/2026-07-11",
            "release_fixture": "automation/fixtures/release/2026-07-11",
            "expected": {
                "editorial_request_id": "editorial-resume-test",
                "image_request_id": "image-preview-test",
                "image_model": "gpt-image-2",
                "research_candidates": 2,
                "selected_stories": 2,
                "cover_sha256": cover_sha,
            },
            "safety": {
                "allow_network": False,
                "allow_openai": False,
                "allow_ftp": False,
                "allow_repository_write": False,
                "allow_schedule": False,
                "allow_production_posts": False,
                "allow_request_file_changes": False,
            },
        }
        self.config_path = self.config_dir / "daily-orchestrator.json"
        self.write_json(self.config_path, self.config)

        research_path = self.research_dir / "candidates.json"
        replay_source = {
            "schema_version": 1,
            "status": "ok",
            "mode": "recorded_fixture_replay",
            "production_eligible": False,
            "sources": {
                "research": {
                    "path": "automation/fixtures/research/2026-07-11/candidates.json",
                    "sha256": common.sha256_file(research_path),
                },
                "editorial": {
                    "path": "automation/fixtures/editorial/2026-07-11",
                    "tree_sha256": common.tree_digest(self.editorial_dir),
                    "files": common.file_manifest(self.editorial_dir),
                },
                "release": {
                    "path": "automation/fixtures/release/2026-07-11",
                    "tree_sha256": common.tree_digest(self.release_dir),
                    "files": common.file_manifest(self.release_dir),
                },
            },
        }
        self.replay_source_path = self.replay_dir / "replay-source.json"
        self.write_json(self.replay_source_path, replay_source)

    def tearDown(self) -> None:
        for module, original in self.original_roots.items():
            module.ROOT = original
        self.temp.cleanup()

    @staticmethod
    def write_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def materialize(self):
        return materializer.materialize(
            self.config_path,
            self.output,
            self.output / "materialization.json",
        )

    def create_completed_reports(self) -> Path:
        self.materialize()
        required = finalizer.REQUIRED_REPORTS
        for name, (relative, status) in required.items():
            path = self.output / relative
            if path.exists():
                continue
            payload = {"status": status}
            if name == "release_manifest":
                payload.update(
                    {
                        "publication_date": "2026-07-11",
                        "release_id": "golden-test",
                        "release_kind": "golden_fixture",
                        "production_eligible": False,
                        "source": {
                            "tree_sha256": "a" * 64,
                            "cover_sha256": self.config["expected"]["cover_sha256"],
                        },
                        "candidate": {
                            "tree_sha256": "b" * 64,
                            "cover_sha256": self.config["expected"]["cover_sha256"],
                        },
                    }
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            self.write_json(path, payload)
        for directory in (
            self.output / "release/source",
            self.output / "release/site/posts",
        ):
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "marker.txt").write_text(directory.name, encoding="utf-8")
        return self.output / "daily-run-manifest.json"


class MaterializationTests(ReplayFixture):
    def test_materializes_all_replay_stages_without_api_usage(self) -> None:
        report = self.materialize()
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["current_run"]["paid_api_calls"], 0)
        self.assertTrue((self.output / "research/candidates.json").is_file())
        self.assertTrue((self.output / "editorial/digest.json").is_file())
        self.assertTrue((self.output / "image/cover.png").is_file())

    def test_rejects_enabled_network(self) -> None:
        self.config["safety"]["allow_network"] = True
        self.write_json(self.config_path, self.config)
        with self.assertRaises(RuntimeError):
            self.materialize()

    def test_rejects_tampered_editorial_fixture(self) -> None:
        (self.editorial_dir / "article.html").write_text("tampered", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.materialize()

    def test_rejects_output_outside_configured_root(self) -> None:
        outside = self.root / "automation/preview/other/2026-07-11"
        with self.assertRaises(RuntimeError):
            materializer.materialize(
                self.config_path,
                outside,
                outside / "materialization.json",
            )

    def test_rejects_symlink_in_fixture(self) -> None:
        target = self.editorial_dir / "article.html"
        link = self.editorial_dir / "link.html"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("Символические ссылки недоступны в окружении теста.")
        with self.assertRaises(RuntimeError):
            self.materialize()


class FinalizationTests(ReplayFixture):
    def test_finalizes_and_validates_complete_replay(self) -> None:
        manifest_path = self.create_completed_reports()
        manifest = finalizer.finalize(self.output, manifest_path)
        report = validator.validate(
            self.config_path,
            manifest_path,
            self.output / "daily-run-validation.json",
        )
        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(report["status"], "ok", report["errors"])
        self.assertEqual(report["checks"]["paid_api_calls"], 0)
        self.assertEqual(report["checks"]["production_gate"], "blocked")

    def test_detects_paid_api_usage(self) -> None:
        manifest_path = self.create_completed_reports()
        manifest = finalizer.finalize(self.output, manifest_path)
        manifest["current_run"]["image_api_calls"] = 1
        self.write_json(manifest_path, manifest)
        report = validator.validate(
            self.config_path,
            manifest_path,
            self.output / "daily-run-validation.json",
        )
        self.assertEqual(report["status"], "error")
        self.assertIn("paid_api_usage", {item["code"] for item in report["errors"]})

    def test_detects_tampered_report(self) -> None:
        manifest_path = self.create_completed_reports()
        finalizer.finalize(self.output, manifest_path)
        (self.output / "workflow-safety.json").write_text('{"status":"ok","tampered":true}\n', encoding="utf-8")
        report = validator.validate(
            self.config_path,
            manifest_path,
            self.output / "daily-run-validation.json",
        )
        self.assertEqual(report["status"], "error")
        self.assertIn("report_hash", {item["code"] for item in report["errors"]})


if __name__ == "__main__":
    unittest.main()
