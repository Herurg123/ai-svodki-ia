from __future__ import annotations

import argparse
import json
from pathlib import Path

from production_daily_common import parse_rss, read_json, write_json

EXPECTED_CRONS = ["17 0 * * *", "37 0 * * *", "57 0 * * *"]

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
        "version": 3,
        "enabled": True,
        "timezone": "Europe/Moscow",
        "publication_hour_local": 6,
        "production_branch": "main",
        "feed_url": "https://rybalka.one/posts/rss.xml",
        "first_publication_date": "2026-07-24",
        "minimum_selected_stories": 7,
        "minimum_publishable_stories": 1,
        "regional_story_quotas_enabled": False,
        "short_digest_notice": "Новостей сегодня меньше, чем обычно",
        "short_digest_notice_html": (
            "<p><em>Новостей сегодня меньше, чем обычно</em></p>"
        ),
        "short_digest_notice_position": "first_article_block_after_cover",
        "coverage_audit_enabled": True,
        "coverage_audit_failure_blocks_publication": False,
        "coverage_audit_max_web_search_calls": 5,
        "coverage_audit_maximum_candidates": 20,
        "require_previous_day_in_rss": False,
        "allow_skipped_publication_days": True,
        "verify_previous_release_on_live_site": True,
    }
    for key, expected in required.items():
        if config.get(key) != expected:
            errors.append(
                f"config {key}: expected {expected!r}, got {config.get(key)!r}"
            )
    for forbidden_key in (
        "minimum_russian_candidates",
        "minimum_world_selected_stories",
        "minimum_russian_selected_stories",
    ):
        if forbidden_key in config:
            errors.append(
                f"config must not restore regional quota key: {forbidden_key}"
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
        ("resilient digest wrapper", "run_digest_preview.py"),
        ("resilient site builder", "run_build_site.py"),
        ("resilient site validator", "run_validate_site.py"),
        ("provisional editorial handoff", "--allow-provisional-editorial"),
        ("pre-paid no-op gate", "Check RSS before paid APIs"),
        (
            "previous release verification",
            "verify_previous_release.py",
        ),
        (
            "search window continuity",
            "validate_search_window_continuity.py",
        ),
        (
            "Russian production status",
            "summarize_production_status.py",
        ),
        (
            "Russian status step",
            "Publish Russian pipeline status",
        ),
        (
            "overall workflow status",
            "Итог публикации",
        ),
        ("successful no-op", "successful no-op"),
        ("deploy-only recovery", "Redeploy already committed release"),
        ("live URL gate", "ai-svodki-production-gate/1.0"),
        ("current main checkout", "ref: main"),
        ("image API", "generate_image_preview.py"),
        ("production source manifest", "artifact-validation.json"),
        ("recovery input", "recovery_run_id"),
        (
            "automatic recovery lookup",
            "Resolve reusable artifact",
        ),
        (
            "artifact API lookup",
            "actions/artifacts?name=daily-production-",
        ),
        (
            "terminal editorial stop reuse",
            "Reuse completed editorial stop without paid APIs",
        ),
        (
            "terminal editorial stop output",
            'echo "stop=${stop}" >> "${GITHUB_OUTPUT}"',
        ),
        (
            "terminal editorial stop guard",
            "steps.terminal_reuse.outputs.stop != 'true'",
        ),
        ("recovery artifact download", "actions/download-artifact@v8"),
        ("deterministic recovery", "recover_digest_artifact.py"),
        ("recovered image target", "--image-target-dir"),
        ("recovered image output", "image_recovered"),
        ("skip duplicate image request", "steps.recovery.outputs.image_recovered != 'true'"),
        ("revalidate recovered cover", "Revalidate recovered production cover"),
        ("partial paid artifact recovery", "Runs for both fresh and recovered artifacts"),
        ("recovery freshness", "--timezone Europe/Moscow"),
        ("shared digest normalization", "normalize_digest_artifact.py"),
        ("shared digest validation", "Normalize and validate digest artifact"),
        ("targeted coverage audit", "ensure_story_coverage.py"),
        ("publishable story validation", "validate_story_coverage.py"),
        ("usual seven-story target", "--usual-total 7"),
        ("one-story publication floor", "--minimum-publishable 1"),
        ("bounded audit searches", "--maximum-audit-web-search-calls 5"),
        (
            "fresh research after unusable automatic recovery",
            "if: steps.recovery.outputs.reused != 'true'",
        ),
        (
            "automatic artifact eligibility check",
            "/actions/runs/${candidate_run_id}/jobs?per_page=100",
        ),
        (
            "automatic recovery fallback output",
            'echo "reused=false" >> "${GITHUB_OUTPUT}"',
        ),
        (
            "successful recovery output",
            r'stream.write("reused=true\n")',
        ),
        (
            "recovered image output newline",
            r'+ "\n"',
        ),
        (
            "zero-story terminal reuse",
            "candidate_pool_after",
        ),
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
        (
            "deployment requires a committed release",
            "needs.production.outputs.commit_sha != ''",
        ),
        ("deployment secrets", "secrets: inherit"),
        ("artifact upload", "upload-artifact"),
    ]
    for label, needle in checks:
        if needle not in workflow:
            errors.append(f"workflow missing {label}: {needle}")
    for forbidden_needle in (
        "--minimum-world",
        "--minimum-russia",
        "--minimum-russian-candidates",
        "Enforce 5 world plus 2 Russian stories",
    ):
        if forbidden_needle in workflow:
            errors.append(
                "workflow must not restore a regional story quota: "
                f"{forbidden_needle}"
            )
    repository_root = args.workflow.resolve().parents[2]
    runtime_path = repository_root / "automation/scripts/editorial_policy_runtime.py"
    runtime_consumers = {
        "digest wrapper": repository_root / "automation/scripts/run_digest_preview.py",
        "site builder wrapper": repository_root / "automation/scripts/run_build_site.py",
        "site validator wrapper": repository_root / "automation/scripts/run_validate_site.py",
    }
    if not runtime_path.is_file():
        errors.append(f"shared agent policy runtime missing: {runtime_path}")
    for label, path in runtime_consumers.items():
        if not path.is_file():
            errors.append(f"{label} missing: {path}")
            continue
        consumer_text = path.read_text(encoding="utf-8")
        if "editorial_policy_runtime" not in consumer_text:
            errors.append(f"{label} does not import editorial_policy_runtime: {path}")
        if "patch_editorial_policy" not in consumer_text:
            errors.append(f"{label} does not apply patch_editorial_policy: {path}")

    terminal_step_start = workflow.find(
        "- name: Reuse completed editorial stop without paid APIs"
    )
    terminal_step_end = workflow.find("- name:", terminal_step_start + 10)
    terminal_step = (
        workflow[terminal_step_start:terminal_step_end]
        if terminal_step_start >= 0 and terminal_step_end > terminal_step_start
        else ""
    )
    if "exit 1" in terminal_step:
        errors.append(
            "reused completed editorial stop must finish as a successful no-op"
        )
    if 'echo "stop=${stop}" >> "${GITHUB_OUTPUT}"' not in terminal_step:
        errors.append("terminal reuse step must expose the stop output")
    guarded_steps = [
        "Restore saved paid artifact",
        "Install pinned OpenAI SDK",
        "Validate API configuration",
        "Patch runtime publication hour to 06:00 Moscow",
        "Validate editorial code and bootstrap archive",
        "Verify search window starts at last successful release",
        "Run full research and editorial",
        "Supplement a short digest when possible",
        "Normalize and validate digest artifact",
        "Validate publishable story count and short digest marker",
        "Build runtime Image API request",
        "Generate one production cover",
        "Revalidate recovered production cover",
        "Stage accepted legacy images under canonical posts/images",
        "Build and validate candidate site",
        "Dry-run or promote candidate",
        "Refresh archive after promotion",
        "Commit production release",
    ]
    for step_name in guarded_steps:
        step_start = workflow.find(f"- name: {step_name}")
        step_end = workflow.find("- name:", step_start + 10)
        if step_start < 0:
            errors.append(f"workflow missing guarded step: {step_name}")
            continue
        if step_end < 0:
            step_end = len(workflow)
        step_text = workflow[step_start:step_end]
        if "steps.terminal_reuse.outputs.stop != 'true'" not in step_text:
            errors.append(
                f"workflow step is not protected from terminal artifact reuse: {step_name}"
            )
    deploy_start = workflow.find("  deploy:")
    final_status_start = workflow.find("  final_status:", deploy_start + 1)
    deploy_job = (
        workflow[deploy_start:final_status_start]
        if deploy_start >= 0 and final_status_start > deploy_start
        else ""
    )
    if "needs.production.outputs.commit_sha != ''" not in deploy_job:
        errors.append("deploy job must require a non-empty production commit SHA")

    coverage_step_start = workflow.find(
        "- name: Supplement a short digest when possible"
    )
    coverage_step_end = workflow.find("- name:", coverage_step_start + 10)
    coverage_step = (
        workflow[coverage_step_start:coverage_step_end]
        if coverage_step_start >= 0 and coverage_step_end > coverage_step_start
        else ""
    )
    if "if: inputs.recovery_run_id == ''" in coverage_step:
        errors.append("coverage audit must also run for recovered partial artifacts")
    if workflow.count("run_digest_preview.py") < 1:
        errors.append("workflow must invoke the resilient digest wrapper")
    if "python automation/scripts/build_site.py" in workflow:
        errors.append("workflow must call run_build_site.py, not build_site.py directly")
    if "python automation/scripts/validate_site.py" in workflow:
        errors.append("workflow must call run_validate_site.py, not validate_site.py directly")
    if workflow.count("steps.recovery.outputs.image_recovered != 'true'") != 2:
        errors.append("image request and image generation must both skip a recovered cover")
    if workflow.count("steps.recovery.outputs.image_recovered == 'true'") != 1:
        errors.append("workflow must revalidate exactly one recovered cover")
    for cron in EXPECTED_CRONS:
        needle = f'cron: "{cron}"'
        if workflow.count(needle) != 1:
            errors.append(f"workflow must contain exactly one cron {cron}")
    if workflow.count("cron:") != len(EXPECTED_CRONS):
        errors.append("workflow must contain exactly three production crons")
    if workflow.count("validate_digest_artifact.py") != 1:
        errors.append("workflow must validate the digest exactly once after normalization")
    runtime_position = workflow.find(
        "Prepare runtime and verify archive freshness"
    )
    previous_release_position = workflow.find(
        "Verify last successful release in repository and live site"
    )
    bootstrap_position = workflow.find(
        "Validate editorial code and bootstrap archive"
    )
    continuity_position = workflow.find(
        "Verify search window starts at last successful release"
    )
    research_position = workflow.find("Run full research and editorial")
    summary_position = workflow.find("Publish Russian pipeline status")
    artifact_position = workflow.find("actions/upload-artifact@v7")
    if (
        runtime_position < 0
        or previous_release_position < 0
        or runtime_position > previous_release_position
    ):
        errors.append(
            "previous release verification must run after runtime preparation"
        )
    if (
        bootstrap_position < 0
        or continuity_position < 0
        or research_position < 0
        or not (
            bootstrap_position
            < continuity_position
            < research_position
        )
    ):
        errors.append(
            "search window continuity must run after archive bootstrap "
            "and before paid research"
        )
    if (
        summary_position < 0
        or artifact_position < 0
        or summary_position > artifact_position
    ):
        errors.append(
            "Russian pipeline status must be written before artifact upload"
        )
    if "if: always()" not in workflow[
        max(0, summary_position - 120):
        summary_position + 200
    ]:
        errors.append("Russian pipeline status must run with if: always()")
    coverage_audit_position = workflow.find(
        "Supplement a short digest when possible"
    )
    normalize_position = workflow.find("Normalize and validate digest artifact")
    coverage_validation_position = workflow.find(
        "Validate publishable story count and short digest marker"
    )
    image_request_position = workflow.find("Build runtime Image API request")
    if coverage_audit_position < 0 or normalize_position < 0 or coverage_audit_position > normalize_position:
        errors.append("targeted coverage audit must run before digest normalization")
    if (
        coverage_validation_position < 0
        or image_request_position < 0
        or coverage_validation_position > image_request_position
    ):
        errors.append(
            "publishable story validation must run before the image request"
        )
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
            "03:17 Europe/Moscow",
            "03:37 Europe/Moscow",
            "03:57 Europe/Moscow",
        ],
        "schedule_utc": EXPECTED_CRONS,
        "first_publication_date": config["first_publication_date"],
        "deployment_mode": "reusable_workflow_call",
        "duplicate_policy": "successful_noop_before_paid_api",
        "recovery_mode": "full_partial_or_research_only_then_coverage_repair",
        "commit_guard": "stage_publish_paths_ignore_runtime_outputs",
        "continuity_policy": "from_last_successfully_published_release",
        "skipped_calendar_days": "allowed",
        "live_previous_release_check": True,
        "failure_status": "Russian summary and GitHub annotations",
        "story_coverage_contract": {
            "usual_total": 7,
            "minimum_publishable": 1,
            "regional_story_quotas_enabled": False,
            "audit_failure_blocks_publication": False,
            "audit_max_web_search_calls": 5,
        },
    }
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1

if __name__ == "__main__":
    raise SystemExit(main())
