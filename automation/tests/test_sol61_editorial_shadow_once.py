"""Offline mock checks: no OpenAI API calls."""
from __future__ import annotations
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TEST_DAY = "2026-10-30"
sys.path.insert(0, str(ROOT / "automation" / "scripts"))
import sol61_editorial_shadow_once as sol


class FakeResponses:
    def __init__(self, value):
        self.calls = []
        self.value = value

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="resp_fake_29", model=sol.SOL, status="completed",
            output_text=json.dumps(self.value, ensure_ascii=False),
            usage={"input_tokens": 24000, "output_tokens": 3000},
            service_tier="incentivized-tier",
        )


class Sol61EditorialShadowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.artifact = self.base / "baseline"
        self.day = self.artifact / TEST_DAY
        self.day.mkdir(parents=True)
        self.archive = self.base / "archive.json"
        self.policy = self.base / "policy.json"
        self.output = self.base / "shadow"
        self.items = [
            {
                "id": f"cand-{i:03d}", "title": f"Independent news {i}",
                "organization": f"Organization {i}",
                "event_summary": "Важная подтверждённая новость",
                "category": "models", "event_type": "launch",
                "verification_status": "verified", "freshness_status": "new_event",
                "recommendation": "include", "significance_score": 4,
                "primary_source": {"title": f"Source {i}", "publisher": "Source Co",
                                   "url": f"https://example.org/{i}"},
            }
            for i in range(1, 7)
        ]
        sol.save(self.day / "candidates.json", {
            "publication_date": TEST_DAY, "status": "ok", "candidates": self.items,
        })
        sol.save(self.day / "editorial-output-raw.json", {
            "status": "ok", "selected_candidate_ids": ["cand-001", "cand-003"],
            "selection_summary": "SECRET_TERRA_DECISION_NEVER_SEND",
        })
        sol.save(self.day / "run-info.json", {
            "status": "ok", "publication_date": TEST_DAY, "model_requested": sol.TERRA,
        })
        sol.save(self.archive, {
            "items": [{"date": "2026-10-28",
                       "stories": [{"headline": "Old", "organization": "Other"}]}],
        })
        sol.save(self.policy, {
            "story_counts": {"total_target_minimum": 7, "total_target_maximum": 12},
            "diversity": {"max_selected_per_publisher_soft": 2,
                          "max_selected_per_organization_soft": 2},
            "candidate_selection": {"verification_required_for_selection": "verified"},
        })
        self.fake = FakeResponses({
            "selected_candidate_ids": ["cand-001", "cand-004"],
            "selection_summary": "Two relevant verified stories",
            "decisions": [
                {"candidate_id": f"cand-{i:03d}",
                 "choice": "select" if i in (1, 4) else "exclude",
                 "reason": "Relevant" if i in (1, 4) else "Lower significance"}
                for i in range(1, 7)
            ],
        })
        self.client = SimpleNamespace(responses=self.fake)

    def perform(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "1",
                                     "AI_DIGEST_PUBLICATION_DATE": TEST_DAY}), patch.object(sol, "current_moscow_day", return_value=TEST_DAY):
            return sol.run(publication_date=TEST_DAY, artifact=self.artifact, archive_path=self.archive,
                           policy_path=self.policy, output=self.output, client=self.client)

    def test_one_mock_request_independent_of_terra_and_original_files_unchanged(self):
        before = (self.day / "editorial-output-raw.json").read_bytes()
        report = self.perform()
        self.assertEqual(len(self.fake.calls), 1)
        call = self.fake.calls[0]
        self.assertEqual(call["model"], sol.SOL)
        self.assertEqual(call["max_output_tokens"], 4000)
        self.assertEqual(call["reasoning"], {"effort": "medium"})
        self.assertNotIn("tools", call)
        self.assertEqual(call["store"], False)
        self.assertNotIn("SECRET_TERRA_DECISION_NEVER_SEND",
                         json.dumps(call["input"], ensure_ascii=False))
        self.assertEqual(report["terra_only"], ["cand-003"])
        self.assertEqual(report["sol_only"], ["cand-004"])
        self.assertEqual(report["selected_by_both"], ["cand-001"])
        self.assertEqual((self.day / "editorial-output-raw.json").read_bytes(), before)
        meta = sol.load(self.output / "frozen-input.json")
        self.assertFalse(meta["sol_saw_terra_selection"])
        self.assertFalse(meta["web_search_enabled"])
        self.assertLessEqual(meta["prompt_bytes"], sol.MAX_PROMPT_BYTES)
        self.assertEqual(sol.load(self.output / "manifest.json")["status"], "complete")
        self.assertEqual(sol.load(self.output / "sol-provider-metadata.json")["service_tier"],
                         "incentivized-tier")

    def test_no_second_paid_attempt_on_same_output(self):
        self.perform()
        with self.assertRaisesRegex(ValueError, "already contains"):
            self.perform()
        self.assertEqual(len(self.fake.calls), 1)

    def test_no_paid_call_on_wrong_date_or_wrong_baseline(self):
        source = sol.load(self.day / "candidates.json")
        source["publication_date"] = "2026-10-31"
        sol.save(self.day / "candidates.json", source)
        with self.assertRaisesRegex(ValueError, "current publication date"):
            self.perform()
        self.assertFalse(self.fake.calls)
        source["publication_date"] = TEST_DAY
        sol.save(self.day / "candidates.json", source)
        baseline = sol.load(self.day / "run-info.json")
        baseline["model_requested"] = sol.SOL
        sol.save(self.day / "run-info.json", baseline)
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.perform()
        self.assertFalse(self.fake.calls)

    def test_rerun_never_spends(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}), patch.object(sol, "current_moscow_day", return_value=TEST_DAY):
            with self.assertRaisesRegex(ValueError, "rerun"):
                sol.run(publication_date=TEST_DAY, artifact=self.artifact, archive_path=self.archive,
                        policy_path=self.policy, output=self.output, client=self.client)
        self.assertEqual(len(self.fake.calls), 0)

    def test_missing_or_duplicate_model_decision_fails_closed(self):
        raw = dict(self.fake.value)
        raw["decisions"] = raw["decisions"][:-1]
        with self.assertRaisesRegex(ValueError, "every candidate"):
            sol.check_result(raw, [c["id"] for c in self.items])
        raw = dict(self.fake.value)
        raw["selected_candidate_ids"] = ["cand-001", "cand-001"]
        with self.assertRaisesRegex(ValueError, "duplicates"):
            sol.check_result(raw, [c["id"] for c in self.items])

    def test_full_candidate_set_and_prompt_bytes(self):
        ids = [c["id"] for c in self.items]
        prompt, got = sol.build_request(sol.load(self.day / "candidates.json"),
                                        sol.load(self.archive), sol.load(self.policy), TEST_DAY)
        self.assertEqual(ids, got)
        self.assertNotIn("selected_candidate_ids", prompt)
        self.assertLessEqual(len((sol.SYSTEM + prompt).encode("utf-8")), sol.MAX_PROMPT_BYTES)

    def test_workflow_daily_after_terra_publish_and_opt_out(self):
        wf = (ROOT / ".github" / "workflows" / "daily-production.yml").read_text(encoding="utf-8")
        block = wf.split("  sol61_editorial_shadow:\n", 1)[1].split("  final_status:\n", 1)[0]
        for marker in (
            "vars.SOL_EDITORIAL_AUDIT_ENABLED != 'false'",
            "needs.deploy.result == 'success'",
            "needs.production.outputs.publish == 'true'",
            "github.run_attempt == 1",
            "needs.gate.outputs.main_sha",
            "run-id: ${{ github.run_id }}",
            "name: daily-production-${{ needs.gate.outputs.publication_date }}",
            "name: sol61-independent-editorial-${{ needs.gate.outputs.publication_date }}",
            "AI_DIGEST_PUBLICATION_DATE: ${{ needs.gate.outputs.publication_date }}",
            "--publication-date \"${AI_DIGEST_PUBLICATION_DATE}\"",
            "continue-on-error: true",
        ):
            self.assertIn(marker, block)
        for forbidden in ("contents: write", "push_protected_main.sh",
                          "generate_production_cover.py", "Commit production release",
                          "force_fresh_research", "2026-10-29"):
            self.assertNotIn(forbidden, block)
        self.assertEqual(wf.count('cron: "17 23 * * *"'), 1)

    def test_old_day_and_historical_date_rejected_without_request(self):
        with patch.object(sol, "current_moscow_day", return_value="2026-10-30"):
            with self.assertRaisesRegex(ValueError, "earlier one-shot"):
                sol.validate_publication_date("2026-10-29")
        with patch.object(sol, "current_moscow_day", return_value="2026-10-31"):
            with self.assertRaisesRegex(ValueError, "Only current Moscow"):
                sol.validate_publication_date("2026-10-30")
        self.assertEqual(self.fake.calls, [])

    def test_next_day_saves_separate_original_evidence(self):
        nextday = "2026-10-31"
        day = self.artifact / nextday
        day.mkdir()
        for name in ("candidates.json", "editorial-output-raw.json", "run-info.json"):
            item = sol.load(self.day / name)
            if name != "editorial-output-raw.json":
                item["publication_date"] = nextday
            sol.save(day / name, item)
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "1",
                                     "AI_DIGEST_PUBLICATION_DATE": nextday}), patch.object(sol, "current_moscow_day", return_value=nextday):
            result = sol.run(publication_date=nextday, artifact=self.artifact,
                             archive_path=self.archive, policy_path=self.policy,
                             output=self.output, client=self.client)
        self.assertEqual(result["publication_date"], nextday)
        self.assertEqual(sol.load(self.output / "manifest.json")["publication_date"], nextday)
        self.assertEqual(len(self.fake.calls), 1)


if __name__ == "__main__":
    unittest.main()
