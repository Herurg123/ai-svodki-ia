from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_replace_once(path: Path, pattern: str, replacement: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, got {count}")
    path.write_text(updated, encoding="utf-8")


workflow = ROOT / ".github/workflows/daily-production.yml"

old_resolver = '''          run_id="${MANUAL_RECOVERY_RUN_ID}"
          source="manual"
          if [[ -z "${run_id}" ]]; then
            source="automatic"
            run_id="$(
              gh api --paginate \\
                -H "X-GitHub-Api-Version: 2026-03-10" \\
                "/repos/${GITHUB_REPOSITORY}/actions/artifacts?name=daily-production-${PUBLICATION_DATE}&per_page=100" \\
                --jq '.artifacts[] | select(.expired == false and .workflow_run.id != null) | [.created_at, (.workflow_run.id | tostring)] | @tsv' \\
              | awk -v current="${GITHUB_RUN_ID}" '$2 != current { print }' \\
              | sort -r \\
              | sed -n '1p' \\
              | cut -f 2
            )"
          fi
'''
new_resolver = '''          run_id="${MANUAL_RECOVERY_RUN_ID}"
          source="manual"
          if [[ -z "${run_id}" ]]; then
            source="automatic"
            candidates="$(
              gh api --paginate \\
                -H "X-GitHub-Api-Version: 2022-11-28" \\
                "/repos/${GITHUB_REPOSITORY}/actions/artifacts?name=daily-production-${PUBLICATION_DATE}&per_page=100" \\
                --jq '.artifacts[] | select(.expired == false and .workflow_run.id != null) | [.created_at, (.workflow_run.id | tostring)] | @tsv' \\
              | awk -v current="${GITHUB_RUN_ID}" '$2 != current { print }' \\
              | sort -r
            )"
            while IFS=$'\\t' read -r _created_at candidate_run_id; do
              [[ -n "${candidate_run_id}" ]] || continue
              reusable_steps="$(
                gh api \\
                  -H "X-GitHub-Api-Version: 2022-11-28" \\
                  "/repos/${GITHUB_REPOSITORY}/actions/runs/${candidate_run_id}/jobs?per_page=100" \\
                  --jq '[.jobs[] | select(.name == "production") | .steps[]? | select((.name == "Run full research and editorial" or .name == "Restore saved paid artifact") and .conclusion == "success")] | length'
              )"
              if [[ "${reusable_steps}" -gt 0 ]]; then
                run_id="${candidate_run_id}"
                break
              fi
              echo "Skipping artifact from run ${candidate_run_id}: no reusable paid research/editorial step completed."
            done <<< "${candidates}"
          fi
'''
replace_once(workflow, old_resolver, new_resolver, "automatic artifact eligibility")

replace_once(
    workflow,
    '''      - name: Download saved editorial artifact for recovery
        if: steps.recovery_source.outputs.run_id != ''
        uses: actions/download-artifact@v8
''',
    '''      - name: Download saved editorial artifact for recovery
        if: steps.recovery_source.outputs.run_id != ''
        continue-on-error: ${{ steps.recovery_source.outputs.source == 'automatic' }}
        uses: actions/download-artifact@v8
''',
    "automatic download fallback",
)

old_terminal = '''          api = data.get("api") or {}
          terminal = (
              data.get("status") == "error"
              and data.get("web_search_performed") is True
              and api.get("status") == "completed"
          )
'''
new_terminal = '''          api = data.get("api") or {}
          pool_after = data.get("candidate_pool_after") or {}
          pool_total = pool_after.get("total") if isinstance(pool_after, dict) else None
          terminal = (
              data.get("status") == "error"
              and data.get("web_search_performed") is True
              and api.get("status") == "completed"
              and isinstance(pool_total, int)
              and pool_total == 0
          )
'''
replace_once(workflow, old_terminal, new_terminal, "zero-story terminal reuse")

recovery_pattern = r'''      - name: Restore saved paid artifact\n.*?(?=      - name: Install pinned OpenAI SDK\n)'''
new_recovery = '''      - name: Restore saved paid artifact
        id: recovery
        if: steps.recovery_source.outputs.run_id != '' && steps.terminal_reuse.outputs.stop != 'true'
        shell: bash
        env:
          PUBLICATION_DATE: ${{ steps.runtime.outputs.publication_date }}
          RECOVERY_RUN_ID: ${{ steps.recovery_source.outputs.run_id }}
          RECOVERY_SOURCE: ${{ steps.recovery_source.outputs.source }}
        run: |
          set +e
          python automation/scripts/recover_digest_artifact.py \\
            --recovery-root "automation/recovery/${RECOVERY_RUN_ID}" \\
            --target-dir "automation/preview/${PUBLICATION_DATE}" \\
            --publication-date "${PUBLICATION_DATE}" \\
            --timezone Europe/Moscow \\
            --image-target-dir "automation/preview/production-daily/image/${PUBLICATION_DATE}" \\
            --report automation/preview/production-daily/recovery.json
          recovery_status=$?
          set -e
          if [[ "${recovery_status}" -ne 0 ]]; then
            echo "reused=false" >> "${GITHUB_OUTPUT}"
            echo "image_recovered=false" >> "${GITHUB_OUTPUT}"
            if [[ "${RECOVERY_SOURCE}" == "manual" ]]; then
              echo "Manual recovery artifact is unusable; refusing to start paid research." >&2
              exit "${recovery_status}"
            fi
            rm -rf \\
              "automation/preview/${PUBLICATION_DATE}" \\
              "automation/preview/production-daily/image/${PUBLICATION_DATE}"
            echo "::warning title=Непригодный автоматический artifact::Artifact run ${RECOVERY_RUN_ID} не содержит завершённого платного research/editorial. Будет выполнен свежий research."
            exit 0
          fi
          python - <<'PY'
          import json
          import os
          from pathlib import Path
          report = json.loads(
              Path("automation/preview/production-daily/recovery.json").read_text(
                  encoding="utf-8"
              )
          )
          with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
              stream.write("reused=true\\n")
              stream.write(
                  "image_recovered="
                  + ("true" if report.get("image_recovered") else "false")
                  + "\\n"
              )
          PY
          echo "Recovered reusable paid artifact from run ${RECOVERY_RUN_ID}."
'''
regex_replace_once(workflow, recovery_pattern, new_recovery, "recovery fallback step")

replace_once(
    workflow,
    "        if: steps.recovery_source.outputs.run_id == '' && steps.terminal_reuse.outputs.stop != 'true'\n",
    "        if: steps.recovery.outputs.reused != 'true' && steps.terminal_reuse.outputs.stop != 'true'\n",
    "fresh research after unusable automatic artifact",
)

# Let the SDK honor Retry-After for transient 429 responses instead of immediately
# abandoning the only useful scheduled window.
generator = ROOT / "automation/scripts/generate_digest_preview.py"
generator_text = generator.read_text(encoding="utf-8")
if generator_text.count('"max_retries": 0') != 2:
    raise RuntimeError("generate_digest_preview settings retry count changed unexpectedly")
generator_text = generator_text.replace('"max_retries": 0', '"max_retries": 2')
if generator_text.count("max_retries=0") != 1:
    raise RuntimeError("generate_digest_preview client retry count changed unexpectedly")
generator_text = generator_text.replace("max_retries=0", "max_retries=2", 1)
generator.write_text(generator_text, encoding="utf-8")

coverage = ROOT / "automation/scripts/ensure_story_coverage.py"
coverage_text = coverage.read_text(encoding="utf-8")
if coverage_text.count("max_retries=0") != 1:
    raise RuntimeError("ensure_story_coverage retry count changed unexpectedly")
coverage.write_text(coverage_text.replace("max_retries=0", "max_retries=2", 1), encoding="utf-8")

validator = ROOT / "automation/scripts/validate_production_daily_contract.py"
replace_once(
    validator,
    '''        (
            "recovery skips full research",
            "if: steps.recovery_source.outputs.run_id == ''",
        ),
''',
    '''        (
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
            'stream.write("reused=true\\\\n")',
        ),
        (
            "zero-story terminal reuse",
            "candidate_pool_after",
        ),
''',
    "contract recovery checks",
)

reliability = ROOT / "automation/tests/test_production_reliability_patch.py"
replace_once(
    reliability,
    '''        self.assertIn("if: steps.recovery_source.outputs.run_id == ''", workflow)
''',
    '''        self.assertIn("if: steps.recovery.outputs.reused != 'true'", workflow)
        self.assertIn("/actions/runs/${candidate_run_id}/jobs?per_page=100", workflow)
        self.assertIn('echo "reused=false" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn('stream.write("reused=true\\\\n")', workflow)
        self.assertIn("candidate_pool_after", workflow)
        self.assertIn("RECOVERY_SOURCE", workflow)
''',
    "reliability recovery assertions",
)

sync_test = ROOT / "automation/tests/test_production_contract_sync.py"
replace_once(
    sync_test,
    '''        self.assertIn("needs.production.outputs.commit_sha != ''", workflow)
''',
    '''        self.assertIn("needs.production.outputs.commit_sha != ''", workflow)
        self.assertIn("if: steps.recovery.outputs.reused != 'true'", workflow)
        self.assertIn("/actions/runs/${candidate_run_id}/jobs?per_page=100", workflow)
        self.assertIn('echo "reused=false" >> "${GITHUB_OUTPUT}"', workflow)
        self.assertIn("candidate_pool_after", workflow)
''',
    "contract sync recovery assertions",
)

retry_test = ROOT / "automation/tests/test_rate_limit_retry_configuration.py"
retry_test.write_text(
    '''from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RateLimitRetryConfigurationTests(unittest.TestCase):
    def test_text_api_clients_retry_transient_rate_limits(self) -> None:
        generator = (
            ROOT / "automation/scripts/generate_digest_preview.py"
        ).read_text(encoding="utf-8")
        coverage = (
            ROOT / "automation/scripts/ensure_story_coverage.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("max_retries=0", generator)
        self.assertNotIn('"max_retries": 0', generator)
        self.assertIn("max_retries=2", generator)
        self.assertEqual(generator.count('"max_retries": 2'), 2)
        self.assertNotIn("max_retries=0", coverage)
        self.assertIn("max_retries=2", coverage)


if __name__ == "__main__":
    unittest.main()
''',
    encoding="utf-8",
)
