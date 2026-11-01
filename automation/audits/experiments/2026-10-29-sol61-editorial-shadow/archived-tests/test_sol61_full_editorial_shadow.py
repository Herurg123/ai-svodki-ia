"""Offline integration checks for exact-input Sol shadow V2, no paid API."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation" / "scripts"))
import sol61_full_editorial_shadow as shadow

DAY = "2026-11-01"


def data(v):
    return (json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n").encode()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(value if isinstance(value, bytes) else data(value))


class MockClient:
    def __init__(self):
        self.calls = []
        self.responses = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        value = {
            "status": "ok", "error_message": None,
            "selected_candidate_ids": ["cand-002"],
            "excluded_candidate_ids": ["cand-001"],
            "selection_summary": "Sol independent",
            "diversity_overrides": [],
            "digest": {"article_html": "<h2>Original full article</h2>", "status": "ok"},
        }
        return SimpleNamespace(
            id="resp_mock", status="completed", model=shadow.SOL,
            service_tier="default", output_text=json.dumps(value, ensure_ascii=False),
            usage={"input_tokens": 180000, "output_tokens": 13000},
        )


class V2Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.artifact = self.root / "artifact"
        self.day = self.artifact / DAY
        self.output = self.root / "sol"
        self.archive = self.root / "archive.json"
        self.policy = self.root / "policy.json"
        self.site = self.root / "site.json"
        self.image = self.root / "image.json"
        self.prompt1 = ("Ты редактор. Дата выпуска: " + DAY + "\nInitial\n").encode()
        self.prompt2 = ("Ты редактор. Дата выпуска: " + DAY + "\nFinal\n").encode()
        self.pool = {"publication_date": DAY, "status": "ok",
                     "candidates": [{"id": "cand-001"}, {"id": "cand-002"}]}
        write(self.day / "editorial-prompt-input.txt", self.prompt2)
        write(self.day / "candidates.json", self.pool)
        write(self.day / "editorial-output-raw.json", {
            "status": "ok", "selected_candidate_ids": ["cand-001"],
            "selection_summary": "TERRA_SECRET", "digest": {"article_html": "terra"}},
        )
        write(self.day / "run-info.json", {
            "publication_date": DAY, "status": "ok", "model_requested": shadow.TERRA,
            "editorial": {"prompt_sha256": shadow.digest(self.prompt2)},
            "limits": {"minimum_selected_stories": 7, "maximum_selected_stories": 12},
        })
        write(self.archive, {"items": [{"date": "2026-10-31"}]})
        for p in [self.policy, self.site, self.image]:
            write(p, {})
        self.snapshot(self.prompt1, "2026-11-01T02:01:00+00:00")
        self.snapshot(self.prompt2, "2026-11-01T02:03:00+00:00")
        self.client = MockClient()

    def snapshot(self, prompt, timestamp):
        h = shadow.digest(prompt)
        root = self.artifact / "production-daily" / "editorial-input-snapshots" / DAY / h
        write(root / "prompt.txt", prompt)
        write(root / "candidates.json", self.pool)
        write(root / "provenance.json", {
            "publication_date": DAY, "model_requested": shadow.TERRA,
            "captured_at": timestamp,
            "prompt_sha256": h, "candidates_sha256": shadow.digest(data(self.pool)),
        })

    def perform(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "1",
                                     "AI_DIGEST_PUBLICATION_DATE": DAY}), \
                patch.object(shadow, "current_date_moscow", return_value=DAY), \
                patch.object(shadow, "validate_like_production",
                             return_value={"status": "pass", "errors": []}) as validate:
            report = shadow.run(publication_date=DAY, artifact=self.artifact,
                                archive_path=self.archive, policy_path=self.policy,
                                site_path=self.site, image_path=self.image,
                                output=self.output, client=self.client)
        return report, validate

    def test_exact_input_full_schema_multiple_attempts_independent_from_terra(self):
        before = (self.day / "editorial-output-raw.json").read_bytes()
        r, v = self.perform()
        self.assertEqual([q["input"].encode() for q in self.client.calls],
                         [self.prompt1, self.prompt2])
        self.assertEqual(v.call_count, 2)
        self.assertTrue(all(q["text"]["format"]["schema"] is shadow.gen.EDITORIAL_SCHEMA
                            for q in self.client.calls))
        self.assertTrue(all(q["max_output_tokens"] == 18000 and
                            q["reasoning"] == {"effort": "medium"} and
                            q["store"] is False and "tools" not in q
                            for q in self.client.calls))
        self.assertNotIn("TERRA_SECRET", str(self.client.calls))
        self.assertEqual(r["terra_only"], ["cand-001"])
        self.assertEqual(r["sol_only"], ["cand-002"])
        self.assertEqual((self.day / "editorial-output-raw.json").read_bytes(), before)
        manifest = shadow.read(self.output / "manifest.json")
        self.assertEqual(manifest["status"], "complete")
        self.assertTrue(all(shadow.digest((self.output / name).read_bytes()) == value
                            for name, value in manifest["files_sha256"].items()))

    def test_cap_preserves_final_and_discloses_skipped_attempts(self):
        for i in range(3):
            self.snapshot(("Ты редактор. Дата выпуска: " + DAY + f"\nBefore{i}\n").encode(),
                          f"2026-11-01T01:0{i}:00+00:00")
        attempts, _ = shadow.collect_attempts(self.artifact, DAY)
        self.assertEqual(len(attempts), 5)
        chosen, skipped = shadow.bounded_attempts(attempts)
        self.assertEqual(len(chosen), shadow.MAX_ATTEMPTS)
        self.assertEqual(len(skipped), 2)
        self.assertTrue(chosen[-1].is_final)

    def test_mutated_snapshot_fails_without_api(self):
        folder = (self.artifact / "production-daily" / "editorial-input-snapshots" /
                  DAY / shadow.digest(self.prompt1))
        (folder / "prompt.txt").write_bytes(b"TAMPER")
        with self.assertRaisesRegex(ValueError, "Corrupted"):
            self.perform()
        self.assertEqual(self.client.calls, [])

    def test_history_fallback_is_labeled(self):
        import shutil
        shutil.rmtree(self.artifact / "production-daily")
        attempts, _ = shadow.collect_attempts(self.artifact, DAY)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].source, "final_only_fallback")

    def test_no_old_dates_or_duplicate_calls(self):
        with patch.object(shadow, "current_date_moscow", return_value=DAY):
            with self.assertRaisesRegex(ValueError, "only permitted"):
                shadow.validate_date("2026-10-31")
        self.perform()
        with self.assertRaisesRegex(ValueError, "evidence exists"):
            self.perform()
        self.assertEqual(len(self.client.calls), 2)

    def test_workflow_only_optional_post_deploy_without_web_search(self):
        wf = (ROOT / ".github" / "workflows" / "daily-production.yml").read_text()
        s = wf.split("  sol61_editorial_shadow:\n", 1)[1].split("  final_status:\n", 1)[0]
        for token in ("sol61_full_editorial_shadow.py",
                      "needs.deploy.result == 'success'",
                      "needs.production.outputs.publish == 'true'",
                      "vars.SOL_EDITORIAL_AUDIT_ENABLED != 'false'",
                      "continue-on-error: true", "contents: read", "github.run_attempt == 1",
                      "name: daily-production-${{ needs.gate.outputs.publication_date }}"):
            self.assertIn(token.replace("${{", "$" + "{{"), s)
        for token in ("contents: write", "force_fresh_research", "push_protected_main.sh"):
            self.assertNotIn(token, s)
        self.assertEqual(wf.count('cron: "17 23 * * *"'), 1)

    def test_provider_does_not_enable_search_or_retries(self):
        source = (ROOT / "automation" / "scripts" /
                  "sol61_full_editorial_shadow.py").read_text()
        self.assertIn("max_retries=0, timeout=400", source)
        self.assertIn("schema\": gen.EDITORIAL_SCHEMA", source)
        self.assertNotIn("web_search_preview", source)

if __name__ == "__main__":
    unittest.main()
