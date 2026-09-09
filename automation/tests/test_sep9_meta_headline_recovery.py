from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import recover_digest_artifact_v1 as recovery
import validate_digest_artifact as validator

FIXTURE = (
    ROOT
    / "automation"
    / "fixtures"
    / "recall"
    / "artifact-meta-headline-2026-09-09.json"
)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def error_codes(report: dict) -> list[str]:
    return [str(row.get("code") or "") for row in report.get("errors", [])]


class Sep09MetaHeadlineRecoveryTests(unittest.TestCase):
    def test_exact_sep9_meta_display_marker_is_headline_equivalent(self) -> None:
        fixture = load_fixture()
        report = {"errors": [], "warnings": []}

        validator.validate_story_mapping(
            fixture["article_html"],
            fixture["candidates"],
            fixture["selection"],
            fixture["stories"],
            report,
        )

        self.assertEqual([], report["errors"])
        self.assertEqual(
            "Meta запустила потребительского агента Muse",
            validator.headline_identity_text(
                "Meta* запустила потребительского агента Muse"
            ),
        )

    def test_only_exact_meta_display_marker_is_normalized(self) -> None:
        self.assertEqual(
            "SomeMeta* запустила агента",
            validator.headline_identity_text("SomeMeta* запустила агента"),
        )
        self.assertEqual(
            "Meta** запустила агента",
            validator.headline_identity_text("Meta** запустила агента"),
        )
        self.assertEqual(
            "Other* запустила агента",
            validator.headline_identity_text("Other* запустила агента"),
        )

    def test_real_headline_change_remains_fail_closed(self) -> None:
        fixture = load_fixture()
        bad = copy.deepcopy(fixture)
        bad["article_html"] = bad["article_html"].replace(
            "<h3>Meta* запустила потребительского агента Muse</h3>",
            "<h3>Meta* запустила другого потребительского агента Muse</h3>",
        )
        report = {"errors": [], "warnings": []}

        validator.validate_story_mapping(
            bad["article_html"],
            bad["candidates"],
            bad["selection"],
            bad["stories"],
            report,
        )

        self.assertEqual(["story_headline_order"], error_codes(report))

    def test_service_meta_star_rule_is_not_weakened(self) -> None:
        fixture = load_fixture()
        self.assertFalse(validator.contains_meta_star(fixture["stories"]))
        bad_stories = copy.deepcopy(fixture["stories"])
        bad_stories[0]["headline"] = "Meta* запустила потребительского агента Muse"
        self.assertTrue(validator.contains_meta_star(bad_stories))

    def test_saved_sep9_headline_error_can_be_revalidated(self) -> None:
        fixture = load_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "artifact-normalization.json").write_text(
                json.dumps({"status": "ok"}), encoding="utf-8"
            )
            (source / "artifact-validation.json").write_text(
                json.dumps(
                    {
                        "status": "error",
                        "errors": [fixture["saved_validation_error"]],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            reusable, reason = recovery._saved_stage_reports_are_reusable(source)

        self.assertTrue(reusable)
        self.assertIsNone(reason)
        self.assertIn(
            "story_headline_order",
            recovery.REVALIDATABLE_ARTIFACT_VALIDATION_CODES,
        )

    def test_mixed_or_unrelated_saved_validation_error_stays_fail_closed(self) -> None:
        fixture = load_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "artifact-normalization.json").write_text(
                json.dumps({"status": "ok"}), encoding="utf-8"
            )
            (source / "artifact-validation.json").write_text(
                json.dumps(
                    {
                        "status": "error",
                        "errors": [
                            fixture["saved_validation_error"],
                            {
                                "code": "story_source_not_candidate",
                                "message": "foreign provenance remains invalid",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            reusable, reason = recovery._saved_stage_reports_are_reusable(source)

        self.assertFalse(reusable)
        self.assertIsNotNone(reason)
        self.assertIn("story_source_not_candidate", str(reason))

    def test_existing_shared_source_revalidation_remains_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "artifact-validation.json").write_text(
                json.dumps(
                    {
                        "status": "error",
                        "errors": [
                            {
                                "code": "ambiguous_story_mapping",
                                "message": "legacy shared-source validator error",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            reusable, reason = recovery._saved_stage_reports_are_reusable(source)

        self.assertTrue(reusable)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
