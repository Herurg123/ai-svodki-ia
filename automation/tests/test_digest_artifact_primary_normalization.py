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
    def make_artifact(self, root: Path, *, agency_sources: list[str], other_sources: list[str] | None = None) -> Path:
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
                "api": {"consulted_sources": [{"url": url} for url in agency_sources]},
            },
            {
                "direction_id": "global_breaking",
                "web_search_calls_completed": 1,
                "api": {"consulted_sources": [{"url": url} for url in (other_sources or [])]},
            },
        ]
        write_json(artifact / "primary-recall.json", {"directions": directions})
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


if __name__ == "__main__":
    unittest.main()
