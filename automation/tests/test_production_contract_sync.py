from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CRONS = ["17 23 * * *"]


class ProductionContractSyncTests(unittest.TestCase):
    def test_config_workflow_and_editorial_thresholds_are_synchronized(self) -> None:
        production = json.loads(
            (ROOT / "automation/config/production-daily.json").read_text(
                encoding="utf-8"
            )
        )
        editorial = json.loads(
            (ROOT / "automation/config/editorial.json").read_text(encoding="utf-8")
        )
        workflow = (
            ROOT / ".github/workflows/daily-production.yml"
        ).read_text(encoding="utf-8")
        deploy_workflow = (
            ROOT / ".github/workflows/deploy-posts.yml"
        ).read_text(encoding="utf-8")
        promotion = (
            ROOT / "automation/scripts/promote_production_site.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(production["schedule_crons_utc"], EXPECTED_CRONS)
        self.assertEqual(production["schedule_cron_utc"], EXPECTED_CRONS[0])
        self.assertEqual(production["minimum_selected_stories"], 7)
        self.assertEqual(production["minimum_publishable_stories"], 1)
        self.assertFalse(production["regional_story_quotas_enabled"])
        self.assertTrue(
            production["coverage_audit_failure_blocks_publication"]
        )
        self.assertTrue(production["coverage_audit_enabled"])
        self.assertEqual(production["research_max_web_search_calls"], 12)
        self.assertEqual(production["coverage_audit_max_web_search_calls"], 7)
        self.assertEqual(
            production["coverage_audit_minimum_required_web_search_calls"], 6
        )
        self.assertEqual(
            production["coverage_audit_required_directions"],
            [
                "security_world",
                "security_russia",
                "security_asia",
                "legal_copyright_scraping",
                "curiosity",
                "general_coverage_gaps",
            ],
        )
        self.assertNotIn("legacy_prefix", production)
        self.assertNotIn("minimum_legacy_items", production)
        self.assertNotIn('config["legacy_prefix"]', promotion)
        self.assertNotIn("dzen-test", promotion)
        self.assertIn("existing_links - candidate_links", promotion)
        # Seven is the ordinary-volume boundary; one worthy story is enough
        # to publish and regional sections never have numeric quotas.
        self.assertEqual(editorial["story_counts"]["total_target_minimum"], 7)
        self.assertEqual(editorial["story_counts"]["short_digest_minimum"], 1)
        self.assertFalse(
            editorial["story_counts"]["regional_story_quotas_enabled"]
        )
        self.assertTrue(editorial["article"]["allow_missing_china_section"])
        self.assertTrue(editorial["article"]["allow_missing_russian_section"])
        self.assertEqual(workflow.count("cron:"), 1)
        for cron in EXPECTED_CRONS:
            self.assertEqual(workflow.count(f'cron: "{cron}"'), 1)
        self.assertIn(
            "Complete mandatory coverage audit for a short digest", workflow
        )
        self.assertIn(
            "Validate publishable story count and short digest marker",
            workflow,
        )
        self.assertIn("--usual-total 7", workflow)
        self.assertIn("--minimum-publishable 1", workflow)
        self.assertNotIn("--minimum-world", workflow)
        self.assertNotIn("--minimum-russia", workflow)
        self.assertNotIn("--minimum-russian-candidates", workflow)
        self.assertIn("--maximum-research-web-search-calls 12", workflow)
        self.assertIn("--maximum-audit-web-search-calls 7", workflow)
        self.assertIn(
            "Reuse completed editorial stop without paid APIs", workflow
        )
        self.assertIn('echo "stop=${stop}" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn(
            "steps.terminal_reuse.outputs.stop != 'true'", workflow
        )
        self.assertIn("needs.production.outputs.commit_sha != ''", workflow)
        self.assertIn("if: steps.recovery.outputs.reused != 'true'", workflow)
        self.assertIn("/actions/runs/${candidate_run_id}/jobs?per_page=100", workflow)
        self.assertIn('echo "reused=false" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn(r'stream.write("reused=true\n")', workflow)
        self.assertIn(r'+ "\n"', workflow)
        self.assertIn("candidate_pool_after", workflow)
        self.assertLess(
            workflow.index("- name: Complete mandatory coverage audit for a short digest"),
            workflow.index("- name: Generate one production cover"),
        )
        self.assertIn(
            "data.get(\"audit_status\") in {\"complete\", \"complete_with_gaps\"}",
            workflow,
        )
        self.assertIn("workflow_call:", deploy_workflow)
        self.assertIn("workflow_dispatch:", deploy_workflow)
        self.assertNotIn("\n  push:\n", deploy_workflow)

    def test_documentation_tracks_current_production_contract(self) -> None:
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        automation_readme = (ROOT / "automation/README.md").read_text(
            encoding="utf-8"
        )
        editorial_spec = (
            ROOT / "automation/specs/editorial-policy.md"
        ).read_text(encoding="utf-8")
        documentation = "\n".join((root_readme, automation_readme))
        normalized_documentation = " ".join(documentation.split())
        normalized_spec = " ".join(editorial_spec.split())

        for marker in (
            "`23:17 UTC`",
            "`02:17",
            "cron-job.org",
            "наиболее полный",
            "06:00 МСК",
            "12 Web Search",
            "до 7 Coverage",
            "24 search operations",
            "`security_world`",
            "`security_russia`",
            "`security_asia`",
            "`legal_copyright_scraping`",
            "`curiosity`",
            "`general_coverage_gaps`",
            "`search_cutoff_at` последнего успешно опубликованного выпуска",
            "`open_page` и `find_in_page`",
            "`partial`, `budget_exhausted` и `error` блокируют Image API",
            "авторитетный last-mile sweep",
            "Новостей сегодня меньше, чем обычно",
            "`publish=false` по умолчанию",
            "`recovery_run_id`",
            "`gpt-5.6-terra`",
            "`gpt-image-2`",
        ):
            self.assertIn(marker, normalized_documentation)

        self.assertIn(
            "`search_cutoff_at` предыдущего выпуска → фактический pre-research cutoff",
            normalized_spec,
        )
        self.assertNotIn(
            "от 07:00 предыдущего дня до 07:00 текущего дня",
            normalized_spec,
        )

    def test_same_contract_validator_used_by_ci_accepts_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Path(temp_dir) / "production-contract.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "automation/scripts/validate_production_daily_contract.py"
                    ),
                    "--config",
                    str(ROOT / "automation/config/production-daily.json"),
                    "--site-config",
                    str(ROOT / "automation/config/site.json"),
                    "--workflow",
                    str(ROOT / ".github/workflows/daily-production.yml"),
                    "--rss",
                    str(ROOT / "posts/rss.xml"),
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            diagnostics = (
                f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
            )
            self.assertEqual(completed.returncode, 0, diagnostics)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["schedule_utc"], EXPECTED_CRONS)
            self.assertEqual(
                payload["schedule_local"],
                [
                    "02:17 Europe/Moscow",
                ],
            )
            self.assertEqual(
                payload["story_coverage_contract"],
                {
                    "usual_total": 7,
                    "minimum_publishable": 1,
                    "regional_story_quotas_enabled": False,
                    "audit_failure_blocks_publication": True,
                    "research_max_web_search_calls": 12,
                    "audit_max_web_search_calls": 7,
                    "audit_minimum_required_web_search_calls": 6,
                    "audit_required_directions": [
                        "security_world",
                        "security_russia",
                        "security_asia",
                        "legal_copyright_scraping",
                        "curiosity",
                        "general_coverage_gaps",
                    ],
                    "maximum_curiosity_stories": 1,
                },
            )


if __name__ == "__main__":
    unittest.main()
