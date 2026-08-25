from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected one marker in {path}, got {text.count(old)}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


root = Path(__file__).resolve().parents[2]
sp = root / "automation/scripts/source_pulse.py"
shadow = root / "automation/scripts/source_pulse_shadow.py"
hybrid = root / "automation/scripts/hybrid_search_completeness.py"
tests = root / "automation/tests/test_source_pulse.py"
shadow_tests = root / "automation/tests/test_source_pulse_shadow.py"
auto_readme = root / "automation/README.md"
audit_md = root / "automation/audits/experiments/2026-08-25-source-pulse-shadow-integration.md"

replace_once(
    sp,
    '"""Research-only Source Pulse v1. Not wired into daily production."""',
    '"""Bounded Source Pulse v1 collector for offline replay and production shadow."""',
)
replace_once(
    sp,
    'UA="ai-svodki-source-pulse/1.0 research-only (+https://rybalka.one/posts/)"',
    'UA="ai-svodki-source-pulse/1.0 (+https://rybalka.one/posts/)"',
)
replace_once(
    sp,
    'GENERIC={"ai","artificial","intelligence","latest","news","release","releases","announces","announced","launches","launched","update","updated","company","group","inc","ltd","the","and","for","with","from","its","new","on","in","to","of","a","an"}\n',
    'GENERIC={"ai","artificial","intelligence","latest","news","release","releases","announces","announced","launches","launched","update","updated","company","group","inc","ltd","the","and","for","with","from","its","new","on","in","to","of","a","an"}\nTRACKING_QUERY_KEYS={"utm_source","utm_medium","utm_campaign","utm_term","utm_content","fbclid","gclid","mc_cid","mc_eid","ref","source"}\nSENSITIVE_QUERY_KEYS={"token","access_token","auth","authorization","signature","sig","credential","credentials","secret","api_key","apikey","key","x-amz-signature","x-amz-credential","x-amz-security-token","x-goog-signature","x-goog-credential"}\nSENSITIVE_QUERY_MARKERS=("token","signature","credential","secret","api_key","apikey","access_key")\n',
)
replace_once(
    sp,
    '''def norm_url(url:str)->str:\n    p=urllib.parse.urlsplit(url); q=urllib.parse.parse_qsl(p.query,keep_blank_values=False)\n    drop={"utm_source","utm_medium","utm_campaign","utm_term","utm_content","fbclid","gclid","mc_cid","mc_eid","ref","source"}\n    q=[(k,v) for k,v in q if k.lower() not in drop]\n    net=(p.hostname or "").lower()+((":"+str(p.port)) if p.port else "")\n    return urllib.parse.urlunsplit((p.scheme.lower(),net,p.path.rstrip("/") or "/",urllib.parse.urlencode(q),""))\n''',
    '''def _drop_query_key(key:str)->bool:\n    value=key.casefold().strip()\n    return value in TRACKING_QUERY_KEYS or value in SENSITIVE_QUERY_KEYS or any(marker in value for marker in SENSITIVE_QUERY_MARKERS)\n\ndef norm_url(url:str)->str:\n    p=urllib.parse.urlsplit(url); q=urllib.parse.parse_qsl(p.query,keep_blank_values=False)\n    q=[(k,v) for k,v in q if not _drop_query_key(k)]\n    net=(p.hostname or "").lower()+((":"+str(p.port)) if p.port else "")\n    return urllib.parse.urlunsplit((p.scheme.lower(),net,p.path.rstrip("/") or "/",urllib.parse.urlencode(q),""))\n\ndef safe_source_item_id(value:Any)->str:\n    raw=str(value or "").strip()\n    if raw.startswith("https://"):\n        return norm_url(raw)\n    if not raw:\n        return ""\n    return "opaque-sha256:"+hashlib.sha256(raw.encode()).hexdigest()[:24]\n''',
)
replace_once(
    sp,
    'seen.add(xf); local.append(PulseLead(s.id,s.tier,s.region,s.role,x.title,norm_url(x.url),x.published_date.isoformat() if x.published_date else None,x.published_at.isoformat() if x.published_at else None,x.time_precision,amb,x.source_item_id,ef,xf,norm_url(x.url) in archived))',
    'seen.add(xf); local.append(PulseLead(s.id,s.tier,s.region,s.role,x.title,norm_url(x.url),x.published_date.isoformat() if x.published_date else None,x.published_at.isoformat() if x.published_at else None,x.time_precision,amb,safe_source_item_id(x.source_item_id),ef,xf,norm_url(x.url) in archived))',
)
replace_once(
    sp,
    '"selected_url":chosen.final_url or chosen.requested_url,',
    '"selected_url":norm_url(chosen.final_url or chosen.requested_url),',
)
replace_once(
    sp,
    'summary={"configured_sources":len(registry),"sources_ok":sum(r["status"]=="ok" for r in reports),"sources_unavailable":sum(r["status"]=="source_unavailable" for r in reports),"sources_parse_error":sum(r["status"]=="parse_error" for r in reports),"lead_count":len(out),"eligible_new_lead_count":sum(not x.cutoff_ambiguous and not x.archive_url_duplicate for x in out),"tier_a_leads":sum(x.tier=="A" for x in out),"tier_b_leads":sum(x.tier=="B" for x in out),"cutoff_ambiguous_leads":sum(x.cutoff_ambiguous for x in out),"archive_url_duplicates":sum(x.archive_url_duplicate for x in out)}',
    'elapsed=[int(a.get("elapsed_ms",0) or 0) for r in reports for a in r.get("attempts",[]) if isinstance(a,dict)]\n    summary={"configured_sources":len(registry),"sources_ok":sum(r["status"]=="ok" for r in reports),"sources_unavailable":sum(r["status"]=="source_unavailable" for r in reports),"sources_parse_error":sum(r["status"]=="parse_error" for r in reports),"lead_count":len(out),"eligible_new_lead_count":sum(not x.cutoff_ambiguous and not x.archive_url_duplicate for x in out),"tier_a_leads":sum(x.tier=="A" for x in out),"tier_b_leads":sum(x.tier=="B" for x in out),"cutoff_ambiguous_leads":sum(x.cutoff_ambiguous for x in out),"archive_url_duplicates":sum(x.archive_url_duplicate for x in out),"fetch_elapsed_ms_total":sum(elapsed),"fetch_elapsed_ms_max":max(elapsed,default=0)}',
)
replace_once(
    sp,
    '_normalized_url=norm_url\nevent_fingerprint=event_fp',
    '_normalized_url=norm_url\n_safe_source_item_id=safe_source_item_id\nevent_fingerprint=event_fp',
)

