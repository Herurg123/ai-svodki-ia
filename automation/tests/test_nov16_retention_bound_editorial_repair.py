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
import run_editorial_repair as repair_runner
import run_digest_preview

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

    def test_editorial_child_generator_reads_the_pinned_archive(self):
        self.prune()
        pinned = self.select()
        required = [
            "run_editorial_repair.py",
            "--publication-date", DATE,
            "--model", MODEL,
            "--repair-persisted-research",
            str(self.research.relative_to(self.root)),
            "--repair-state-dir",
            str(self.state.relative_to(self.root)),
            "--repair-archive",
            str(pinned.relative_to(self.root)),
            "--repair-artifact-dir",
            str(self.artifact.relative_to(self.root)),
            "--research-input",
            str(self.runtime.relative_to(self.root)),
        ]
        calls = []

        def no_network_editorial():
            # Real generator entrypoint's archive is patched to this exact
            # signed context by the public child, before any model request.
            calls.append(generator.ARCHIVE_PATH.resolve())
            self.assertEqual(
                json.loads(generator.ARCHIVE_PATH.read_text()),
                self.original_archive,
            )
            return 0

        with patch.object(repair_runner, "REPOSITORY_ROOT", self.root), \
             patch.object(repair_runner, "load_required", return_value=self.context), \
             patch.object(repair_runner, "mark_validated"), \
             patch.object(run_digest_preview, "main", side_effect=no_network_editorial), \
             patch.object(generator, "ARCHIVE_PATH", self.archive_path), \
             patch.object(generator, "call_with_usage"), \
             patch.object(sys, "argv", required):
            self.assertEqual(repair_runner.main(), 0)
        self.assertEqual(calls, [pinned.resolve()])

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
        self.assertEqual(
            [c["title"] for c in cleaned["candidates"]],
            ["Independent new AI event"],
        )
        # Candidate IDs are intentionally renumbered by the existing
        # sanitizer after removing an invalid row; identity is the story/source.
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
        self.assertIn(
            "Huawei Cloud openPangu 2.1 Pro",
            [c["title"] for c in accepted["candidates"]],
        )
        self.assertFalse(any(r["id"] == "cand-006" for r in removed_update))


