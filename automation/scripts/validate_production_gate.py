from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from release_common import current_iso, parse_iso_datetime, read_json, resolve_from_root, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Проверить production release gate без публикации.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--actual-ref", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--manual-approval", default="false")
    parser.add_argument("--now", default=None)
    parser.add_argument("--expect-blocked", action="store_true")
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def boolean(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def validate_gate(
    config: dict[str, Any],
    manifest: dict[str, Any],
    actual_ref: str,
    event_name: str,
    manual_approval: bool,
    now: datetime,
) -> dict[str, Any]:
    blockers: list[str] = []
    checks: dict[str, bool] = {}

    checks["production_enabled"] = config.get("production_enabled") is True
    if not checks["production_enabled"]:
        blockers.append("production_enabled=false")

    expected_ref = f"refs/heads/{config.get('production_branch', 'main')}"
    checks["production_branch"] = actual_ref == expected_ref
    if not checks["production_branch"]:
        blockers.append(f"branch must be {expected_ref}")

    checks["manual_event"] = event_name == "workflow_dispatch"
    if not checks["manual_event"]:
        blockers.append("event must be workflow_dispatch")

    checks["manual_approval"] = manual_approval or not bool(config.get("require_manual_approval", True))
    if not checks["manual_approval"]:
        blockers.append("manual approval is missing")

    checks["manifest_ok"] = manifest.get("status") == "ok"
    if not checks["manifest_ok"]:
        blockers.append("release manifest status is not ok")

    checks["production_release_kind"] = manifest.get("release_kind") == "production"
    if not checks["production_release_kind"]:
        blockers.append("release_kind is not production")

    checks["production_eligible"] = manifest.get("production_eligible") is True
    if not checks["production_eligible"]:
        blockers.append("production_eligible is not true")

    if manifest.get("release_kind") == "golden_fixture" and not config.get("allow_golden_fixture_in_production", False):
        blockers.append("golden fixtures are forbidden in production")
        checks["golden_fixture_forbidden"] = False
    else:
        checks["golden_fixture_forbidden"] = True

    published_at_raw = str(manifest.get("published_at", ""))
    try:
        published_at = parse_iso_datetime(published_at_raw)
        timezone = ZoneInfo(str(config.get("publication_timezone", "Europe/Moscow")))
        age_hours = (now.astimezone(timezone) - published_at.astimezone(timezone)).total_seconds() / 3600
        max_age = float(config.get("max_candidate_age_hours", 36))
        checks["fresh_candidate"] = 0 <= age_hours <= max_age
        if not checks["fresh_candidate"]:
            blockers.append(f"candidate age {age_hours:.1f}h is outside 0..{max_age:.1f}h")
    except Exception as exc:
        age_hours = None
        checks["fresh_candidate"] = False
        blockers.append(f"invalid published_at: {exc}")

    validations = manifest.get("validations") if isinstance(manifest.get("validations"), dict) else {}
    expected_validations = {
        "editorial_artifact": "ok",
        "cover_contract": "ok",
        "visual_review": "accepted",
        "site": "ok",
        "dzen_feed": "ok",
    }
    validation_ok = True
    for name, expected in expected_validations.items():
        entry = validations.get(name)
        actual = entry.get("status") if isinstance(entry, dict) else entry
        if actual != expected:
            validation_ok = False
            blockers.append(f"validation {name} is not {expected}")
    checks["validations"] = validation_ok

    safety = manifest.get("safety") if isinstance(manifest.get("safety"), dict) else {}
    safety_ok = (
        safety.get("live_posts_unchanged") is True
        and safety.get("ftp_used") is False
        and safety.get("request_files_changed") is False
    )
    checks["safety"] = safety_ok
    if not safety_ok:
        blockers.append("release safety flags are not clean")

    return {
        "schema_version": 1,
        "status": "ready" if not blockers else "blocked",
        "checked_at": current_iso(),
        "actual_ref": actual_ref,
        "expected_ref": expected_ref,
        "event_name": event_name,
        "manual_approval": manual_approval,
        "release_id": manifest.get("release_id"),
        "release_kind": manifest.get("release_kind"),
        "production_eligible": manifest.get("production_eligible"),
        "candidate_age_hours": age_hours,
        "checks": checks,
        "blockers": blockers,
    }


def main() -> int:
    args = parse_args()
    try:
        config = read_json(resolve_from_root(args.config))
        manifest = read_json(resolve_from_root(args.manifest))
        if not isinstance(config, dict) or not isinstance(manifest, dict):
            raise RuntimeError("Config и manifest должны быть JSON-объектами.")
        now = parse_iso_datetime(args.now) if args.now else datetime.now().astimezone()
        report = validate_gate(
            config,
            manifest,
            args.actual_ref,
            args.event_name,
            boolean(args.manual_approval),
            now,
        )
        write_json(resolve_from_root(args.report), report)
        if args.expect_blocked:
            if report["status"] != "blocked":
                print("Production gate unexpectedly became ready.", file=sys.stderr)
                return 1
            print("Production gate is safely blocked")
            for blocker in report["blockers"]:
                print(f"- {blocker}")
            return 0
        if report["status"] != "ready":
            print("Production gate blocked:", file=sys.stderr)
            for blocker in report["blockers"]:
                print(f"- {blocker}", file=sys.stderr)
            return 1
        print("Production gate ready. This script still performs no publication.")
        return 0
    except Exception as exc:
        print(f"Production gate check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
