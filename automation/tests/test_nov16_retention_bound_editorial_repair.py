"""November 16 durable Editorial Repair regression, entirely offline.

Strictly separate an archive pruning of old dated entries from any modified
archive story, signed journal, provider outcome or editor candidate. Exercise
the production replay seam without a live model or any API budget.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import editorial_repair_guard as guard
import ensure_story_coverage_p0 as coverage
import generate_digest_preview as generator

DATE = "2026-11-16"
MODEL = "gpt-5.6-terra"
STARTRISE = "https://www.startrise.io/models"


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


class November16BoundArchiveReplayTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.artifact = self.root / "automation/preview" / DATE
        self.artifact.mkdir(parents=True)
        self.state = self.root / "automation/preview/production-daily"
        self.state.mkdir(parents=True)
        self.archive_path = self.root / "automation/archive/index.json"
        self.research = (
            self.state / f"coverage-audit-merged-candidates-{DATE}.json"
        )
        self.runtime = (
            self.root / "automation/fixtures/research" / f".coverage-audit-{DATE}.json"
        )
        self.original_archive = {
            "version": 2,
            "source": "automation/content + posts/rss.xml",
            "items": [
                {
                    "date": "2026-11-15",
                    "source_urls": ["https://example.org/nov15"],
                    "title": "Nov 15 AI digest",
                },
                {
                    "date": "2026-10-13",
                    "source_urls": [STARTRISE],
                    "title": "Unrelated older release",
                },
            ],
        }
        self.initial_research = {
            "publication_date": DATE,
            "candidates": [{"id": "cand-001"}],
            "search_window": {
                "start_at": "2026-11-14T05:06:19+03:00",
                "end_at": "2026-11-16T05:06:21+03:00",
            },
        }
        write(self.archive_path, self.original_archive)
        write(self.research, self.initial_research)
        write(self.runtime, self.initial_research)
        (self.artifact / "editorial-prompt-input.txt").write_text(
            "editorial\n=== ARCHIVE_CONTEXT_BEGIN ===\n"
            + json.dumps(self.original_archive, ensure_ascii=False)
            + "\n=== ARCHIVE_CONTEXT_END ===\nbody",
            encoding="utf-8",
        )
        self.context = guard.prepare_required(
            publication_date=DATE,
            state_dir=self.state,
            persisted_research_path=self.research,
            archive_path=self.archive_path,
            artifact_dir=self.artifact,
            model=MODEL,
        )
        guard.mark_failed_before_request(
            self.context, "generator_nonzero_before_request"
        )

    def prune(self):
        archive = copy.deepcopy(self.original_archive)
        archive["items"] = [x for x in archive["items"] if x["date"] != "2026-10-13"]
        archive["generated_at"] = "2026-11-16T02:23:43+00:00"
        write(self.archive_path, archive)

    def select(self) -> Path:
        return guard.select_bound_archive_for_replay(
            publication_date=DATE,
            state_dir=self.state,
            artifact_dir=self.artifact,
            archive_path=self.archive_path,
        )

    def test_uses_same_original_archive_when_unchanged(self):
        self.assertEqual(self.select(), self.archive_path.resolve())

    def test_old_retention_prune_reuses_exact_sealed_context_and_intent(self):
        self.prune()
        pinned = self.select()
        self.assertEqual(
            pinned, self.state / f"editorial-repair-{DATE}.archive.json"
        )
        self.assertEqual(json.loads(pinned.read_text()), self.original_archive)
        journal = json.loads(self.context.journal_path.read_text())
        self.assertEqual(
            guard._archive_sha256(json.loads(pinned.read_text()), version=2),
            journal["archive_sha256"],
        )
        # This is the public guard, not an assertion on an isolated helper.
        recovered = guard.prepare_required(
            publication_date=DATE,
            state_dir=self.state,
            persisted_research_path=self.research,
            archive_path=pinned,
            artifact_dir=self.artifact,
            model=MODEL,
        )
        self.assertEqual(recovered.intent_sha256, self.context.intent_sha256)
        self.assertEqual(
            guard.journal_state(self.state, DATE), "failed_before_request"
        )
        self.assertIsNone(
            json.loads(self.context.journal_path.read_text())["request_sha256"]
        )

    def test_rebuild_snapshot_from_untouched_saved_original_prompt(self):
        self.prune()
        self.context.state_dir.joinpath(
            f"editorial-repair-{DATE}.archive.json"
        ).unlink()
        self.assertEqual(
            json.loads(self.select().read_text()), self.original_archive
        )

    def test_forged_or_missing_archive_proof_cannot_waive_sha_mismatch(self):
        self.prune()
        snapshot = self.state / f"editorial-repair-{DATE}.archive.json"
        snapshot.unlink()
        (self.artifact / "editorial-prompt-input.txt").unlink()
        with self.assertRaisesRegex(
            guard.EditorialRepairError, "does not match sealed archive_sha256"
        ):
            self.select()

    def test_mutated_saved_snapshot_is_not_accepted_even_if_prompt_is_valid(self):
        self.prune()
        snapshot = self.state / f"editorial-repair-{DATE}.archive.json"
        tampered = copy.deepcopy(self.original_archive)
        tampered["items"][0]["title"] = "CHANGED RECENT STORY"
        write(snapshot, tampered)
        with self.assertRaisesRegex(
            guard.EditorialRepairError, "does not match sealed archive_sha256"
        ):
            self.select()

    def test_any_recent_prune_new_story_changed_story_or_reorder_is_blocked(self):
        self.prune()
        base = json.loads(self.archive_path.read_text())
        scenarios = {}
        scenarios["recent_removed"] = {
            **base,
            "items": [],
        }
        scenarios["new_story"] = copy.deepcopy(base)
        scenarios["new_story"]["items"].insert(0, {
            "date": DATE, "title": "New story", "source_urls": []
        })
        scenarios["mutated_story"] = copy.deepcopy(base)
        scenarios["mutated_story"]["items"][0]["title"] = "TAMPERED"
        scenarios["changed_source"] = copy.deepcopy(base)
        scenarios["changed_source"]["source"] = "different archive origin"
        for scenario, changed in scenarios.items():
            with self.subTest(scenario=scenario):
                write(self.archive_path, changed)
                with self.assertRaisesRegex(
                    guard.EditorialRepairError, "retention-only cleanup"
                ):
                    self.select()

    def test_unknown_provider_outcome_remains_fail_closed(self):
        self.prune()
        # A signed unknown state never gains paid retry permission.
        journal = json.loads(self.context.journal_path.read_text())
        journal["state"] = "unknown_after_request"
        write(
            self.context.journal_path,
            guard._seal(journal, "journal_sha256"),
        )
        with self.assertRaisesRegex(
            guard.EditorialRepairError, "unknown provider outcome"
        ):
            self.select()

    def test_coverage_wrapper_passes_one_pinned_path_to_parent_and_child(self):
        self.prune()
        old = coverage._ATTEMPTED_THIS_PROCESS
        try:
            with patch.object(coverage, "_is_coverage_research", return_value=True), \
                 patch.object(coverage, "REPOSITORY_ROOT", self.root), \
                 patch.object(coverage, "STATE_DIR", self.state), \
                 patch.object(coverage, "ARCHIVE_PATH", self.archive_path), \
                 patch.object(coverage, "_persisted_research", return_value=self.research), \
                 patch.object(coverage, "_artifact_dir", return_value=self.artifact), \
                 patch.object(coverage, "_model", return_value=MODEL), \
                 patch.object(coverage.subprocess, "run",
                              return_value=subprocess.CompletedProcess([], 0, "")) as runner:
                coverage.rerun_editorial(
                    publication_date=DATE,
                    merged_research_path=self.runtime,
                    minimum_total=7,
                    maximum_candidates=20,
                    maximum_selected_stories=12,
                )
                command = runner.call_args.args[0]
                passed = command[command.index("--repair-archive") + 1]
                pinned = self.select()
                self.assertEqual(passed, str(pinned.relative_to(self.root)))
                self.assertEqual(json.loads(pinned.read_text()), self.original_archive)
        finally:
            coverage._ATTEMPTED_THIS_PROCESS = old

    def test_source_repair_filters_archive_homepage_without_fake_update(self):
        archive = copy.deepcopy(self.original_archive)
        archive["items"][0]["source_urls"].append(STARTRISE)
        original = {
            "status": "ok", "publication_date": DATE,
            "candidates": [
                {
                    "id": "cand-006", "title": "Huawei Cloud openPangu 2.1 Pro",
                    "published_date": "2026-11-15",
                    "time_precision": "date", "published_at": None,
                    "primary_source": {
                        "title": "Generic model catalog", "publisher": "Startrise",
                        "url": STARTRISE,
                    },
                    "supporting_sources": [{
                        "title": "Official Huawei MaaS documentation",
                        "publisher": "Huawei Cloud",
                        "url": "https://support.huaweicloud.com/bestpractice-maas/bestpractice_maas_0021_03.html",
                    }],
                    "recommendation": "consider", "archive_status": "none",
                },
                {
                    "id": "cand-007", "title": "Independent new AI event",
                    "published_date": "2026-11-15",
                    "time_precision": "date", "published_at": None,
                    "primary_source": {
                        "title": "New primary", "publisher": "AP",
                        "url": "https://apnews.com/article/new-event",
                    },
                    "supporting_sources": [],
                    "recommendation": "consider", "archive_status": "none",
                },
            ],
        }
        untouched = copy.deepcopy(original)
        cleaned, removed, warnings = generator.sanitize_research_candidates(
            original, date.fromisoformat(DATE), archive,
            {"timezone": "Europe/Moscow", "publication_hour": 6},
            cutoff_at=datetime.fromisoformat("2026-11-16T05:06:21+03:00"),
        )
        self.assertEqual([c["id"] for c in cleaned["candidates"]], ["cand-007"])
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["id"], "cand-006")
        self.assertEqual(removed[0]["reason_code"], "archived_primary_without_update")
        self.assertIn("архивный primary URL", " ".join(warnings))
        self.assertEqual(original, untouched, "original paid research must not mutate")

        update = copy.deepcopy(original)
        update["candidates"][0]["archive_status"] = "update"
        update["candidates"][0]["archive_reason"] = "Documented independent update"
        accepted, removed_update, _ = generator.sanitize_research_candidates(
            update, date.fromisoformat(DATE), archive,
            {"timezone": "Europe/Moscow", "publication_hour": 6},
            cutoff_at=datetime.fromisoformat("2026-11-16T05:06:21+03:00"),
        )
        self.assertIn("cand-006", [c["id"] for c in accepted["candidates"]])
        self.assertFalse(any(r["id"] == "cand-006" for r in removed_update))


if __name__ == "__main__":
    unittest.main()
