from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "automation" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import recover_digest_artifact_v1 as recovery


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_sep3_obsolete_ambiguous_mapping_error_is_revalidatable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp)
        write_json(
            source / "artifact-validation.json",
            {
                "status": "error",
                "errors": [
                    {
                        "code": "ambiguous_story_mapping",
                        "message": "saved pre-#145 shared-source ambiguity",
                    }
                ],
            },
        )

        assert recovery._saved_stage_reports_are_reusable(source) == (True, None)


def test_mixed_saved_validation_error_remains_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp)
        write_json(
            source / "artifact-validation.json",
            {
                "status": "error",
                "errors": [
                    {"code": "ambiguous_story_mapping", "message": "obsolete"},
                    {"code": "metadata_mismatch", "message": "still invalid"},
                ],
            },
        )

        reusable, reason = recovery._saved_stage_reports_are_reusable(source)
        assert reusable is False
        assert "metadata_mismatch" in str(reason)


def test_unknown_or_empty_saved_validation_error_remains_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp)
        write_json(
            source / "artifact-validation.json",
            {"status": "error", "errors": []},
        )

        reusable, reason = recovery._saved_stage_reports_are_reusable(source)
        assert reusable is False
        assert "artifact-validation.json" in str(reason)


def test_saved_normalization_error_is_never_revalidated_by_this_exception() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp)
        write_json(
            source / "artifact-normalization.json",
            {"status": "error", "error": "normalization failed"},
        )
        write_json(
            source / "artifact-validation.json",
            {
                "status": "error",
                "errors": [{"code": "ambiguous_story_mapping", "message": "obsolete"}],
            },
        )

        reusable, reason = recovery._saved_stage_reports_are_reusable(source)
        assert reusable is False
        assert "artifact-normalization.json" in str(reason)


def test_recovery_still_removes_stale_artifact_validation_before_current_recheck() -> None:
    assert "artifact-validation.json" in recovery.IMAGE_STAGE_FILES
