from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
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
policy = load_module(
    "coverage_search_upgrade_policy",
    SCRIPTS / "ensure_story_coverage_policy.py",
)


SEARCH_WINDOW = {
    "start_at": "2026-07-28T06:00:00+03:00",
    "end_at": "2026-08-01T06:00:00+03:00",
    "start_date": "2026-07-28",
    "end_date": "2026-08-01",
}


def candidate(
    title: str,
    url: str,
    *,
    category: str = "security",
    published_date: str = "2026-07-31",
    source_type: str = "technology_media",
    score: int = 4,
    verification_status: str = "verified",
    freshness_status: str = "new_event",
    legal_scale: str = "not_applicable",
    legal_scale_reason: str = "",
    curiosity_eligible: bool = False,
    curiosity_verification: str = "",
) -> dict[str, object]:
    return {
        "title": title,
        "organization": title,
        "published_date": published_date,
        "published_at": None,
        "time_precision": "date",
        "topic": title,
        "event_type": (
            "security_disclosure"
            if category == "security"
            else ("court_decision" if category == "legal" else "product_launch")
        ),
        "keywords": ["ИИ", category],
        "geography": "world",
        "category": category,
        "source_type": source_type,
        "primary_source": {
            "title": title,
            "publisher": "Regression source",
            "url": url,
        },
        "supporting_sources": [],
        "event_summary": f"Проверяемое событие: {title}",
        "verified_facts": ["Подтверждённый факт 1", "Подтверждённый факт 2"],
        "significance": "Самостоятельная значимая новость",
        "significance_score": score,
        "limitations": "Исторический регрессионный пример",
        "archive_status": "none",
        "archive_reason": "В архиве отсутствует",
        "recommendation": "include",
        "verification_status": verification_status,
        "verification_notes": "Проверены источник, дата и событие",
        "freshness_status": freshness_status,
        "freshness_reason": "Самостоятельное событие внутри редакционного окна",
        "legal_scale": legal_scale,
        "legal_scale_reason": legal_scale_reason,
        "curiosity_eligible": curiosity_eligible,
        "curiosity_verification": curiosity_verification,
    }


def direction_from_prompt(prompt: str) -> str:
    for direction_id in policy.AUDIT_DIRECTION_IDS:
        if f"Идентификатор направления: {direction_id}" in prompt:
            return direction_id
    raise AssertionError("direction id missing from prompt")


