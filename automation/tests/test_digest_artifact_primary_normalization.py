from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "automation" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import normalize_digest_artifact as normalizer


SAFE_PROMPT = (
    "Изображение 16:9: тест.\n"
    "Главные визуальные темы: тест.\n"
    "Композиция: тест.\n"
    "Стиль: без логотипов; без дополнительного текста; без водяных знаков; без узнаваемых лиц."
)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class FreshPrimaryArtifactNormalizationTests(unittest.TestCase):
    def make_artifact(
        self,
        root: Path,
        *,
        agency_sources: list[str],
        other_sources: list[str] | None = None,
        with_search_window: bool = False,
    ) -> Path:
        artifact = root / "artifact"
        artifact.mkdir()
        write_json(artifact / "digest.json", {"image_prompt": SAFE_PROMPT})
        (artifact / "image-prompt.txt").write_text(SAFE_PROMPT, encoding="utf-8")
        write_json(
            artifact / "run-info.json",
            {
                "status": "ok",
                "pipeline": "editorial_from_saved_research",
                "research": {
                    "status": "ok",
                    "mode": "primary_recall_v2",
                    "settings": {"source": "saved_fixture"},
                    "response": {"web_search_calls": 12},
                },
            },
        )
        directions = [
            {
                "direction_id": "major_agencies",
                "web_search_calls_completed": 1,
                "raw_candidates": [],
                "api": {"consulted_sources": [{"url": url} for url in agency_sources]},
            },
            {
                "direction_id": "global_breaking",
                "web_search_calls_completed": 1,
                "raw_candidates": [],
                "api": {"consulted_sources": [{"url": url} for url in (other_sources or [])]},
            },
        ]
        primary: dict[str, object] = {"directions": directions}
        if with_search_window:
            primary["search_window"] = {
                "start_at": "2026-08-11T09:41:12+03:00",
                "end_at": "2026-08-13T02:58:08+03:00",
            }
        write_json(artifact / "primary-recall.json", primary)
        return artifact

    def test_fresh_primary_metadata_is_not_left_as_saved_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=["https://www.reuters.com/technology/example"],
                other_sources=["https://openai.com/index/example"],
            )
            report = normalizer.normalize_artifact(artifact, artifact / "artifact-normalization.json")
            run_info = json.loads((artifact / "run-info.json").read_text(encoding="utf-8"))
            self.assertEqual(run_info["pipeline"], "primary_recall_v2_then_editorial")
            self.assertEqual(
                run_info["research"]["settings"]["source"],
                "trusted_runtime_primary_recall",
            )
            self.assertIn("run-info.json", report["changed_files"])

    def test_empty_major_agencies_sources_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=[],
                other_sources=["https://openai.com/index/example", "https://nvidia.com/example"],
            )
            with self.assertRaises(normalizer.NormalizationError) as ctx:
                normalizer.normalize_artifact(artifact, artifact / "artifact-normalization.json")
            self.assertIn("major_agencies", str(ctx.exception))

    def test_low_signal_only_primary_sources_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=["https://arxiv.org/abs/2608.00001"],
                other_sources=[
                    "https://en.wikipedia.org/wiki/Artificial_intelligence",
                    "https://www.reddit.com/r/artificial/example",
                ],
            )
            with self.assertRaises(normalizer.NormalizationError) as ctx:
                normalizer.normalize_artifact(artifact, artifact / "artifact-normalization.json")
            self.assertIn("меньше двух", str(ctx.exception))

    def test_stale_agency_pages_do_not_count_as_fresh_source_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=[
                    "https://www.bloomberg.com/authors/EXAMPLE/example-author",
                    "https://www.bloomberg.com/news/newsletters/2026-04-09/old-ai-newsletter",
                ],
                other_sources=["https://openai.com/index/example", "https://nvidia.com/example"],
                with_search_window=True,
            )
            with self.assertRaises(normalizer.NormalizationError) as ctx:
                normalizer.normalize_artifact(artifact, artifact / "artifact-normalization.json")
            self.assertIn("Reuters/AP/Bloomberg/FT", str(ctx.exception))

    def test_fresh_agency_candidate_in_thematic_direction_is_source_health_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=[
                    "https://www.bloomberg.com/authors/EXAMPLE/example-author",
                ],
                other_sources=["https://openai.com/index/example"],
                with_search_window=True,
            )
            primary_path = artifact / "primary-recall.json"
            primary = json.loads(primary_path.read_text(encoding="utf-8"))
            primary["directions"].append(
                {
                    "direction_id": "security_safety",
                    "web_search_calls_completed": 1,
                    "raw_candidates": [
                        {
                            "published_date": "2026-08-12",
                            "primary_source": {
                                "url": "https://www.ft.com/content/fresh-security-story"
                            },
                        }
                    ],
                    "api": {"consulted_sources": []},
                }
            )
            write_json(primary_path, primary)
            normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )

    def test_final_coverage_pool_can_supply_fresh_agency_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=[
                    "https://www.bloomberg.com/authors/EXAMPLE/example-author",
                    "https://www.bloomberg.com/news/newsletters/2026-04-09/old-ai-newsletter",
                ],
                other_sources=["https://openai.com/index/example", "https://nvidia.com/example"],
                with_search_window=True,
            )
            write_json(
                artifact / "candidates.json",
                {
                    "candidates": [
                        {
                            "published_date": "2026-08-12",
                            "primary_source": {
                                "url": "https://www.reuters.com/technology/fresh-coverage-rescue-2026-08-12/"
                            },
                        }
                    ]
                },
            )
            normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )

    def test_current_dated_reuters_article_is_fresh_source_health_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=[
                    "https://www.reuters.com/technology/example-ai-story-2026-08-12/"
                ],
                other_sources=["https://openai.com/index/example"],
                with_search_window=True,
            )
            normalizer.normalize_artifact(artifact, artifact / "artifact-normalization.json")

    def test_recovery_artifact_without_primary_report_keeps_saved_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            write_json(artifact / "digest.json", {"image_prompt": SAFE_PROMPT})
            (artifact / "image-prompt.txt").write_text(SAFE_PROMPT, encoding="utf-8")
            write_json(
                artifact / "run-info.json",
                {
                    "status": "ok",
                    "pipeline": "editorial_from_saved_research",
                    "research": {
                        "status": "ok",
                        "settings": {"source": "saved_fixture"},
                        "response": {"web_search_calls": 0},
                    },
                },
            )
            normalizer.normalize_artifact(artifact, artifact / "artifact-normalization.json")
            run_info = json.loads((artifact / "run-info.json").read_text(encoding="utf-8"))
            self.assertEqual(run_info["pipeline"], "editorial_from_saved_research")
            self.assertEqual(run_info["research"]["settings"]["source"], "saved_fixture")


    def test_final_pool_post_cutoff_same_day_agency_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=["https://www.bloomberg.com/authors/EXAMPLE/example-author"],
                other_sources=["https://openai.com/index/example", "https://nvidia.com/example"],
                with_search_window=True,
            )
            write_json(
                artifact / "candidates.json",
                {
                    "candidates": [
                        {
                            "published_date": "2026-08-13",
                            "published_at": "2026-08-13T12:00:00+03:00",
                            "time_precision": "datetime",
                            "primary_source": {
                                "url": "https://www.reuters.com/technology/post-cutoff-2026-08-13/"
                            },
                        }
                    ]
                },
            )
            with self.assertRaises(normalizer.NormalizationError):
                normalizer.normalize_artifact(
                    artifact, artifact / "artifact-normalization.json"
                )

    def test_final_pool_exact_pre_cutoff_agency_evidence_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = self.make_artifact(
                Path(tmp),
                agency_sources=["https://www.bloomberg.com/authors/EXAMPLE/example-author"],
                other_sources=["https://openai.com/index/example", "https://nvidia.com/example"],
                with_search_window=True,
            )
            write_json(
                artifact / "candidates.json",
                {
                    "candidates": [
                        {
                            "published_date": "2026-08-13",
                            "published_at": "2026-08-13T02:00:00+03:00",
                            "time_precision": "datetime",
                            "primary_source": {
                                "url": "https://www.reuters.com/technology/pre-cutoff-2026-08-13/"
                            },
                        }
                    ]
                },
            )
            normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )

if __name__ == "__main__":
    unittest.main()
