from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release_common = load("release_common")
materializer = load("materialize_release_candidate")
creator = load("create_release_manifest")
validator = load("validate_release_candidate")
gate = load("validate_production_gate")


class ReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "production_enabled": False,
            "production_branch": "main",
            "publication_timezone": "Europe/Moscow",
            "max_candidate_age_hours": 36,
            "require_manual_approval": True,
            "allow_golden_fixture_in_production": False,
        }
        self.manifest = {
            "status": "ok",
            "release_id": "test",
            "release_kind": "golden_fixture",
            "production_eligible": False,
            "published_at": "2026-07-11T07:00:00+03:00",
            "validations": {
                "editorial_artifact": {"status": "ok"},
                "cover_contract": {"status": "ok"},
                "visual_review": {"status": "accepted"},
                "site": {"status": "ok"},
                "dzen_feed": {"status": "ok"},
            },
            "safety": {
                "live_posts_unchanged": True,
                "ftp_used": False,
                "request_files_changed": False,
            },
        }

    def test_golden_fixture_is_blocked(self) -> None:
        report = gate.validate_gate(
            self.config,
            self.manifest,
            "refs/heads/automation-prep",
            "push",
            False,
            datetime.fromisoformat("2026-07-12T12:00:00+03:00"),
        )
        self.assertEqual(report["status"], "blocked")
        self.assertIn("production_enabled=false", report["blockers"])
        self.assertIn("golden fixtures are forbidden in production", report["blockers"])

    def test_stale_candidate_is_blocked_even_when_enabled(self) -> None:
        config = dict(self.config, production_enabled=True)
        manifest = json.loads(json.dumps(self.manifest))
        manifest["release_kind"] = "production"
        manifest["production_eligible"] = True
        report = gate.validate_gate(
            config,
            manifest,
            "refs/heads/main",
            "workflow_dispatch",
            True,
            datetime.fromisoformat("2026-07-15T12:00:00+03:00"),
        )
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["fresh_candidate"])

    def test_fresh_production_candidate_can_be_ready(self) -> None:
        config = dict(self.config, production_enabled=True)
        manifest = json.loads(json.dumps(self.manifest))
        manifest["release_kind"] = "production"
        manifest["production_eligible"] = True
        manifest["published_at"] = "2026-07-12T07:00:00+03:00"
        report = gate.validate_gate(
            config,
            manifest,
            "refs/heads/main",
            "workflow_dispatch",
            True,
            datetime.fromisoformat("2026-07-12T08:00:00+03:00"),
        )
        self.assertEqual(report["status"], "ready", report["blockers"])

    def test_missing_manual_approval_blocks(self) -> None:
        config = dict(self.config, production_enabled=True)
        manifest = json.loads(json.dumps(self.manifest))
        manifest["release_kind"] = "production"
        manifest["production_eligible"] = True
        manifest["published_at"] = "2026-07-12T07:00:00+03:00"
        report = gate.validate_gate(
            config,
            manifest,
            "refs/heads/main",
            "workflow_dispatch",
            False,
            datetime.fromisoformat("2026-07-12T08:00:00+03:00"),
        )
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["checks"]["manual_approval"])


class HashTests(unittest.TestCase):
    def test_tree_digest_changes_after_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.txt").write_text("one", encoding="utf-8")
            before = release_common.tree_digest(root)
            (root / "a.txt").write_text("two", encoding="utf-8")
            after = release_common.tree_digest(root)
            self.assertNotEqual(before, after)

    def test_file_manifest_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target.txt"
            target.write_text("x", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("Symlinks are unavailable")
            with self.assertRaises(RuntimeError):
                release_common.file_manifest(root)


if __name__ == "__main__":
    unittest.main()