replace_once(
    shadow,
    '        "matching_policy": "exact_url_then_conservative_title_date_event_fingerprint",\n',
    '        "matching_policy": "exact_url_then_conservative_title_date_event_fingerprint",\n        "matching_is_diagnostic_only": True,\n',
)
replace_once(
    shadow,
    '''        "fusion_summary": copy.deepcopy(fusion.get("summary")) if isinstance(fusion, dict) else None,\n        "error": report.get("error"),\n''',
    '''        "fusion_summary": copy.deepcopy(fusion.get("summary")) if isinstance(fusion, dict) else None,\n        "fusion_pre_hybrid_summary": copy.deepcopy(report.get("fusion_pre_hybrid", {}).get("summary")) if isinstance(report.get("fusion_pre_hybrid"), dict) else None,\n        "fusion_post_hybrid_summary": copy.deepcopy(report.get("fusion_post_hybrid", {}).get("summary")) if isinstance(report.get("fusion_post_hybrid"), dict) else None,\n        "error": report.get("error"),\n''',
)
replace_once(
    shadow,
    '''        archive = read_json(archive_path)\n        registry = source_pulse.load_registry(registry_path)\n        snapshot = collector_fn(\n''',
    '''        archive = read_json(archive_path)\n        registry_contract = read_json(registry_path)\n        if registry_contract.get("mode") != "production_shadow":\n            raise RuntimeError("Source Pulse registry mode must be production_shadow")\n        if registry_contract.get("production_integration") is not True:\n            raise RuntimeError("Source Pulse registry production_integration must be true")\n        if registry_contract.get("candidate_influence") is not False:\n            raise RuntimeError("Source Pulse shadow candidate_influence must remain false")\n        if registry_contract.get("repoll_on_recovery") is not False:\n            raise RuntimeError("Source Pulse shadow repoll_on_recovery must remain false")\n        registry = source_pulse.load_registry(registry_path)\n        snapshot = collector_fn(\n''',
)
replace_once(
    shadow,
    '''                "snapshot": snapshot,\n                "fusion": fusion,\n                "error": None,\n''',
    '''                "snapshot": snapshot,\n                "fusion": fusion,\n                "fusion_pre_hybrid": copy.deepcopy(fusion),\n                "error": None,\n''',
)
insert_marker = '''    _persist(\n        report,\n        artifact_dir=artifact_dir,\n        output_root=output_root,\n        publication_date=publication_date,\n    )\n    return report\n'''
insert_replacement = '''    _persist(\n        report,\n        artifact_dir=artifact_dir,\n        output_root=output_root,\n        publication_date=publication_date,\n    )\n    return report\n\n\ndef refresh_post_hybrid_fusion(\n    *, artifact_dir: Path, output_root: Path, publication_date: str,\n    research: dict[str, Any]\n) -> dict[str, Any] | None:\n    """Recompare the saved snapshot after Hybrid without repolling sources."""\n    report = _prior_report(artifact_dir, output_root, publication_date)\n    if not isinstance(report, dict) or not isinstance(report.get("snapshot"), dict):\n        return report\n    updated = copy.deepcopy(report)\n    updated["fusion_post_hybrid"] = build_fusion_diagnostics(updated["snapshot"], research)\n    _persist(updated, artifact_dir=artifact_dir, output_root=output_root, publication_date=publication_date)\n    return updated\n'''
# Replace only the final run_source_pulse_shadow return block, not helper returns.
idx = shadow.read_text(encoding="utf-8").rfind(insert_marker)
if idx < 0:
    raise SystemExit("source_pulse_shadow final persist marker not found")
