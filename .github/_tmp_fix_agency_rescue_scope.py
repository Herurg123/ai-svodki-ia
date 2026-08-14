from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:140]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Scope the new source-health contract to modern Primary artifacts. Historical
# fixtures/releases without primary-recall.json never had this gate and must
# stay no-op/reusable without requiring a new paid search.
replace_once(
    "automation/scripts/ensure_story_coverage_policy.py",
    '''AGENCY_SOURCE_HEALTH_DOMAINS: tuple[str, ...] = (\n    "reuters.com",\n    "apnews.com",\n    "bloomberg.com",\n    "ft.com",\n)\n''',
    '''AGENCY_SOURCE_HEALTH_DOMAINS: tuple[str, ...] = (\n    "reuters.com",\n    "apnews.com",\n    "bloomberg.com",\n    "ft.com",\n)\nSOURCE_HEALTH_CONTRACT_VERSION = 1\n''',
)
marker = '''def completed_prior_audit(payload: Any) -> bool:\n'''
# This function lives later in the policy file; add a conditional wrapper after
# it rather than changing legacy completed_prior_audit semantics globally.
p = Path("automation/scripts/ensure_story_coverage_policy.py")
text = p.read_text(encoding="utf-8")
func_end = '''    return bool(\n        payload.get("web_search_performed") is True\n        and payload.get("audit_status") in {"complete", "complete_with_gaps"}\n        and set(payload.get("checked_directions") or ())\n        == set(AUDIT_DIRECTION_IDS)\n        and isinstance(api, dict)\n        and api.get("status") == "completed"\n    )\n\n\ndef _remove_short_notices'''
replacement = '''    return bool(\n        payload.get("web_search_performed") is True\n        and payload.get("audit_status") in {"complete", "complete_with_gaps"}\n        and set(payload.get("checked_directions") or ())\n        == set(AUDIT_DIRECTION_IDS)\n        and isinstance(api, dict)\n        and api.get("status") == "completed"\n    )\n\n\ndef completed_prior_audit_for_source_health(\n    payload: Any, *, source_health_rescue_needed: bool\n) -> bool:\n    """Reuse legacy audits normally; version them only for modern source-health rescue."""\n    if not completed_prior_audit(payload):\n        return False\n    if not source_health_rescue_needed:\n        return True\n    return bool(\n        isinstance(payload, dict)\n        and payload.get("source_health_contract_version")\n        == SOURCE_HEALTH_CONTRACT_VERSION\n    )\n\n\ndef _remove_short_notices'''
if func_end not in text:
    raise SystemExit("completed_prior_audit end marker not found")
text = text.replace(func_end, replacement, 1)
old_scope = '''        source_health_rescue_needed = bool(\n            candidate_pool["total"] > 0\n            and not _candidates_have_fresh_agency_source(\n                research["candidates"], search_window\n            )\n        )\n        report["source_health_rescue_needed"] = source_health_rescue_needed\n'''
new_scope = '''        modern_primary_artifact = (args.artifact_dir / "primary-recall.json").is_file()\n        source_health_rescue_needed = bool(\n            modern_primary_artifact\n            and candidate_pool["total"] > 0\n            and not _candidates_have_fresh_agency_source(\n                research["candidates"], search_window\n            )\n        )\n        report["source_health_contract_required"] = modern_primary_artifact\n        report["source_health_rescue_needed"] = source_health_rescue_needed\n'''
if old_scope not in text:
    raise SystemExit("source-health scope marker not found")
text = text.replace(old_scope, new_scope, 1)
old_prior = '''        prior_attempted = prior_audit_attempted(prior_report)\n        prior_complete = completed_prior_audit(prior_report)\n'''
new_prior = '''        prior_attempted = prior_audit_attempted(prior_report)\n        prior_complete = completed_prior_audit_for_source_health(\n            prior_report, source_health_rescue_needed=source_health_rescue_needed\n        )\n'''
if old_prior not in text:
    raise SystemExit("prior complete marker not found")
text = text.replace(old_prior, new_prior, 1)
p.write_text(text, encoding="utf-8")

