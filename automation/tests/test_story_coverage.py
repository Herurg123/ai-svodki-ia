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
    def test_exact_five_world_two_russia_passes(self) -> None:
        result = coverage.coverage_summary(
            [story("world") for _ in range(5)]
            + [story("russia") for _ in range(2)]
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["counts"], {"total": 7, "world": 5, "russia": 2, "unknown": 0})

    def test_six_world_one_russia_fails(self) -> None:
        result = coverage.coverage_summary(
            [story("world") for _ in range(6)] + [story("russia")]
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing"]["russia"], 1)
        self.assertEqual(result["missing"]["total"], 0)

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
            "{{MISSING_WORLD}}|{{MISSING_RUSSIA}}|{{MAX_WEB_SEARCH_CALLS}}|"
            "{{EXISTING_CANDIDATES}}|{{ARCHIVE_INDEX}}",
            publication_date="2026-07-25",
            search_window={
                "start_at": "2026-07-24T06:00:00+03:00",
                "end_at": "2026-07-25T06:00:00+03:00",
            },
            missing_world=1,
            missing_russia=2,
            maximum_web_search_calls=5,
            existing_candidates=[{"title": "Existing"}],
            archive={"items": [{"date": "2026-07-24", "title": "Archive"}]},
        )
        self.assertIn("2026-07-25", prompt)
        self.assertIn("|1|2|5|", prompt)
        self.assertIn("Existing", prompt)
        self.assertIn("Archive", prompt)

    def test_final_validator_returns_error_before_image_for_six_plus_one(self) -> None:
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
            report = root / "report.json"
            import subprocess
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_story_coverage.py"),
                    "--artifact-dir",
                    str(artifact),
                    "--minimum-total",
                    "7",
                    "--minimum-world",
                    "5",
                    "--minimum-russia",
                    "2",
                    "--report",
                    str(report),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["counts"]["russia"], 1)


class CoverageAuditExecutionTests(unittest.TestCase):
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
            self.assertEqual(payload["mode"], "no_op")
            self.assertFalse(payload["web_search_performed"])

    def test_api_request_has_hard_tool_call_cap(self) -> None:
        captured: dict[str, object] = {}

        class Item:
            type = "web_search_call"

        class Response:
            status = "completed"
            output_text = json.dumps(
                {
                    "status": "ok",
                    "error_message": None,
                    "queries_used": [
                        {"area": "russia", "query": "q", "purpose": "p"}
                    ],
                    "candidates": [],
                    "notes": "Новых достойных кандидатов нет",
                },
                ensure_ascii=False,
            )
            output = [Item()]
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
        self.assertEqual(metadata["web_search_calls"], 1)
        self.assertEqual(payload["status"], "ok")


class ConfigurationContractTests(unittest.TestCase):
    def test_config_contains_hard_5_plus_2_contract(self) -> None:
        config = json.loads(
            (ROOT / "automation/config/production-daily.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["minimum_selected_stories"], 7)
        self.assertEqual(config["minimum_world_selected_stories"], 5)
        self.assertEqual(config["minimum_russian_selected_stories"], 2)
        self.assertTrue(config["coverage_audit_enabled"])
        self.assertEqual(config["coverage_audit_max_web_search_calls"], 5)
        editorial = json.loads(
            (ROOT / "automation/config/editorial.json").read_text(encoding="utf-8")
        )
        self.assertEqual(editorial["story_counts"]["total_target_minimum"], 7)
        self.assertEqual(editorial["story_counts"]["world_target_minimum"], 5)
        self.assertEqual(editorial["story_counts"]["russian_target_minimum"], 2)

    def test_prompts_describe_final_contract(self) -> None:
        editorial = (ROOT / "automation/prompts/daily_digest.md").read_text(encoding="utf-8")
        research = (ROOT / "automation/prompts/research_candidates.md").read_text(encoding="utf-8")
        self.assertIn("минимум 5 мировых", editorial)
        self.assertIn("минимум 2 российских", editorial)
        self.assertIn("5 мировых и 2 российских", research)


if __name__ == "__main__":
    unittest.main()
