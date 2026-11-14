"""2026-11-14 regression: normalization must never rewrite hash-bound editorial raw.

The published-day failure from run 43544298749 occurred after a validated
Editorial Repair response; normalizer appended two missing image constraints
to editorial-output-raw.json, breaking the response/RAW equality. No API calls.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import editorial_repair_guard as repair
import normalize_digest_artifact as normalizer
import validate_digest_artifact_base as base

DATE = "2026-11-14"
MISSING = ("без водяных знаков", "без узнаваемых лиц")
PROMPT = (
    "Изображение 16:9: точный заголовок «ИИ-Сводка за 14 ноября 2026». "
    "Главные визуальные темы: технологии. Композиция: символическая сцена. "
    "Стиль: иллюстрация без логотипов и без дополнительного текста."
)


def dump(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ValidatedRawNormalizationRegression(unittest.TestCase):
    def setup_saved_response(self, root: Path, *, meta_marker: bool = False):
        artifact = root / DATE
        artifact.mkdir()
        state = root / "production-daily"
        state.mkdir()
        raw = {
            "digest": {"image_prompt": PROMPT},
            "status": "ok",
            "selection_summary": "Meta* подтверждена" if meta_marker else "Подтверждено",
        }
        dump(artifact / "editorial-output-raw.json", raw)
        dump(artifact / "editorial-output.json", raw)
        dump(artifact / "digest.json", {"image_prompt": PROMPT})
        (artifact / "image-prompt.txt").write_text(PROMPT + "\n", encoding="utf-8")

        intent, request = "exact-intent", "exact-request"
        response_path = state / f"editorial-repair-{DATE}.response.json"
        journal_path = state / f"editorial-repair-{DATE}.json"
        envelope = repair._seal({
            "version": repair.VERSION,
            "publication_date": DATE,
            "intent_sha256": intent,
            "request_sha256": request,
            "response": {
                "output_text": json.dumps(raw, ensure_ascii=False),
                "status": "completed",
            },
        }, "response_sha256")
        dump(response_path, envelope)
        journal = repair._seal({
            "version": repair.VERSION,
            "publication_date": DATE,
            "state": "validated",
            "intent_sha256": intent,
            "request_sha256": request,
            "response_sha256": envelope["response_sha256"],
            "response_file": response_path.name,
            "validated_editorial_sha256": repair.canonical_sha256(raw),
        }, "journal_sha256")
        dump(journal_path, journal)
        return artifact, state, raw

    def test_missing_constraints_modify_derived_outputs_not_validated_raw(self):
        with tempfile.TemporaryDirectory() as td:
            artifact, state, raw = self.setup_saved_response(Path(td))
            original = (artifact / "editorial-output-raw.json").read_bytes()

            # This passes before normalization, then MUST still pass afterwards.
            repair.publication_safe(artifact, state)
            report = normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )
            repair.publication_safe(artifact, state)
            self.assertEqual(
                sha((artifact / "editorial-output-raw.json").read_bytes()),
                sha(original),
                "validated provider payload must never be rewritten",
            )
            self.assertNotIn("editorial-output-raw.json", report["changed_files"])
            self.assertEqual(
                repair.canonical_sha256(raw),
                repair.canonical_sha256(json.loads(original)),
            )
            for filename in ("digest.json", "editorial-output.json"):
                payload = json.loads((artifact / filename).read_text(encoding="utf-8"))
                prompt = (payload.get("digest") or payload)["image_prompt"]
                for required in MISSING:
                    self.assertIn(required, prompt)
            for required in MISSING:
                self.assertIn(
                    required, (artifact / "image-prompt.txt").read_text(encoding="utf-8")
                )
            self.assertNotIn("editorial-output-raw.json", report["changed_files"])

            # Deterministic repeated validation/recovery is idempotent.
            repeat = normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )
            self.assertNotIn("editorial-output-raw.json", repeat["changed_files"])
            repair.publication_safe(artifact, state)

    def test_raw_meta_marker_is_preserved_but_derived_marker_is_normalized(self):
        with tempfile.TemporaryDirectory() as td:
            artifact, state, original = self.setup_saved_response(
                Path(td), meta_marker=True
            )
            raw_bytes = (artifact / "editorial-output-raw.json").read_bytes()
            report = normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )
            repair.publication_safe(artifact, state)
            self.assertEqual(
                raw_bytes, (artifact / "editorial-output-raw.json").read_bytes()
            )
            raw = json.loads(raw_bytes)
            derived = json.loads(
                (artifact / "editorial-output.json").read_text(encoding="utf-8")
            )
            self.assertIn("Meta*", raw["selection_summary"])
            self.assertNotIn("Meta*", derived["selection_summary"])
            self.assertIn("editorial-output.json", report["changed_files"])
            self.assertNotIn("editorial-output-raw.json", report["changed_files"])

    def test_tampering_with_raw_is_still_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            artifact, state, _ = self.setup_saved_response(Path(td))
            normalizer.normalize_artifact(
                artifact, artifact / "artifact-normalization.json"
            )
            raw = json.loads(
                (artifact / "editorial-output-raw.json").read_text(encoding="utf-8")
            )
            raw["digest"]["image_prompt"] += " tampered"
            dump(artifact / "editorial-output-raw.json", raw)
            with self.assertRaisesRegex(
                repair.EditorialRepairError,
                "validated repair no longer matches final editorial artifact",
            ):
                repair.publication_safe(artifact, state)

    def test_public_validator_presentation_scope_excludes_forensic_raw(self):
        self.assertNotIn("editorial-output-raw.json", normalizer.JSON_FILES)
        self.assertNotIn("editorial-output-raw.json", normalizer.META_SERVICE_JSON_FILES)
        self.assertTrue(
            base.contains_meta_star({"selection_summary": "Meta* confirmed"})
        )
        # Visible service fields must still be normalized on output paths.
        out, changes = normalizer.normalize_meta_service_markers(
            {"selection_summary": "Meta* confirmed"}
        )
        self.assertEqual(out["selection_summary"], "Meta confirmed")
        self.assertEqual(len(changes), 1)


if __name__ == "__main__":
    unittest.main()