text = shadow.read_text(encoding="utf-8")
shadow.write_text(text[:idx] + insert_replacement + text[idx+len(insert_marker):], encoding="utf-8")

replace_once(
    hybrid,
    'from source_pulse_shadow import compact_shadow_report, run_source_pulse_shadow',
    'from source_pulse_shadow import compact_shadow_report, refresh_post_hybrid_fusion, run_source_pulse_shadow',
)
replace_once(
    hybrid,
    '''    pulse_path = artifact_dir / "source-pulse.json"\n    if pulse_path.is_file():\n''',
    '''    pulse_path = artifact_dir / "source-pulse.json"\n    try:\n        fusion_research = read_json(artifact_dir / "candidates.json")\n        merged_path = report.get("merged_research_path")\n        if isinstance(merged_path, str) and Path(merged_path).is_file():\n            candidate_research = read_json(Path(merged_path))\n            if isinstance(candidate_research, dict):\n                fusion_research = candidate_research\n        if isinstance(fusion_research, dict):\n            refresh_post_hybrid_fusion(\n                artifact_dir=artifact_dir,\n                output_root=output_root,\n                publication_date=publication_date,\n                research=fusion_research,\n            )\n    except Exception:\n        pass\n    if pulse_path.is_file():\n''',
)

# Security regression: signed/tracking parameters must never persist in normalized lead URLs.
replace_once(
    tests,
    '''    def test_tracking_query_does_not_change_normalized_url(self):\n        a = sp._normalized_url("https://x.example/a?utm_source=z&k=1")\n        b = sp._normalized_url("https://x.example/a?k=1")\n        self.assertEqual(a, b)\n''',
    '''    def test_tracking_query_does_not_change_normalized_url(self):\n        a = sp._normalized_url("https://x.example/a?utm_source=z&k=1")\n        b = sp._normalized_url("https://x.example/a?k=1")\n        self.assertEqual(a, b)\n\n    def test_signed_credentials_are_stripped_from_persisted_url_identity(self):\n        value = sp._normalized_url(\n            "https://x.example/a?keep=1&token=secret&X-Amz-Signature=abc&credential=xyz"\n        )\n        self.assertEqual(value, "https://x.example/a?keep=1")\n        opaque = sp._safe_source_item_id("opaque-secret-provider-guid")\n        self.assertTrue(opaque.startswith("opaque-sha256:"))\n        self.assertNotIn("secret", opaque)\n''',
)

