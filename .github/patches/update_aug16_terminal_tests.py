from pathlib import Path

path = Path("automation/tests/test_digest_artifact_primary_normalization.py")
text = path.read_text(encoding="utf-8")

old = '''            with self.assertRaises(normalizer.NormalizationError) as ctx:\n                normalizer.normalize_artifact(artifact, artifact / "artifact-normalization.json")\n            self.assertIn("Reuters/AP/Bloomberg/FT", str(ctx.exception))\n'''
new = '''            report = normalizer.normalize_artifact(\n                artifact, artifact / "artifact-normalization.json"\n            )\n            self.assertTrue(\n                any(\n                    "source-health warning" in warning\n                    for warning in report.get("warnings", [])\n                )\n            )\n'''
if text.count(old) != 1:
    raise SystemExit(f"stale-agency expectation: expected 1 match, got {text.count(old)}")
text = text.replace(old, new, 1)

old = '''            with self.assertRaises(normalizer.NormalizationError):\n                normalizer.normalize_artifact(\n                    artifact, artifact / "artifact-normalization.json"\n                )\n\n    def test_final_pool_exact_pre_cutoff_agency_evidence_is_accepted(self):\n'''
new = '''            report = normalizer.normalize_artifact(\n                artifact, artifact / "artifact-normalization.json"\n            )\n            self.assertTrue(\n                any(\n                    "source-health warning" in warning\n                    for warning in report.get("warnings", [])\n                )\n            )\n\n    def test_final_pool_exact_pre_cutoff_agency_evidence_is_accepted(self):\n'''
if text.count(old) != 1:
    raise SystemExit(f"post-cutoff expectation: expected 1 match, got {text.count(old)}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
