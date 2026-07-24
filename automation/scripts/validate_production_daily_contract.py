from __future__ import annotations

import argparse
import json
from pathlib import Path

from production_daily_common import parse_rss, read_json, write_json

EXPECTED_CRONS = ["17 3 * * *", "37 3 * * *", "57 3 * * *"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--site-config", type=Path, required=True)
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--rss", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    config = read_json(args.config)
    site = read_json(args.site_config)
    workflow = args.workflow.read_text(encoding="utf-8")
    deploy_workflow_path = args.workflow.with_name("deploy-posts.yml")
    deploy_workflow = (
        deploy_workflow_path.read_text(encoding="utf-8")
        if deploy_workflow_path.exists()
        else ""
    )
    rss = parse_rss(args.rss)
    errors: list[str] = []

    required = {
        "enabled": True,
        "timezone": "Europe/Moscow",
        "publication_hour_local": 6,
        "production_branch": "main",
        "feed_url": "https://rybalka.one/posts/rss.xml",
        "first_publication_date": "2026-07-24",
    }
    for key, expected in required.items():
        if config.get(key) != expected:
            errors.append(
                f"config {key}: expected {expected!r}, got {config.get(key)!r}"
            )

    if config.get("schedule_crons_utc") != EXPECTED_CRONS:
        errors.append(
            "config schedule_crons_utc must contain the three accepted backup windows"
        )
    if config.get("schedule_cron_utc") != EXPECTED_CRONS[0]:
        errors.append("config schedule_cron_utc must equal the primary window")
    if config.get("publication_minute_local") != 17:
        errors.append("config publication_minute_local must equal 17")

    if site.get("feed_url") != config.get("feed_url"):
        errors.append("site feed_url differs from production feed_url")
    if site.get("timezone") != config.get("timezone"):
        errors.append("site timezone differs from production timezone")

    checks = [
        ("main branch guard", "refs/heads/main"),
        ("contents write", "contents: write"),
        ("actions read", "actions: read"),
        ("full digest", "PIPELINE_MODE: full"),
        ("pre-paid no-op gate", "Check RSS before paid APIs"),
        ("successful no-op", "successful no-op"),
        ("deploy-only recovery", "Redeploy already committed release"),
        ("live URL gate", "ai-svodki-production-gate/1.0"),
        ("current main checkout", "ref: main"),
        ("image API", "generate_image_preview.py"),
        ("production source manifest", "artifact-validation.json"),
        ("recovery input", "recovery_run_id"),
        ("recovery artifact download", "actions/download-artifact@v8"),
        ("deterministic recovery", "recover_digest_artifact.py"),
        ("recovery freshness", "--timezone Europe/Moscow"),
        ("shared digest normalization", "normalize_digest_artifact.py"),
        ("shared digest validation", "Normalize and validate digest artifact"),
        ("recovery skips research", "if: inputs.recovery_run_id == ''"),
        ("legacy image staging", "stage_legacy_images.py"),
        ("RSS normalization", "normalize_production_rss.py"),
        ("structured data", "inject_blogposting_schema.py"),
        ("structured data validation", "validate_structured_data.py"),
        ("posts sitemap", "build_posts_sitemap.py"),
        ("posts sitemap validation", "validate_posts_sitemap.py"),
        ("site promotion", "promote_production_site.py"),
        ("publish change validation", "validate_publish_changes.py"),
        ("publish change report", "publish-changes.json"),
        ("git push", "git push origin HEAD:main"),
        ("commit SHA output", 'echo "commit_sha=${commit_sha}"'),
        ("reusable deployment", "uses: ./.github/workflows/deploy-posts.yml"),
        ("deployment dependency", "needs: production"),
        ("deployment ref", "needs.production.outputs.commit_sha"),
        ("deployment secrets", "secrets: inherit"),
        ("artifact upload", "upload-artifact"),
    ]
    for label, needle in checks:
        if needle not in workflow:
            errors.append(f"workflow missing {label}: {needle}")

    for cron in EXPECTED_CRONS:
        needle = f'cron: "{cron}"'
        if workflow.count(needle) != 1:
            errors.append(f"workflow must contain exactly one cron {cron}")
    if workflow.count("cron:") != len(EXPECTED_CRONS):
        errors.append("workflow must contain exactly three production crons")
    if workflow.count("validate_digest_artifact.py") != 1:
        errors.append("workflow must validate the digest exactly once after normalization")
    normalize_position = workflow.find("Normalize and validate digest artifact")
    image_request_position = workflow.find("Build runtime Image API request")
    if normalize_position < 0 or image_request_position < 0 or normalize_position > image_request_position:
        errors.append("digest normalization/validation must run before the image request")

    for forbidden in ("FTP_SERVER", "FTP_USERNAME", "FTP_PASSWORD"):
        if forbidden in workflow:
            errors.append(f"production workflow must not access {forbidden}")
    if "gh workflow run deploy-posts.yml" in workflow:
        errors.append(
            "production workflow must call deploy-posts.yml as a reusable workflow, "
            "not dispatch it asynchronously"
        )
    if "starts automatically after the posts/** push" in workflow:
        errors.append(
            "workflow incorrectly assumes a GITHUB_TOKEN push starts another workflow"
        )

    if not deploy_workflow_path.exists():
        errors.append(f"deployment workflow missing: {deploy_workflow_path}")
    else:
        deploy_checks = [
            ("workflow_call", "workflow_call:"),
            ("exact ref input", "ref:"),
            ("checkout requested ref", "inputs.ref || github.sha"),
            ("FTP action", "SamKirkland/FTP-Deploy-Action@v4.4.0"),
            ("canonical local directory", "local-dir: ./posts/"),
            ("isolated FTP root", "server-dir: ./"),
        ]
        for label, needle in deploy_checks:
            if needle not in deploy_workflow:
                errors.append(f"deployment workflow missing {label}: {needle}")

    if rss["self_url"] != config["feed_url"]:
        errors.append("current RSS self URL is not the accepted root URL")
    legacy_count = sum(
        1
        for row in rss["items"]
        if row["link"].startswith(str(config["legacy_prefix"]))
    )
    if legacy_count < int(config["minimum_legacy_items"]):
        errors.append("current RSS does not contain required legacy dzen-test items")

    report = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "rss_latest_date": rss["latest_date"],
        "legacy_items": legacy_count,
        "schedule_local": [
            "06:17 Europe/Moscow",
            "06:37 Europe/Moscow",
            "06:57 Europe/Moscow",
        ],
        "schedule_utc": EXPECTED_CRONS,
        "first_publication_date": config["first_publication_date"],
        "deployment_mode": "reusable_workflow_call",
        "duplicate_policy": "successful_noop_before_paid_api",
        "recovery_mode": "deterministic_restore_freshness_normalize_validate",
        "commit_guard": "stage_publish_paths_ignore_runtime_outputs",
    }
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
