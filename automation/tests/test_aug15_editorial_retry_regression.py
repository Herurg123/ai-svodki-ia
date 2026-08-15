from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Main CI intentionally runs without the paid OpenAI SDK. This regression uses
# only deterministic sanitation helpers, so keep the test offline rather than
# installing a transport dependency merely to import the module under test.
if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    sys.modules["openai"] = openai_stub

import generate_digest_preview as generator  # noqa: E402
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

AUG15_CANDIDATES = [
    {
        "id": "cand-001",
        "title": "OpenAI представила preview-режим Ultrafast для GPT-5.6 Sol",
        "organization": "OpenAI; Cerebras",
        "published_date": "2026-08-13",
        "published_at": "2026-08-13T12:22:00-07:00",
        "time_precision": "datetime",
    },
    {
        "id": "cand-002",
        "title": "Microsoft объединяет потребительский Copilot и Microsoft 365 Copilot",
        "organization": "Microsoft",
        "published_date": "2026-08-13",
        "published_at": "2026-08-13T08:30:00-07:00",
        "time_precision": "datetime",
    },
    {
        "id": "cand-003",
        "title": "Writer представила Palmyra X6 и обновлённый агентный harness",
        "organization": "Writer; Z.ai",
        "published_date": "2026-08-13",
        "published_at": "2026-08-13T14:13:00-07:00",
        "time_precision": "datetime",
    },
    {
        "id": "cand-004",
        "title": "Google сделала видимые водяные знаки в AI-генерациях опциональными",
        "organization": "Google; Gemini; Flow",
        "published_date": "2026-08-14",
        "published_at": "2026-08-14T09:13:00-07:00",
        "time_precision": "datetime",
    },
    {
        "id": "cand-005",
        "title": "Zayo строит более 8 000 миль магистрального оптоволокна",
        "organization": "Zayo; Nvidia",
        "published_date": "2026-08-13",
        "published_at": None,
        "time_precision": "date",
    },
]


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
            fake_generator = FakeGenerator()

            self.assertTrue(runner.patch_trusted_runtime_window(fake_generator, str(relative)))
            start_at, end_at = fake_generator.expected_search_window(None, {}, {})

            self.assertEqual(start_at.isoformat(), SAVED_WINDOW["start_at"])
            self.assertEqual(end_at.isoformat(), SAVED_WINDOW["end_at"])

    def test_real_aug15_five_candidate_pool_survives_retry_sanitation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture_root = self.configure_temp_repo(temp)
            handoff = fixture_root / ".coverage-audit-2026-08-15.json"
            research = {
                "search_window": SAVED_WINDOW,
                "candidates": AUG15_CANDIDATES,
            }
            handoff.write_text(json.dumps(research), encoding="utf-8")
            relative = handoff.relative_to(Path(temp))
            previous_expected_window = generator.expected_search_window
            try:
                self.assertTrue(
                    runner.patch_trusted_runtime_window(generator, str(relative))
                )
                sanitized, filtered, _warnings = generator.sanitize_research_candidates(
                    research,
                    date(2026, 8, 15),
                    {
                        "items": [
                            {
                                "date": "2026-08-14",
                                "published_at": "2026-08-14T06:00:00+03:00",
                                "search_cutoff_at": "2026-08-14T07:36:56+03:00",
                            }
                        ]
                    },
                    {"timezone": "Europe/Moscow", "publication_hour": 6},
                    cutoff_at=datetime.fromisoformat(SAVED_WINDOW["end_at"]),
                )
            finally:
                generator.expected_search_window = previous_expected_window

            self.assertEqual(filtered, [])
            self.assertEqual(
                [item["id"] for item in sanitized["candidates"]],
                ["cand-001", "cand-002", "cand-003", "cand-004", "cand-005"],
            )
            self.assertEqual(sanitized["search_window"]["start_at"], SAVED_WINDOW["start_at"])
            self.assertEqual(sanitized["search_window"]["end_at"], SAVED_WINDOW["end_at"])

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