# Wrapper keeps zero-pool sentinel semantics but no longer globally invalidates
# every historical non-zero audit. The policy-level conditional wrapper decides
# whether current source-health versioning is required for this artifact.
p = Path("automation/scripts/ensure_story_coverage.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    'SOURCE_HEALTH_CONTRACT_VERSION = 1\n',
    'SOURCE_HEALTH_CONTRACT_VERSION = _policy.SOURCE_HEALTH_CONTRACT_VERSION\n',
    1,
)
old_version = '''    if (\n        isinstance(pool_total, int)\n        and pool_total > 0\n        and payload.get("source_health_contract_version")\n        != SOURCE_HEALTH_CONTRACT_VERSION\n    ):\n        return False\n    return True\n'''
if old_version not in text:
    raise SystemExit("wrapper legacy version block not found")
text = text.replace(old_version, '    return True\n', 1)
p.write_text(text, encoding="utf-8")

# New test loader needs the scripts directory on sys.path because the runtime
# intentionally imports story_coverage as a sibling module.
p = Path("automation/tests/test_agency_rescue.py")
text = p.read_text(encoding="utf-8")
old_loader = '''ROOT = Path(__file__).resolve().parents[2]\nSCRIPTS = ROOT / "automation" / "scripts"\n\n\ndef load_module'''
new_loader = '''ROOT = Path(__file__).resolve().parents[2]\nSCRIPTS = ROOT / "automation" / "scripts"\nsys.path.insert(0, str(SCRIPTS))\n\n\ndef load_module'''
if old_loader not in text:
    raise SystemExit("test loader marker not found")
text = text.replace(old_loader, new_loader, 1)
old_test = '''        self.assertFalse(runtime.completed_prior_audit(report))\n        report["source_health_contract_version"] = runtime.SOURCE_HEALTH_CONTRACT_VERSION\n        self.assertTrue(runtime.completed_prior_audit(report))\n'''
new_test = '''        self.assertTrue(runtime.completed_prior_audit(report))\n        self.assertFalse(\n            runtime._policy.completed_prior_audit_for_source_health(\n                report, source_health_rescue_needed=True\n            )\n        )\n        report["source_health_contract_version"] = runtime.SOURCE_HEALTH_CONTRACT_VERSION\n        self.assertTrue(\n            runtime._policy.completed_prior_audit_for_source_health(\n                report, source_health_rescue_needed=True\n            )\n        )\n'''
if old_test not in text:
    raise SystemExit("agency version test marker not found")
text = text.replace(old_test, new_test, 1)
p.write_text(text, encoding="utf-8")

# Make the legacy compatibility regression explicit rather than merely relying
# on existing historical fixtures.
p = Path("automation/tests/test_recall_sentinel.py")
text = p.read_text(encoding="utf-8")
old_name = '    def test_nonzero_completed_legacy_audit_remains_reusable(self) -> None:\n'
if old_name not in text:
    raise SystemExit("legacy audit test marker missing")
# Existing assertion remains correct; no code change needed, only leave it as
# the protected compatibility contract.

# Docs: rescue is a modern Primary source-health extension, not a retroactive
# requirement for historical artifacts that predate primary-recall diagnostics.
for path in ("README.md", "automation/README.md", "AGENTS.md"):
    p = Path(path)
    value = p.read_text(encoding="utf-8")
    anchor = "Normalizer принимает свежую agency evidence либо из Primary diagnostics, либо из\nфинального validated candidate pool после mandatory Coverage; он не требует,\nчтобы найденный агентский материал возник именно в Primary-слое."
    addition = anchor + "\nЭтот rescue-контракт применяется только к modern Primary artifacts с `primary-recall.json`; legacy-выпуски без Primary diagnostics сохраняют прежнюю recovery-совместимость и не требуют нового платного поиска."
    if anchor in value and "legacy-выпуски без Primary diagnostics" not in value:
        value = value.replace(anchor, addition, 1)
    p.write_text(value, encoding="utf-8")

Path(".github/_tmp_fix_agency_rescue_scope.py").unlink()
