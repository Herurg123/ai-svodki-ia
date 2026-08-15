from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_digest_preview as runner  # noqa: E402
from editorial_policy_runtime import (  # noqa: E402
    primary_subject_is_asia,
    wrap_validator,
)

SAVED_WINDOW = {
    "start_at": "2026-08-13T07:36:56+03:00",
    "end_at": "2026-08-15T06:48:32+03:00",
    "latest_archive_at": "2026-08-14T07:36:56+03:00",
}


class FakeGenerator:
    @staticmethod
    def parse_aware_datetime(value: str, field: str) -> datetime:
        del field
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise RuntimeError("timezone required")
        return parsed

    @staticmethod
    def expected_search_window(*args, **kwargs):
        raise AssertionError("canonical continuity must be replaced for trusted runtime")


class Aug15RetryWindowRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_root = runner.REPOSITORY_ROOT
        self.old_trusted = runner.TRUSTED_RUNTIME_RESEARCH_ROOT

    def tearDown(self) -> None:
        runner.REPOSITORY_ROOT = self.old_root
        runner.TRUSTED_RUNTIME_RESEARCH_ROOT = self.old_trusted

    def configure_temp_repo(self, temp: str) -> Path:
        root = Path(temp)
        fixture_root = root / "automation" / "fixtures" / "research"
        runtime_root = fixture_root / ".runtime"
        runtime_root.mkdir(parents=True)
        runner.REPOSITORY_ROOT = root
        runner.TRUSTED_RUNTIME_RESEARCH_ROOT = runtime_root
        return fixture_root

    def test_coverage_handoff_preserves_both_saved_window_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture_root = self.configure_temp_repo(temp)
            handoff = fixture_root / ".coverage-audit-2026-08-15.json"
            handoff.write_text(
                json.dumps({"search_window": SAVED_WINDOW, "candidates": [1, 2, 3, 4, 5]}),
                encoding="utf-8",
            )
            relative = handoff.relative_to(Path(temp))
            generator = FakeGenerator()

            self.assertTrue(runner.patch_trusted_runtime_window(generator, str(relative)))
            start_at, end_at = generator.expected_search_window(None, {}, {})

            self.assertEqual(start_at.isoformat(), SAVED_WINDOW["start_at"])
            self.assertEqual(end_at.isoformat(), SAVED_WINDOW["end_at"])

    def test_arbitrary_fixture_cannot_override_continuity_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture_root = self.configure_temp_repo(temp)
            fixture = fixture_root / "caller-supplied.json"
            fixture.write_text(json.dumps({"search_window": SAVED_WINDOW}), encoding="utf-8")

            self.assertIsNone(
                runner._trusted_runtime_research_path(str(fixture.relative_to(Path(temp))))
            )

    def test_reversed_coverage_window_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture_root = self.configure_temp_repo(temp)
            handoff = fixture_root / ".coverage-audit-2026-08-15.json"
            handoff.write_text(
                json.dumps(
                    {
                        "search_window": {
                            "start_at": SAVED_WINDOW["end_at"],
                            "end_at": SAVED_WINDOW["start_at"],
                        }
                    }
                ),
                encoding="utf-8",
            )
            relative = handoff.relative_to(Path(temp))

            with self.assertRaisesRegex(RuntimeError, "start_at > end_at"):
                runner.patch_trusted_runtime_window(FakeGenerator(), str(relative))


class Aug15AsiaSubjectRegressionTests(unittest.TestCase):
    policy = {
        "tracked_asia_organizations": ["Z.ai", "DeepSeek"],
        "article": {"china_heading": "Китайские лидеры ИИ"},
    }
    china_error = (
        "При выбранных китайских сюжетах заголовок «Китайские лидеры ИИ» "
        "должен встречаться ровно один раз."
    )

    def test_secondary_zai_reference_does_not_make_writer_story_chinese(self) -> None:
        candidate = {
            "title": "Writer представила Palmyra X6 и обновлённый агентный harness",
            "organization": "Writer; Z.ai",
        }
        self.assertFalse(primary_subject_is_asia(candidate, self.policy))

    def test_primary_zai_story_remains_chinese(self) -> None:
        candidate = {
            "title": "Z.ai представила новую модель",
            "organization": "Z.ai; Partner",
        }
        self.assertTrue(primary_subject_is_asia(candidate, self.policy))

    def test_runtime_filters_only_false_secondary_reference_error(self) -> None:
        def original(article_html, selected, short_digest, policy):
            del article_html, selected, short_digest, policy
            return [self.china_error, "other error"], [], {}

        wrapped = wrap_validator(original)
        writer = {
            "title": "Writer представила Palmyra X6",
            "organization": "Writer; Z.ai",
        }
        errors, warnings, _ = wrapped("<p>x</p>", [writer], False, self.policy)

        self.assertEqual(errors, ["other error"])
        self.assertTrue(any("вторичная организация" in item for item in warnings))

    def test_runtime_keeps_china_requirement_for_primary_asia_subject(self) -> None:
        def original(article_html, selected, short_digest, policy):
            del article_html, selected, short_digest, policy
            return [self.china_error], [], {}

        wrapped = wrap_validator(original)
        zai = {"title": "Z.ai выпустила модель", "organization": "Z.ai"}
        errors, warnings, _ = wrapped("<p>x</p>", [zai], False, self.policy)

        self.assertEqual(errors, [self.china_error])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
