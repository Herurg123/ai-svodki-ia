from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
AGENTS = ROOT / "AGENTS.md"
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


class ActionsOperatorLanguageTests(unittest.TestCase):
    def workflows(self) -> list[Path]:
        return sorted([*WORKFLOW_ROOT.glob("*.yml"), *WORKFLOW_ROOT.glob("*.yaml")])

    def test_every_active_workflow_has_operator_summary(self) -> None:
        workflows = self.workflows()
        self.assertTrue(workflows)
        for path in workflows:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    "GITHUB_STEP_SUMMARY",
                    text,
                    f"{path.name} must leave a repository-controlled Russian Actions Summary",
                )

    def test_dispatch_input_descriptions_are_russian(self) -> None:
        description = re.compile(r"(?m)^\s+description:\s*[\"']?(.*?)[\"']?\s*$")
        for path in self.workflows():
            text = path.read_text(encoding="utf-8")
            for value in description.findall(text):
                with self.subTest(workflow=path.name, description=value):
                    self.assertRegex(
                        value,
                        CYRILLIC,
                        f"{path.name} exposes a non-Russian input description: {value}",
                    )

    def test_repository_authored_annotations_are_russian(self) -> None:
        for path in self.workflows():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not re.search(r"::(?:error|warning|notice)\b", line):
                    continue
                with self.subTest(workflow=path.name, line=line.strip()):
                    self.assertRegex(
                        line,
                        CYRILLIC,
                        f"{path.name} has a non-Russian GitHub annotation",
                    )

    def test_explicit_workflow_error_messages_are_russian(self) -> None:
        stderr_echo = re.compile(r'echo\s+"([^"]+)"\s*>&2')
        system_exit = re.compile(
            r"raise\s+SystemExit\(\s*f?[\"']([^\"']+)[\"']",
            re.DOTALL,
        )
        for path in self.workflows():
            text = path.read_text(encoding="utf-8")
            messages = stderr_echo.findall(text) + system_exit.findall(text)
            for message in messages:
                with self.subTest(workflow=path.name, message=message):
                    self.assertRegex(
                        message,
                        CYRILLIC,
                        f"{path.name} has a repository-authored operator error without Russian text",
                    )

    def test_old_english_operator_messages_do_not_return(self) -> None:
        forbidden = (
            "successful no-op",
            "Already published:",
            "Paid API calls:",
            "Path classification did not succeed",
            "is required but finished as",
            "routing is inconsistent",
            "FTP deployment is allowed only from main",
            "Local posts/ directory is missing",
            "retention_days must be an integer",
            "retention_days must be at least",
            "main changed while generation was running; refusing to push",
            "main changed while cleanup was running; refusing to push",
            "Manual fresh research requested",
            "No reusable artifact selected",
            "Unexpected text model",
            "Unexpected image model",
        )
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in self.workflows()
        )
        for message in forbidden:
            with self.subTest(message=message):
                self.assertNotIn(message, combined)

    def test_agents_prescribes_russian_operator_surface(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn(
            "Repository-controlled operator-facing GitHub Actions text must be in Russian.",
            text,
        )
        self.assertIn("GITHUB_STEP_SUMMARY", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn("::error", text)


if __name__ == "__main__":
    unittest.main()
