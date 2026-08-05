from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coverage = load_module("story_coverage", SCRIPTS / "story_coverage.py")
audit = load_module("ensure_story_coverage", SCRIPTS / "ensure_story_coverage.py")


def story(geography: str) -> dict[str, str]:
    return {"section": geography, "geography": geography, "headline": geography}


def candidate(
    *,
    geography: str,
    url: str,
    title: str,
    published_date: str = "2026-07-23",
) -> dict[str, object]:
    return {
        "title": title,
        "organization": title,
        "published_date": published_date,
        "published_at": None,
        "time_precision": "date",
        "topic": title,
        "event_type": "product_launch",
        "keywords": [title, "ИИ"],
        "geography": geography,
        "category": "enterprise" if geography == "russia" else "models",
        "source_type": "official",
        "primary_source": {
            "title": title,
            "publisher": title,
            "url": url,
        },
        "supporting_sources": [],
        "event_summary": f"Событие {title}",
        "verified_facts": ["Факт один", "Факт два"],
        "significance": "Существенное событие",
        "significance_score": 4,
        "limitations": "Официальный анонс",
        "archive_status": "none",
        "archive_reason": "В архиве отсутствует",
        "recommendation": "include",
    }


class StoryCoverageTests(unittest.TestCase):
    def test_seven_stories_are_full_regardless_of_regional_mix(self) -> None:
        result = coverage.coverage_summary(
            [story("world") for _ in range(6)] + [story("russia")]
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["usual_target_met"])
        self.assertFalse(result["short_digest"])
        self.assertEqual(
            result["counts"],
            {"total": 7, "world": 6, "russia": 1, "unknown": 0},
        )

    def test_two_world_stories_are_a_publishable_short_digest(self) -> None:
        result = coverage.coverage_summary(
            [story("world"), story("world")]
        )
        self.assertTrue(result["valid"])
        self.assertTrue(result["publication_allowed"])
        self.assertTrue(result["short_digest"])
        self.assertEqual(result["missing_to_usual"], 5)
        self.assertEqual(result["counts"]["russia"], 0)

    def test_empty_digest_is_not_publishable(self) -> None:
        result = coverage.coverage_summary([])
        self.assertFalse(result["valid"])
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(result["status"], "empty")

    def test_merge_deduplicates_tracking_variants_and_rejects_old_date(self) -> None:
        base_candidate = candidate(
            geography="world",
            url="https://example.com/news?utm_source=x",
            title="Base",
        )
        base_candidate["id"] = "cand-001"
        research = {
            "status": "ok",
            "error_message": None,
            "publication_date": "2026-07-24",
            "search_window": {
                "start_at": "2026-07-23T07:00:00+03:00",
                "end_at": "2026-07-24T06:00:00+03:00",
                "start_date": "2026-07-23",
                "end_date": "2026-07-24",
                "latest_archive_at": "2026-07-23T07:00:00+03:00",
                "latest_archive_date": "2026-07-23",
            },
            "coverage": [],
            "candidates": [base_candidate],
            "rejected_as_duplicates": [],
            "research_notes": "base",
        }
        duplicate = candidate(
            geography="world",
            url="https://example.com/news",
            title="Duplicate",
        )
        old = candidate(
            geography="russia",
            url="https://example.ru/old",
            title="Old",
            published_date="2026-07-22",
        )
        fresh = candidate(
            geography="russia",
            url="https://example.ru/fresh",
            title="Fresh",
        )
        merged, accepted, rejected = coverage.merge_candidates(
            research, [duplicate, old, fresh]
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["title"], "Fresh")
        self.assertEqual(len(merged["candidates"]), 2)
        self.assertEqual([item["id"] for item in merged["candidates"]], ["cand-001", "cand-002"])
        rejection_text = json.dumps(rejected, ensure_ascii=False)
        self.assertIn("дубликат", rejection_text)
        self.assertIn("вне редакционного окна", rejection_text)

    def test_prompt_is_targeted_and_bounded(self) -> None:
        prompt = audit.build_prompt(
            "{{PUBLICATION_DATE}}|{{SEARCH_WINDOW_START_AT}}|{{SEARCH_WINDOW_END_AT}}|"
            "{{MISSING_TOTAL}}|{{MAX_WEB_SEARCH_CALLS}}|"
            "{{EXISTING_CANDIDATES}}|{{ARCHIVE_INDEX}}",
            publication_date="2026-07-25",
            search_window={
                "start_at": "2026-07-24T06:00:00+03:00",
                "end_at": "2026-07-25T06:00:00+03:00",
            },
            missing_total=5,
            maximum_web_search_calls=5,
            existing_candidates=[{"title": "Existing"}],
            archive={"items": [{"date": "2026-07-24", "title": "Archive"}]},
        )
        self.assertIn("2026-07-25", prompt)
        self.assertIn("|5|5|", prompt)
        self.assertIn("Existing", prompt)
        self.assertIn("Archive", prompt)

    def test_final_validator_accepts_seven_with_one_russian_story(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            artifact.mkdir()
            (artifact / "stories.json").write_text(
                json.dumps(
                    [story("world") for _ in range(6)] + [story("russia")],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (artifact / "digest.json").write_text(
                json.dumps(
                    {
                        "short_digest": False,
                        "article_html": "<p>Обычный выпуск.</p>",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report = root / "report.json"
            import subprocess
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_story_coverage.py"),
                    "--artifact-dir",
                    str(artifact),
                    "--usual-total",
                    "7",
                    "--minimum-publishable",
                    "1",
                    "--report",
                    str(report),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["counts"]["russia"], 1)

    def test_final_validator_accepts_short_digest_without_regional_sections(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            artifact.mkdir()
            (artifact / "stories.json").write_text(
                json.dumps(
                    [story("world"), story("world")],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (artifact / "digest.json").write_text(
                json.dumps(
                    {
                        "short_digest": True,
                        "article_html": (
                            "<p><em>Новостей сегодня меньше, чем обычно</em></p>"
                            "<p>Короткий выпуск.</p>"
                        ),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report = root / "report.json"
            import subprocess
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_story_coverage.py"),
                    "--artifact-dir",
                    str(artifact),
                    "--usual-total",
                    "7",
                    "--minimum-publishable",
                    "1",
                    "--report",
                    str(report),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["publication_mode"], "short")
            self.assertEqual(payload["counts"]["russia"], 0)

    def test_final_validator_rejects_more_than_one_curiosity_story(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            artifact.mkdir()
            (artifact / "stories.json").write_text(
                json.dumps(
                    [
                        {"geography": "world", "category": "curiosity"},
                        {"geography": "world", "category": "curiosity"},
                    ]
                ),
                encoding="utf-8",
            )
            (artifact / "digest.json").write_text(
                json.dumps(
                    {
                        "short_digest": True,
                        "article_html": (
                            "<p><em>Новостей сегодня меньше, чем обычно</em></p>"
                            "<p>Короткий выпуск.</p>"
                        ),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report = root / "report.json"
            import subprocess

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_story_coverage.py"),
                    "--artifact-dir",
                    str(artifact),
                    "--report",
                    str(report),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertIn("не более одного", " ".join(payload["errors"]))


class CoverageAuditExecutionTests(unittest.TestCase):
    def test_audit_metadata_separates_completed_calls_from_output_items(
        self,
    ) -> None:
        items = [
            types.SimpleNamespace(
                type="web_search_call",
                id=f"ws_{index}",
                status="completed" if index < 5 else "failed",
                action={
                    "type": "search",
                    "query": f"query-{index}",
                    "sources": [
                        {
                            "title": f"Source {index}",
                            "url": f"https://example.com/source-{index}",
                        }
                    ],
                },
            )
            for index in range(6)
        ]
        response = types.SimpleNamespace(
            id="resp_mixed",
            status="completed",
            model="gpt-5.6-terra",
            output=items,
            usage={"input_tokens": 1, "output_tokens": 1},
            error=None,
            incomplete_details=None,
        )

        metadata = audit.build_audit_api_metadata(
            response,
            maximum_web_search_calls=5,
        )

        self.assertEqual(metadata["web_search_calls_completed"], 5)
        self.assertEqual(metadata["web_search_call_items_total"], 6)
        self.assertEqual(metadata["configured_web_search_limit"], 5)
        self.assertEqual(metadata["observed_web_search_calls"], 6)
        self.assertFalse(metadata["budget_overrun"])
        self.assertFalse(metadata["completed_call_limit_exceeded"])
        self.assertTrue(metadata["output_item_limit_exceeded"])
        self.assertEqual(metadata["web_search_search_operations_total"], 6)
        self.assertEqual(metadata["web_search_navigation_items_total"], 0)
        self.assertEqual(
            metadata["web_search_call_statuses"],
            {"completed": 5, "failed": 1},
        )
        self.assertEqual(metadata["actual_queries"], [f"query-{i}" for i in range(6)])
        self.assertEqual(len(metadata["consulted_sources"]), 6)

    def test_complete_artifact_is_noop_without_openai(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            artifact.mkdir()
            stories = [story("world") for _ in range(5)] + [story("russia") for _ in range(2)]
            (artifact / "stories.json").write_text(
                json.dumps(stories, ensure_ascii=False), encoding="utf-8"
            )
            candidates = []
            for index in range(5):
                item = candidate(
                    geography="world",
                    url=f"https://example.com/world-{index}",
                    title=f"World {index}",
                )
                item["id"] = f"cand-{index + 1:03d}"
                candidates.append(item)
            for index in range(2):
                item = candidate(
                    geography="russia",
                    url=f"https://example.ru/russia-{index}",
                    title=f"Russia {index}",
                )
                item["id"] = f"cand-{index + 6:03d}"
                candidates.append(item)
            research = {
                "status": "ok",
                "candidates": candidates,
                "search_window": {
                    "start_at": "2026-07-23T07:00:00+03:00",
                    "end_at": "2026-07-24T06:00:00+03:00",
                    "start_date": "2026-07-23",
                    "end_date": "2026-07-24",
                },
            }
            (artifact / "candidates.json").write_text(
                json.dumps(research, ensure_ascii=False), encoding="utf-8"
            )
            (artifact / "run-info.json").write_text("{}", encoding="utf-8")
            (artifact / "digest.json").write_text(
                json.dumps(
                    {
                        "short_digest": False,
                        "article_html": "<p>Обычный выпуск.</p>",
                        "editorial_notes": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            archive = root / "archive.json"
            archive.write_text('{"items": []}', encoding="utf-8")
            report = root / "coverage-audit.json"
            argv = [
                "ensure_story_coverage.py",
                "--artifact-dir",
                str(artifact),
                "--archive",
                str(archive),
                "--publication-date",
                "2026-07-24",
                "--model",
                "gpt-5.6-terra",
                "--report",
                str(report),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                audit, "run_audit_request", side_effect=AssertionError("API must not run")
            ):
                self.assertEqual(audit.main(), 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "existing_full_digest")
            self.assertFalse(payload["web_search_performed"])

    def test_legacy_incomplete_audit_cannot_publish_short_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            artifact.mkdir()
            stories = [story("world"), story("world")]
            (artifact / "stories.json").write_text(
                json.dumps(stories, ensure_ascii=False),
                encoding="utf-8",
            )
            candidates = []
            for index in range(2):
                item = candidate(
                    geography="world",
                    url=f"https://example.com/world-{index}",
                    title=f"World {index}",
                )
                item["id"] = f"cand-{index + 1:03d}"
                candidates.append(item)
            research = {
                "status": "ok",
                "candidates": candidates,
                "search_window": {
                    "start_at": "2026-07-30T06:00:00+03:00",
                    "end_at": "2026-07-31T06:00:00+03:00",
                    "start_date": "2026-07-30",
                    "end_date": "2026-07-31",
                },
            }
            (artifact / "candidates.json").write_text(
                json.dumps(research, ensure_ascii=False),
                encoding="utf-8",
            )
            (artifact / "run-info.json").write_text("{}", encoding="utf-8")
            (artifact / "digest.json").write_text(
                json.dumps(
                    {
                        "short_digest": True,
                        "article_html": (
                            "<p><em>Новостей сегодня меньше, чем обычно</em></p>"
                            "<p>Два достойных сюжета.</p>"
                        ),
                        "editorial_notes": [
                            {
                                "type": "regional_gap",
                                "area": "russian_ai",
                                "message": (
                                    "Legacy: выбрано 0 российских сюжетов "
                                    "при цели 2."
                                ),
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            archive = root / "archive.json"
            archive.write_text('{"items": []}', encoding="utf-8")
            report = root / "coverage-audit.json"
            report.write_text(
                json.dumps(
                    {
                        "status": "error",
                        "publication_date": "2026-07-31",
                        "web_search_performed": False,
                        "api": None,
                        "error": (
                            "RuntimeError: Coverage audit превысил лимит "
                            "web search: 6>5"
                        ),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            argv = [
                "ensure_story_coverage.py",
                "--artifact-dir",
                str(artifact),
                "--archive",
                str(archive),
                "--publication-date",
                "2026-07-31",
                "--model",
                "gpt-5.6-terra",
                "--report",
                str(report),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                audit,
                "run_audit_request",
                side_effect=AssertionError("paid audit must not repeat"),
            ):
                self.assertEqual(audit.main(), 1)

            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "error")
            self.assertFalse(payload["prior_audit_reused"])
            self.assertIn("заблокированы", payload["error"])
            digest = json.loads(
                (artifact / "digest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(digest["short_digest"])
            self.assertTrue(
                digest["article_html"].startswith(
                    "<p><em>Новостей сегодня меньше, чем обычно</em></p>"
                )
            )
            self.assertIn(
                "regional_gap",
                {
                    item.get("type")
                    for item in digest["editorial_notes"]
                    if isinstance(item, dict)
                },
                "fail-closed audit must leave the pre-existing artifact untouched",
            )

    def test_api_request_has_hard_tool_call_cap(self) -> None:
        captured: dict[str, object] = {}

        class Item:
            type = "web_search_call"

            def __init__(self, index: int) -> None:
                self.id = f"ws_{index}"
                self.status = "completed"
                self.action = {
                    "type": "search",
                    "query": f"query-{index}",
                    "sources": [],
                }

        class Response:
            status = "completed"
            output_text = json.dumps(
                {
                    "status": "complete_with_gaps",
                    "error_message": None,
                    "direction_id": "general_coverage_gaps",
                    "candidates": [],
                    "rejections": [],
                    "notes": "Новых достойных кандидатов нет",
                },
                ensure_ascii=False,
            )
            # Reproduces run 30602601828: the response contains six completed
            # items even though max_tool_calls=5. The useful payload must not
            # be discarded.
            output = [Item(index) for index in range(6)]
            id = "resp_test"
            model = "gpt-5.6-terra"
            usage = {"input_tokens": 1, "output_tokens": 1}

        class Responses:
            def create(self, **kwargs):
                captured.update(kwargs)
                return Response()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.responses = Responses()

        fake_module = types.ModuleType("openai")
        fake_module.OpenAI = FakeOpenAI
        with mock.patch.dict(sys.modules, {"openai": fake_module}):
            payload, metadata = audit.run_audit_request(
                api_key="secret",
                model="gpt-5.6-terra",
                prompt="targeted",
                maximum_web_search_calls=5,
            )
        self.assertEqual(captured["max_tool_calls"], 5)
        self.assertEqual(captured["tool_choice"], "required")
        self.assertFalse(captured["store"])
        self.assertEqual(metadata["web_search_calls"], 6)
        self.assertEqual(metadata["configured_web_search_limit"], 5)
        self.assertEqual(metadata["observed_web_search_calls"], 6)
        self.assertTrue(metadata["budget_overrun"])
        self.assertTrue(metadata["completed_call_limit_exceeded"])
        self.assertEqual(metadata["configured_max_tool_calls"], 5)
        self.assertEqual(payload["status"], "complete_with_gaps")


class ConfigurationContractTests(unittest.TestCase):
    def test_config_contains_fail_closed_short_digest_contract(self) -> None:
        config = json.loads(
            (ROOT / "automation/config/production-daily.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["minimum_selected_stories"], 7)
        self.assertEqual(config["minimum_publishable_stories"], 1)
        self.assertFalse(config["regional_story_quotas_enabled"])
        self.assertTrue(config["coverage_audit_failure_blocks_publication"])
        self.assertNotIn("minimum_world_selected_stories", config)
        self.assertNotIn("minimum_russian_selected_stories", config)
        self.assertTrue(config["coverage_audit_enabled"])
        self.assertEqual(config["research_max_web_search_calls"], 12)
        self.assertEqual(config["coverage_audit_max_web_search_calls"], 7)
        self.assertEqual(
            config["coverage_audit_minimum_required_web_search_calls"], 6
        )
        editorial = json.loads(
            (ROOT / "automation/config/editorial.json").read_text(encoding="utf-8")
        )
        self.assertEqual(editorial["story_counts"]["total_target_minimum"], 7)
        self.assertFalse(
            editorial["story_counts"]["regional_story_quotas_enabled"]
        )
        self.assertNotIn("world_target_minimum", editorial["story_counts"])
        self.assertNotIn("russian_target_minimum", editorial["story_counts"])
        self.assertEqual(editorial["spec_version"], "2026-08-05")
        self.assertEqual(
            editorial["candidate_selection"]["maximum_selected_curiosity_stories"],
            1,
        )
        self.assertEqual(
            editorial["candidate_selection"]["legal_scale_required_for_selection"],
            "major",
        )

    def test_prompts_describe_final_contract(self) -> None:
        editorial = (ROOT / "automation/prompts/daily_digest.md").read_text(encoding="utf-8")
        research = (ROOT / "automation/prompts/research_candidates.md").read_text(encoding="utf-8")
        self.assertIn(
            "Числовых квот для китайских и российских новостей нет",
            editorial,
        )
        self.assertIn(
            "отсутствие дополнений не является ошибкой",
            editorial,
        )
        self.assertIn(
            "Числовых квот для китайских и российских",
            research,
        )


if __name__ == "__main__":
    unittest.main()