def successful_pass(
    direction_id: str,
    *,
    call_items: int = 1,
    completed_calls: int = 1,
    with_query: bool = True,
) -> tuple[dict[str, object], dict[str, object]]:
    query = f"{direction_id} AI news July 31 2026"
    return (
        {
            "status": "complete_with_gaps",
            "error_message": None,
            "direction_id": direction_id,
            "candidates": [],
            "rejections": [
                {
                    "title": "Проверенный слабый материал",
                    "url": "https://example.com/rejected",
                    "reason_code": "insufficient_significance",
                    "reason": "Недостаточно самостоятельной новостной ценности",
                }
            ],
            "notes": "Направление проверено, пригодных дополнений нет",
        },
        {
            "status": "completed",
            "web_search_calls": completed_calls,
            "web_search_calls_completed": completed_calls,
            "web_search_call_items_total": call_items,
            "web_search_call_statuses": {"completed": completed_calls},
            "actual_queries": [query] if with_query else [],
            "consulted_sources": [
                {
                    "title": "Checked source",
                    "url": f"https://example.com/{direction_id}",
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )


class AuditDirectionPlanTests(unittest.TestCase):
    def _run_plan(self, fake_request):
        with mock.patch.object(policy, "run_audit_request", side_effect=fake_request):
            return policy.execute_audit_plan(
                api_key="secret",
                model="gpt-5.6-terra",
                template=(ROOT / "automation/prompts/coverage_audit.md").read_text(
                    encoding="utf-8"
                ),
                publication_date="2026-08-01",
                search_window=SEARCH_WINDOW,
                missing_total=5,
                maximum_web_search_calls=7,
                existing_candidates=[],
                archive={"items": []},
            )

    def test_six_required_one_search_passes_are_actually_run(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_request(**kwargs):
            calls.append(kwargs)
            return successful_pass(direction_from_prompt(str(kwargs["prompt"])))

        result = self._run_plan(fake_request)

        self.assertEqual(len(calls), 6)
        self.assertTrue(all(item["maximum_web_search_calls"] == 1 for item in calls))
        self.assertEqual(result["audit_status"], "complete_with_gaps")
        self.assertEqual(result["checked_directions"], list(policy.AUDIT_DIRECTION_IDS))
        self.assertEqual(result["unchecked_directions"], [])
        self.assertEqual(result["search_budget"]["completed_calls"], 6)
        self.assertEqual(result["search_budget"]["maximum_calls"], 7)

    def test_seventh_call_only_retries_an_incomplete_required_direction(self) -> None:
        attempts: dict[str, int] = {}

        def fake_request(**kwargs):
            direction_id = direction_from_prompt(str(kwargs["prompt"]))
            attempts[direction_id] = attempts.get(direction_id, 0) + 1
            if direction_id == "security_russia" and attempts[direction_id] == 1:
                return successful_pass(
                    direction_id,
                    call_items=0,
                    completed_calls=0,
                    with_query=False,
                )
            return successful_pass(direction_id)

        result = self._run_plan(fake_request)

        self.assertEqual(sum(attempts.values()), 7)
        self.assertEqual(attempts["security_russia"], 2)
        self.assertEqual(result["audit_status"], "complete_with_gaps")
        self.assertEqual(result["search_budget"]["completed_calls"], 6)

    def test_missing_direction_cannot_be_reported_as_complete(self) -> None:
        def fake_request(**kwargs):
            direction_id = direction_from_prompt(str(kwargs["prompt"]))
            payload, metadata = successful_pass(direction_id)
            if direction_id == "general_coverage_gaps":
                # Consume both the initial and retry calls without proving the
                # requested direction, exhausting the seven-call budget.
                payload["direction_id"] = "security_world"
            return payload, metadata

        result = self._run_plan(fake_request)

        self.assertEqual(result["audit_status"], "budget_exhausted")
        self.assertEqual(result["unchecked_directions"], ["general_coverage_gaps"])
        self.assertTrue(result["search_budget"]["exhausted"])
        self.assertNotEqual(result["audit_status"], "complete")

    def test_transport_failure_with_budget_left_is_partial(self) -> None:
        def fake_request(**kwargs):
            direction_id = direction_from_prompt(str(kwargs["prompt"]))
            if direction_id == "security_world":
                return successful_pass(
                    direction_id,
                    call_items=0,
                    completed_calls=0,
                    with_query=False,
                )
            return successful_pass(direction_id)

        result = self._run_plan(fake_request)

        self.assertEqual(result["audit_status"], "partial")
        self.assertEqual(result["partial_directions"], ["security_world"])
        self.assertFalse(result["search_budget"]["exhausted"])

    def test_provider_side_per_pass_overrun_stops_further_requests(self) -> None:
        calls = 0

        def fake_request(**kwargs):
            nonlocal calls
            calls += 1
            direction_id = direction_from_prompt(str(kwargs["prompt"]))
            return successful_pass(direction_id, call_items=2)

        result = self._run_plan(fake_request)

        self.assertEqual(calls, 1)
        self.assertTrue(result["search_budget"]["provider_overrun"])
        self.assertEqual(result["unchecked_directions"][0], "security_russia")
        self.assertNotIn(result["audit_status"], {"complete", "complete_with_gaps"})


class HistoricalCandidateRegressionTests(unittest.TestCase):
    def test_word_copilot_worm_is_an_eligible_security_candidate(self) -> None:
        worm = candidate(
            "Word worm spreads through Microsoft 365 Copilot documents",
            "https://www.theregister.com/security/2026/07/29/word-worm-crawls-into-copilot-spreads-chaos/5280588",
        )
        self.assertEqual(coverage.validate_audit_candidate(worm, SEARCH_WINDOW), [])

    def test_major_suno_copyright_ruling_is_eligible(self) -> None:
        suno = candidate(
            "German court rules Suno broke copyright rules",
            "https://www.reuters.com/world/german-court-rules-ai-music-firm-suno-broke-copyright-rules-2026-07-31/",
            category="legal",
            source_type="news_agency",
            legal_scale="major",
            legal_scale_reason=(
                "Решение значимого суда против крупного генератора музыки "
                "может повлиять на обучение моделей и лицензирование."
            ),
        )
        self.assertEqual(coverage.validate_audit_candidate(suno, SEARCH_WINDOW), [])

    def test_major_perplexity_scraping_ruling_is_eligible(self) -> None:
        perplexity = candidate(
            "Perplexity loses bid to dismiss Reddit data-scraping suit",
            "https://www.reuters.com/legal/litigation/perplexity-ai-loses-bid-toss-reddit-lawsuit-over-data-scraping-2026-07-31/",
            category="legal",
            source_type="news_agency",
            legal_scale="major",
            legal_scale_reason=(
                "Федеральный процесс затрагивает доступ ИИ-поисковика к "
                "платформенным данным и способен повлиять на весь сегмент."
            ),
        )
        self.assertEqual(
            coverage.validate_audit_candidate(perplexity, SEARCH_WINDOW), []
        )

    def test_fake_launch_old_reprint_and_minor_household_lawsuit_are_rejected(self) -> None:
        fake_launch = candidate(
            "Unconfirmed launch of a nonexistent model",
            "https://example.com/fake-model",
            category="models",
            verification_status="unconfirmed",
        )
        old_reprint = candidate(
            "Old benchmark achievement reprinted without a new event",
            "https://example.com/old-reprint",
            category="research",
            published_date="2026-07-31",
            freshness_status="old_reprint",
        )
        household_case = candidate(
            "Private household dispute mentions a large AI company",
            "https://example.com/minor-lawsuit",
            category="legal",
            source_type="business_media",
            score=2,
            legal_scale="minor",
            legal_scale_reason="Единичная бытовая претензия без отраслевого эффекта.",
        )

        self.assertIn(
            "verification_status=verified",
            " ".join(coverage.validate_audit_candidate(fake_launch, SEARCH_WINDOW)),
        )
        self.assertIn(
            "старая перепечатка",
            " ".join(coverage.validate_audit_candidate(old_reprint, SEARCH_WINDOW)),
        )
        household_errors = " ".join(
            coverage.validate_audit_candidate(household_case, SEARCH_WINDOW)
        )
        self.assertIn("legal_scale=major", household_errors)
        self.assertIn("significance_score не ниже 4", household_errors)

    def test_unverified_curiosity_is_rejected_and_at_most_one_is_merged(self) -> None:
        unverified = candidate(
            "Viral but unverified AI oddity",
            "https://example.com/unverified-oddity",
            category="curiosity",
            verification_status="unconfirmed",
        )
        self.assertTrue(coverage.validate_audit_candidate(unverified, SEARCH_WINDOW))

        first = candidate(
            "Verified oddity one",
            "https://example.com/oddity-one",
            category="curiosity",
            score=3,
            curiosity_eligible=True,
            curiosity_verification="Подтверждено первоисточником и агентством.",
        )
        second = candidate(
            "Verified oddity two",
            "https://example.com/oddity-two",
            category="curiosity",
            score=3,
            curiosity_eligible=True,
            curiosity_verification="Подтверждено двумя независимыми источниками.",
        )
        base = {
            "candidates": [],
            "search_window": SEARCH_WINDOW,
            "research_notes": "base",
        }
        _merged, accepted, rejected = coverage.merge_candidates(
            base, [first, second]
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)
        self.assertIn("максимум один curiosity", " ".join(rejected[0]["errors"]))

    def test_date_only_candidate_is_kept_with_time_precision_warning(self) -> None:
        date_only = candidate(
            "Date-only source",
            "https://example.com/date-only",
        )
        self.assertTrue(coverage.candidate_in_window(date_only, SEARCH_WINDOW))
        payload, metadata = successful_pass("security_world")
        payload["candidates"] = [date_only]
        with mock.patch.object(
            policy, "run_audit_request", return_value=(payload, metadata)
        ):
            result = policy.execute_audit_plan(
                api_key="secret",
                model="gpt-5.6-terra",
                template=(ROOT / "automation/prompts/coverage_audit.md").read_text(
                    encoding="utf-8"
                ),
                publication_date="2026-08-01",
                search_window=SEARCH_WINDOW,
                missing_total=1,
                maximum_web_search_calls=7,
                existing_candidates=[],
                archive={"items": []},
            )
        self.assertTrue(result["time_precision_warnings"])
        self.assertIn("time_precision=date", result["time_precision_warnings"][0]["warning"])


class EditorialRerunGateTests(unittest.TestCase):
    def test_publishable_short_digest_without_new_candidates_skips_editorial(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            artifact.mkdir()
            (artifact / "stories.json").write_text(
                json.dumps([{"geography": "world", "category": "security"}]),
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
                        "editorial_notes": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (artifact / "candidates.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "publication_date": "2026-08-01",
                        "search_window": SEARCH_WINDOW,
                        "candidates": [
                            {
                                "id": "cand-001",
                                "geography": "world",
                                "recommendation": "include",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            archive = root / "archive.json"
            archive.write_text('{"items": []}', encoding="utf-8")
            report = root / "coverage-audit.json"
            plan = {
                "audit_status": "complete_with_gaps",
                "required_directions": list(policy.AUDIT_DIRECTION_IDS),
                "checked_directions": list(policy.AUDIT_DIRECTION_IDS),
                "partial_directions": [],
                "unchecked_directions": [],
                "directions": [],
                "attempts": [],
                "search_budget": {
                    "maximum_calls": 7,
                    "minimum_required_calls": 6,
                    "response_attempts": 6,
                    "observed_call_items": 6,
                    "completed_calls": 6,
                    "remaining_calls": 1,
                    "exhausted": False,
                    "provider_overrun": False,
                },
                "time_precision_warnings": [],
                "api": {"status": "completed"},
                "candidates": [],
            }
            argv = [
                "ensure_story_coverage_policy.py",
                "--artifact-dir",
                str(artifact),
                "--archive",
                str(archive),
                "--publication-date",
                "2026-08-01",
                "--model",
                "gpt-5.6-terra",
                "--maximum-audit-web-search-calls",
                "7",
                "--report",
                str(report),
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
                mock.patch.object(policy, "execute_audit_plan", return_value=plan),
                mock.patch.object(
                    policy,
                    "rerun_editorial",
                    side_effect=AssertionError("editorial must not rerun"),
                ) as rerun,
            ):
                self.assertEqual(policy.main(), 0)

            rerun.assert_not_called()
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(result["audit_added_candidates"], 0)
            self.assertFalse(result["editorial_rerun_required"])
            self.assertFalse(result["editorial_rerun_performed"])
            self.assertEqual(result["publication_mode"], "short")


if __name__ == "__main__":
    unittest.main()
