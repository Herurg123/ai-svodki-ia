from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
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
orchestrator_common = load("orchestrator_common")
publication = load("create_publication_plan")
snapshotter = load("create_rollback_snapshot")
rollback = load("create_rollback_plan")
simulator = load("simulate_release_and_rollback")
contract = load("validate_orchestrator_contract")
workflow_safety = load("validate_workflow_safety")


class OrchestratorFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.live = self.root / "posts"
        self.candidate = self.root / "automation/preview/candidate/posts"
        self.output = self.root / "automation/preview/production-orchestrator/test"
        self.live.mkdir(parents=True)
        self.candidate.mkdir(parents=True)

        self.write(self.live, "index.html", "old-index")
        self.write(self.live, "rss.xml", "old-rss")
        self.write(self.live, "2026-07-10/index.html", "old-post")
        self.write(self.live, "images/old.png", "old-image")

        self.write(self.candidate, "index.html", "new-index")
        self.write(self.candidate, "rss.xml", "new-rss")
        self.write(self.candidate, "2026-07-10/index.html", "old-post")
        self.write(self.candidate, "2026-07-11/index.html", "new-post")
        self.write(self.candidate, "images/new.png", "new-image")

        self.config = {
            "publication_enabled": False,
            "rollback_execution_enabled": False,
            "simulation_only": True,
            "allow_golden_fixture_publication": False,
            "allow_repository_write": False,
            "allow_ftp": False,
            "allow_external_network": False,
            "allow_schedule": False,
            "live_posts_directory": "posts",
            "preview_root": "automation/preview/production-orchestrator",
            "allowed_preview_roots": [
                "automation/preview/production-orchestrator",
                "automation/preview/rollback-drill",
            ],
        }
        self.release_manifest = {
            "status": "ok",
            "release_id": "golden-test",
            "release_kind": "golden_fixture",
            "production_eligible": False,
        }
        self.gate_report = {"status": "blocked", "blockers": ["production_enabled=false"]}

        # The production modules resolve paths against their module-level ROOT.
        self.root_modules = (
            release_common,
            publication,
            snapshotter,
            rollback,
            simulator,
            contract,
            workflow_safety,
        )
        self.original_roots = {}
        for module in self.root_modules:
            if hasattr(module, "ROOT"):
                self.original_roots[module] = module.ROOT
                module.ROOT = self.root

    def tearDown(self) -> None:
        for module, original in self.original_roots.items():
            module.ROOT = original
        self.temp.cleanup()

    @staticmethod
    def write(root: Path, relative: str, value: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def write_json(self, relative: str, payload: dict) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def build_plans(self):
        release_path = self.write_json(
            "automation/preview/production-orchestrator/test/release-manifest.json",
            self.release_manifest,
        )
        publication_path = self.output / "publication-plan.json"
        plan = publication.create_plan(
            self.config,
            self.release_manifest,
            self.gate_report,
            self.live,
            self.candidate,
            publication_path,
        )
        snapshot_dir = self.output / "rollback-snapshot"
        snapshot_path = self.output / "rollback-snapshot.json"
        snapshot = snapshotter.create_snapshot(self.live, snapshot_dir, snapshot_path)
        rollback_path = self.output / "rollback-plan.json"
        rollback_plan = rollback.create_plan(
            self.config,
            snapshot,
            self.candidate,
            rollback_path,
        )
        return release_path, plan, publication_path, snapshot, snapshot_dir, snapshot_path, rollback_plan, rollback_path


class PathSafetyTests(unittest.TestCase):
    def test_path_traversal_is_rejected(self) -> None:
        for value in ("../posts/index.html", "/tmp/file", "", ".."): 
            with self.assertRaises(RuntimeError):
                orchestrator_common.validate_relative_path(value)



class PublicationPlanTests(OrchestratorFixture):
    def test_publication_plan_is_blocked_and_exact(self) -> None:
        _, plan, *_ = self.build_plans()
        self.assertEqual(plan["status"], "blocked")
        self.assertFalse(plan["execution_allowed"])
        self.assertGreater(plan["summary"]["total"], 0)
        expected = orchestrator_common.diff_manifests(
            release_common.file_manifest(self.live),
            release_common.file_manifest(self.candidate),
        )
        self.assertEqual(plan["operations"], expected)
        self.assertIn("golden fixture publication is forbidden", plan["blockers"])

    def test_snapshot_is_exact_copy(self) -> None:
        _, _, _, snapshot, snapshot_dir, *_ = self.build_plans()
        copied = snapshot_dir / "posts"
        self.assertEqual(snapshot["files"], release_common.file_manifest(self.live))
        self.assertEqual(snapshot["tree_sha256"], release_common.tree_digest(copied))
        self.assertFalse(snapshot["actual_production_changed"])

    def test_rollback_plan_restores_snapshot(self) -> None:
        *_, rollback_plan, _ = self.build_plans()
        self.assertEqual(rollback_plan["status"], "blocked")
        self.assertFalse(rollback_plan["execution_allowed"])
        self.assertGreater(rollback_plan["summary"]["total"], 0)


class PreviewRootTests(OrchestratorFixture):
    def test_rollback_drill_root_is_allowed_for_both_plans(self) -> None:
        drill_root = self.root / "automation/preview/rollback-drill/test"
        publication_path = drill_root / "publication-plan.json"
        publication_plan = publication.create_plan(
            self.config,
            self.release_manifest,
            self.gate_report,
            self.live,
            self.candidate,
            publication_path,
        )
        snapshot_dir = drill_root / "rollback-snapshot"
        snapshot_path = drill_root / "rollback-snapshot.json"
        snapshot = snapshotter.create_snapshot(
            self.live,
            snapshot_dir,
            snapshot_path,
        )
        rollback_path = drill_root / "rollback-plan.json"
        rollback_plan = rollback.create_plan(
            self.config,
            snapshot,
            self.candidate,
            rollback_path,
        )
        self.assertEqual(publication_plan["status"], "blocked")
        self.assertEqual(rollback_plan["status"], "blocked")
        self.assertTrue(publication_path.is_file())
        self.assertTrue(rollback_path.is_file())

    def test_unlisted_preview_root_is_rejected(self) -> None:
        outside = self.root / "automation/preview/unlisted/plan.json"
        with self.assertRaises(RuntimeError):
            publication.create_plan(
                self.config,
                self.release_manifest,
                self.gate_report,
                self.live,
                self.candidate,
                outside,
            )

    def test_parent_traversal_in_allowed_root_is_rejected(self) -> None:
        config = dict(self.config)
        config["allowed_preview_roots"] = ["automation/preview/../outside"]
        with self.assertRaises(RuntimeError):
            publication.create_plan(
                config,
                self.release_manifest,
                self.gate_report,
                self.live,
                self.candidate,
                self.output / "publication-plan.json",
            )


class SimulationTests(OrchestratorFixture):
    def test_release_and_rollback_restore_original_tree(self) -> None:
        (
            release_path,
            plan,
            publication_path,
            snapshot,
            snapshot_dir,
            snapshot_path,
            rollback_plan,
            rollback_path,
        ) = self.build_plans()
        live_before = release_common.tree_digest(self.live)
        report_path = self.output / "rollback-drill.json"
        report = simulator.simulate(
            self.live,
            self.candidate,
            snapshot_dir / "posts",
            snapshot,
            plan,
            rollback_plan,
            self.output / "simulation",
            report_path,
        )
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["safety"]["live_posts_unchanged"])
        self.assertEqual(live_before, release_common.tree_digest(self.live))

        validation_path = self.output / "orchestrator-validation.json"
        validation = contract.validate(
            self.config,
            self.live,
            self.candidate,
            self.release_manifest,
            self.gate_report,
            plan,
            snapshot,
            rollback_plan,
            report,
            validation_path,
        )
        self.assertEqual(validation["status"], "ok", validation["errors"])

    def test_tampered_snapshot_is_rejected(self) -> None:
        (
            _,
            plan,
            _,
            snapshot,
            snapshot_dir,
            _,
            rollback_plan,
            _,
        ) = self.build_plans()
        (snapshot_dir / "posts/index.html").write_text("tampered", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            simulator.simulate(
                self.live,
                self.candidate,
                snapshot_dir / "posts",
                snapshot,
                plan,
                rollback_plan,
                self.output / "simulation",
                self.output / "rollback-drill.json",
            )


class WorkflowSafetyTests(OrchestratorFixture):
    def test_safe_workflow_is_accepted(self) -> None:
        path = self.root / ".github/workflows/safe.yml"
        path.parent.mkdir(parents=True)
        path.write_text(
            """name: Safe dry run
on:
  push:
    branches:
      - automation-prep
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - run: python automation/scripts/example.py
""",
            encoding="utf-8",
        )
        report = workflow_safety.validate_workflows(
            [Path(".github/workflows/safe.yml")],
            Path("automation/preview/safety.json"),
        )
        self.assertEqual(report["status"], "ok", report["errors"])

    def test_unsafe_workflow_is_rejected(self) -> None:
        path = self.root / ".github/workflows/unsafe.yml"
        path.parent.mkdir(parents=True)
        path.write_text(
            """name: Unsafe
on:
  schedule:
    - cron: '0 7 * * *'
permissions:
  contents: write
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - run: git push
""",
            encoding="utf-8",
        )
        report = workflow_safety.validate_workflows(
            [Path(".github/workflows/unsafe.yml")],
            Path("automation/preview/unsafe-safety.json"),
        )
        self.assertEqual(report["status"], "error")
        codes = {error["code"] for error in report["errors"]}
        self.assertIn("schedule_trigger", codes)
        self.assertIn("write_permission", codes)
        self.assertIn("repository_mutation", codes)


if __name__ == "__main__":
    unittest.main()