class November16RealRSSRetentionRebuildTests(unittest.TestCase):
    """Original 2026-10-14 archive row, frozen from run 43790005874.

    Nightly cleanup removes the old release from the RSS feed and removes its
    run-info, but retains its meta.json and stories.json. The rebuilt archive
    has 121 entries still, yet its old Oct14 summary and cutoff change. The
    prior 2026-11-16 PR #252 tested deletion only and incorrectly blocked it.
    """

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        fixtures = Path(__file__).resolve().parent / "fixtures"
        self.old_row = json.loads(
            (fixtures / "nov16_oct14_rss_original_row.json").read_text(
                encoding="utf-8"
            )
        )
        self.meta = json.loads(
            (fixtures / "nov16_oct14_retained_meta.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(self.old_row["date"], "2026-10-14")
        self.assertEqual(len(self.old_row["stories"]), 7)

        self.state = self.root / "automation/preview/production-daily"
        self.artifact = self.root / "automation/preview" / DATE
        self.artifact.mkdir(parents=True)
        self.archive_path = self.root / "automation/archive/index.json"
        self.research = self.state / "saved-research.json"
        self.rss = self.root / "posts/rss.xml"
        self.rss.parent.mkdir(parents=True)
        self.rss.write_text(
            "<rss><channel><item>"
            "<link>https://rybalka.one/posts/2026-11-15/</link>"
            "</item></channel></rss>",
            encoding="utf-8",
        )
        self.old_archive = {
            "version": 2,
            "source": "automation/content + posts/rss.xml",
            "items": [
                {
                    "date": "2026-11-15",
                    "published_at": "2026-11-15T06:00:00+03:00",
                    "title": "Recent already-published digest",
                    "link": "https://rybalka.one/posts/2026-11-15/",
                    "summary": "Recent intact summary",
                    "stories": [],
                },
                self.old_row,
            ],
        }
        self.changed_archive = copy.deepcopy(self.old_archive)
        row = self.changed_archive["items"][-1]
        row["summary"] = str(self.meta["description"])[:500]
        row["search_cutoff_at"] = self.meta["published_at"]
        self.assertNotEqual(row, self.old_row)
        self.assertEqual(
            {k: v for k, v in row.items()
             if k not in {"summary", "search_cutoff_at"}},
            {k: v for k, v in self.old_row.items()
             if k not in {"summary", "search_cutoff_at"}},
        )
        content = self.root / "automation/content/2026-10-14"
        write(content / "meta.json", self.meta)
        write(content / "stories.json", self.old_row["stories"])
        self.content = content

        write(self.archive_path, self.old_archive)
        write(self.research, {
            "publication_date": DATE,
            "candidates": [],
            "search_window": {
                "start_at": "2026-11-14T05:06:19+03:00",
                "end_at": "2026-11-16T05:06:21+03:00",
            },
        })
        (self.artifact / "editorial-prompt-input.txt").write_text(
            "editorial\n=== ARCHIVE_CONTEXT_BEGIN ===\n"
            + json.dumps(self.old_archive, ensure_ascii=False)
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
        self.saved_hash = json.loads(
            self.context.journal_path.read_text(encoding="utf-8")
        )["archive_sha256"]
        write(self.archive_path, self.changed_archive)

    def select(self):
        return guard.select_bound_archive_for_replay(
            publication_date=DATE,
            state_dir=self.state,
            artifact_dir=self.artifact,
            archive_path=self.archive_path,
        )

    def test_actual_oct14_rss_to_meta_rebuild_uses_signed_original(self):
        """The previously untested production failure, no paid transport."""
        pinned = self.select()
        self.assertNotEqual(pinned, self.archive_path)
        self.assertEqual(
            json.loads(pinned.read_text(encoding="utf-8")), self.old_archive
        )
        self.assertEqual(
            guard._archive_sha256(json.loads(pinned.read_text()), version=2),
            self.saved_hash,
        )
        required = guard.prepare_required(
            publication_date=DATE,
            state_dir=self.state,
            persisted_research_path=self.research,
            archive_path=pinned,
            artifact_dir=self.artifact,
            model=MODEL,
        )
        self.assertEqual(required.intent_sha256, self.context.intent_sha256)
        self.assertEqual(guard.journal_state(self.state, DATE), "failed_before_request")
        self.assertIsNone(
            json.loads(self.context.journal_path.read_text())["request_sha256"]
        )

    def test_retained_fallback_not_accepted_when_rss_still_has_oct14(self):
        self.rss.write_text(
            '<rss><channel><item><link>'
            'https://rybalka.one/posts/2026-10-14/'
            '</link></item></channel></rss>',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(guard.EditorialRepairError, "retention-only"):
            self.select()

    def test_retained_fallback_requires_missing_run_info_and_valid_files(self):
        run_info = self.content / "run-info.json"
        write(run_info, {"status": "ok"})
        with self.assertRaisesRegex(guard.EditorialRepairError, "retention-only"):
            self.select()
        run_info.unlink()
        for filename in ("meta.json", "stories.json"):
            path = self.content / filename
            original = path.read_bytes()
            try:
                path.unlink()
                with self.assertRaisesRegex(guard.EditorialRepairError, "retention-only"):
                    self.select()
            finally:
                path.write_bytes(original)

    def test_non_fallback_old_record_changes_are_still_blocked(self):
        attacks = {}
        for key in ("title", "link", "published_at"):
            value = copy.deepcopy(self.changed_archive)
            value["items"][-1][key] = "tampered"
            attacks[key] = value
        for key in ("stories", "source_urls", "topics"):
            value = copy.deepcopy(self.changed_archive)
            value["items"][-1][key] = []
            attacks[key] = value
        for key, text in (
            ("summary", "fabricated old news"), 
            ("search_cutoff_at", "2026-10-14T03:00:00+03:00"),
        ):
            value = copy.deepcopy(self.changed_archive)
            value["items"][-1][key] = text
            attacks[key] = value
        for case, archive in attacks.items():
            with self.subTest(case=case):
                write(self.archive_path, archive)
                with self.assertRaisesRegex(
                    guard.EditorialRepairError, "retention-only"
                ):
                    self.select()

    def test_unverified_meta_proof_and_new_stories_still_block(self):
        original_meta = (self.content / "meta.json").read_bytes()
        try:
            altered = copy.deepcopy(self.meta)
            altered["description"] = "FAKE"
            write(self.content / "meta.json", altered)
            with self.assertRaisesRegex(guard.EditorialRepairError, "retention-only"):
                self.select()
        finally:
            (self.content / "meta.json").write_bytes(original_meta)

        newly_added = copy.deepcopy(self.changed_archive)
        newly_added["items"].insert(
            0, {"date": DATE, "title": "untrusted new entry"}
        )
        write(self.archive_path, newly_added)
        with self.assertRaisesRegex(guard.EditorialRepairError, "retention-only"):
            self.select()

    def test_recent_rows_never_qualify_for_fallback(self):
        tampered = copy.deepcopy(self.changed_archive)
        tampered["items"][0]["summary"] = "Other recent summary"
        write(self.archive_path, tampered)
        with self.assertRaisesRegex(guard.EditorialRepairError, "retention-only"):
            self.select()


if __name__ == "__main__":
    unittest.main()