# Add post-Hybrid and runtime-contract tests before the architecture class.
replace_once(
    shadow_tests,
    '''\n\nclass SourcePulseShadowArchitectureTests(unittest.TestCase):\n''',
    '''\n\n    def test_invalid_shadow_contract_fails_open_without_polling(self):\n        payload = json.loads(self.registry.read_text(encoding="utf-8"))\n        payload["candidate_influence"] = True\n        self.registry.write_text(json.dumps(payload) + "\\n", encoding="utf-8")\n\n        def collector(**kwargs):\n            self.fail("collector must not run with invalid shadow contract")\n\n        result = shadow.run_source_pulse_shadow(\n            artifact_dir=self.artifact,\n            archive_path=self.archive,\n            publication_date="2026-08-25",\n            output_root=self.output,\n            registry_path=self.registry,\n            collector_fn=collector,\n        )\n        self.assertEqual(result["state"], "error_nonfatal")\n        self.assertIn("candidate_influence", result["error"])\n\n    def test_saved_snapshot_gets_post_hybrid_fusion_without_repoll(self):\n        pulse_lead = lead("x", "Current important event", "https://x.example/news/event", "2026-08-24")\n        calls = []\n\n        def collector(**kwargs):\n            calls.append(1)\n            return {\n                "version": 1, "snapshot_hash": "abc", "summary": {"lead_count": 1},\n                "leads": [pulse_lead], "sources": [], "paid_api_calls": 0,\n                "web_search_operations": 0,\n            }\n\n        first = shadow.run_source_pulse_shadow(\n            artifact_dir=self.artifact, archive_path=self.archive, publication_date="2026-08-25",\n            output_root=self.output, registry_path=self.registry, collector_fn=collector,\n        )\n        self.assertEqual(first["fusion_pre_hybrid"]["summary"]["pulse_only_count"], 1)\n        research = {\n            "candidates": [candidate("cand-001", "Current important event", "https://x.example/news/event", "2026-08-24")]\n        }\n        updated = shadow.refresh_post_hybrid_fusion(\n            artifact_dir=self.artifact, output_root=self.output, publication_date="2026-08-25", research=research\n        )\n        self.assertEqual(len(calls), 1)\n        self.assertEqual(updated["fusion_post_hybrid"]["summary"]["both_count"], 1)\n        self.assertEqual(updated["fusion_post_hybrid"]["summary"]["pulse_only_count"], 0)\n\n\nclass SourcePulseShadowArchitectureTests(unittest.TestCase):\n''',
)

replace_once(auto_readme, "### 4. Диагностика Hybrid\n", "### 5. Диагностика Hybrid\n")
replace_once(
    auto_readme,
    "source health и `pulse_only / both / search_only` diagnostics. Snapshot является\nчастью обычного Actions artifact.",
    "source health и pre-Hybrid `pulse_only / both / search_only` diagnostics; после\nHybrid тот же сохранённый snapshot без повторного polling сравнивается ещё раз и\nдаёт `fusion_post_hybrid`. Snapshot является частью обычного Actions artifact.",
)

replace_once(
    audit_md,
    "## Architecture verdict\n",
    "## Дополнительный hardening review\n\nПеред финальным CI stage 2 отдельно проверен на production-специфические seam risks. Найдены и исправлены:\n\n- **diagnostic secret hygiene:** Pulse URL normalization теперь удаляет token/signature/credential/API-key query parameters, а opaque source item IDs сохраняются только как hash;\n- **runtime config drift:** shadow wrapper сам fail-open проверяет `mode=production_shadow`, `candidate_influence=false` и `repoll_on_recovery=false`, а не полагается только на CI;\n- **pre-Hybrid overstatement:** один и тот же snapshot теперь сравнивается повторно после Hybrid без network repoll, поэтому аудит может отличать `pulse_only` до Hybrid от того, что Hybrid позже всё-таки восстановил;\n- **latency observability:** snapshot summary сохраняет суммарный и максимальный elapsed fetch time. Sequential collector остаётся bounded (10 s × 2 attempts per URL) и fail-open; реальную задержку надо отдельно измерять в ежедневном аудите первого live shadow sample.\n\nEvent-fingerprint matching намеренно остаётся консервативной diagnostic heuristic. `pulse_only` не является автоматически подтверждённым retrieval miss или Must Include; это обязан перепроверить независимый reference-set audit.\n\n## Architecture verdict\n",
)
