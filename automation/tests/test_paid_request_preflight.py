from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_paid_request_preflight.py"
)
SPEC = importlib.util.spec_from_file_location("paid_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
paid_preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = paid_preflight
SPEC.loader.exec_module(paid_preflight)


class PaidRequestPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-b", "automation-prep")
        self.git("config", "user.name", "CI Test")
        self.git("config", "user.email", "ci@example.invalid")
        (self.root / "automation/requests").mkdir(parents=True)
        (self.root / "automation/fixtures/research/2026-07-11").mkdir(parents=True)
        self.fixture_path = (
            self.root
            / "automation/fixtures/research/2026-07-11/candidates.json"
        )
        self.write_fixture("2026-07-11")
        self.write_request("editorial-resume-003")
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

    def write_fixture(self, publication_date: str) -> None:
        self.fixture_path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "publication_date": publication_date,
                    "candidates": [{"id": "cand-001"}],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def request_payload(self, request_id: str, mode: str = "editorial_only") -> dict:
        return {
            "enabled": True,
            "mode": mode,
            "research_input": (
                "automation/fixtures/research/2026-07-11/candidates.json"
                if mode == "editorial_only"
                else None
            ),
            "publication_date": "2026-07-11",
            "request_id": request_id,
            "minimum_candidates": 12,
            "minimum_russian_candidates": 2,
            "maximum_candidates": 20,
            "minimum_selected_stories": 6,
            "maximum_selected_stories": 12,
        }

    def write_request(self, request_id: str, mode: str = "editorial_only") -> None:
        path = self.root / paid_preflight.REQUEST_REL
        path.write_text(
            json.dumps(self.request_payload(request_id, mode), indent=2) + "\n",
            encoding="utf-8",
        )

    def commit_all(self, message: str) -> str:
        self.git("add", ".")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def validate(self, current: str):
        return paid_preflight.validate_preflight(
            repo_root=self.root,
            request_rel=paid_preflight.REQUEST_REL,
            before_sha=self.before,
            current_sha=current,
            expected_ref="refs/heads/automation-prep",
            actual_ref="refs/heads/automation-prep",
        )

    def test_valid_editorial_only_commit(self) -> None:
        self.write_request("editorial-resume-004")
        current = self.commit_all("request only")
        report, validated = self.validate(current)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["changed_files"], [paid_preflight.REQUEST_REL.as_posix()])
        self.assertEqual(validated.mode, "editorial_only")
        self.assertEqual(validated.fixture_candidates, 1)
        self.assertEqual(len(validated.fixture_sha256 or ""), 64)

    def test_mixed_commit_is_rejected(self) -> None:
        self.write_request("editorial-resume-004")
        (self.root / "README.md").write_text("mixed\n", encoding="utf-8")
        current = self.commit_all("mixed")
        with self.assertRaisesRegex(paid_preflight.PreflightError, "ровно"):
            self.validate(current)

    def test_unchanged_request_id_is_rejected(self) -> None:
        payload = self.request_payload("editorial-resume-003")
        payload["maximum_candidates"] = 19
        path = self.root / paid_preflight.REQUEST_REL
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        current = self.commit_all("same id")
        with self.assertRaisesRegex(paid_preflight.PreflightError, "не изменился"):
            self.validate(current)

    def test_reused_historical_request_id_is_rejected(self) -> None:
        self.write_request("editorial-resume-004")
        first_004 = self.commit_all("first 004")
        self.write_request("editorial-resume-005")
        self.commit_all("005")
        self.before = self.git("rev-parse", "HEAD").strip()
        self.write_request("editorial-resume-004")
        current = self.commit_all("reuse 004")
        self.assertTrue(first_004)
        with self.assertRaisesRegex(paid_preflight.PreflightError, "уже использовался"):
            self.validate(current)

    def test_fixture_date_mismatch_is_rejected(self) -> None:
        self.write_request("editorial-resume-004")
        self.write_fixture("2026-07-12")
        current = self.commit_all("fixture mismatch")
        # The mixed-file guard should fire first in a real paid push.
        with self.assertRaisesRegex(paid_preflight.PreflightError, "ровно"):
            self.validate(current)

        # Validate the request payload directly to isolate fixture integrity.
        payload = paid_preflight.load_json(
            self.root / paid_preflight.REQUEST_REL,
            paid_preflight.REQUEST_REL.as_posix(),
        )
        with self.assertRaisesRegex(paid_preflight.PreflightError, "не совпадает"):
            paid_preflight.validate_request_payload(payload, self.root)

    def test_full_mode_requires_null_research_input(self) -> None:
        payload = self.request_payload("full-001", mode="full")
        validated = paid_preflight.validate_request_payload(payload, self.root)
        self.assertEqual(validated.mode, "full")
        self.assertEqual(validated.research_input, "")
        self.assertIsNone(validated.fixture_sha256)

    def test_wrong_branch_is_rejected(self) -> None:
        self.write_request("editorial-resume-004")
        current = self.commit_all("request only")
        with self.assertRaisesRegex(paid_preflight.PreflightError, "разрешён только"):
            paid_preflight.validate_preflight(
                repo_root=self.root,
                request_rel=paid_preflight.REQUEST_REL,
                before_sha=self.before,
                current_sha=current,
                expected_ref="refs/heads/automation-prep",
                actual_ref="refs/heads/main",
            )


if __name__ == "__main__":
    unittest.main()
