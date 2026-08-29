from pathlib import Path


def repl(path: str, old: str, new: str, *, count: int = 1) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    found = text.count(old)
    if found != count:
        raise SystemExit(f'{path}: expected {count} occurrences, got {found}: {old[:80]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')


p = 'automation/scripts/ensure_story_coverage.py'
repl(p, 'from typing import Any\n', 'from typing import Any\nfrom urllib.parse import urlparse\n')
repl(
    p,
    '})\n\n# Stable v8 transport still uses OpenAI(..., max_retries=2).',
    '})\nBOUNDED_UNVERIFIED_MIN_DISTINCT_HOSTS = 3\n\n# Stable v8 transport still uses OpenAI(..., max_retries=2).',
)
marker = 'def _latest_resolution_attempt(plan: dict[str, Any]) -> dict[str, Any] | None:\n'
helper = '''def _source_host(url: Any) -> str:\n    host = (urlparse(str(url or "")).hostname or "").casefold()\n    return host[4:] if host.startswith("www.") else host\n\n\ndef _bounded_unverified_signal_ids(\n    rejections: Any,\n    signals: list[dict[str, Any]],\n    *,\n    api: Any,\n    actual_queries: Any,\n    allowed_domains: Any,\n) -> set[str]:\n    """Close only a fully spent, evidence-rich unverified quality check."""\n    if allowed_domains or not isinstance(api, dict) or api.get("status") != "completed":\n        return set()\n    if int(api.get("web_search_calls_completed", 0) or 0) != 1:\n        return set()\n    if not isinstance(actual_queries, list) or len(actual_queries) != 1:\n        return set()\n    if not isinstance(rejections, list):\n        return set()\n    hosts_by_signal: dict[str, set[str]] = {\n        str(signal.get("signal_id") or ""): set()\n        for signal in signals if signal.get("signal_id")\n    }\n    for rejection in rejections:\n        if not isinstance(rejection, dict) or rejection.get("reason_code") != "unverified":\n            continue\n        host = _source_host(rejection.get("url"))\n        if not host:\n            continue\n        for signal in signals:\n            signal_id = str(signal.get("signal_id") or "")\n            if signal_id and _rejection_matches_signal(rejection, signal):\n                hosts_by_signal.setdefault(signal_id, set()).add(host)\n    return {\n        signal_id for signal_id, hosts in hosts_by_signal.items()\n        if len(hosts) >= BOUNDED_UNVERIFIED_MIN_DISTINCT_HOSTS\n    }\n\n\n'''
repl(p, marker, helper + marker)

# Reclassify both saved and fresh resolution attempts with the same strict evidence gate.
repl(
    p,
    '    terminal_ids = _terminal_negative_signal_ids(attempt.get("rejections"), cluster)\n'
    '    cluster_ids = {\n',
    '    terminal_ids = _terminal_negative_signal_ids(attempt.get("rejections"), cluster)\n'
    '    bounded_unverified_ids = _bounded_unverified_signal_ids(\n'
    '        attempt.get("rejections"), cluster, api=attempt.get("api"),\n'
    '        actual_queries=attempt.get("actual_queries"),\n'
    '        allowed_domains=attempt.get("allowed_domains"),\n'
    '    )\n'
    '    cluster_ids = {\n',
)
repl(
    p,
    '    negative_complete = bool(cluster_ids and cluster_ids.issubset(terminal_ids))\n',
    '    noncandidate_complete_ids = terminal_ids | bounded_unverified_ids\n'
    '    negative_complete = bool(\n'
    '        cluster_ids and cluster_ids.issubset(noncandidate_complete_ids)\n'
    '    )\n',
)
repl(
    p,
    '    elif complete and negative_complete:\n'
    '        reason = (\n'
    '            "resolution search conclusively rejected the signal under existing "\n'
    '            "freshness, deduplication, legal/fiction, or AI-relevance rules"\n'
    '        )\n'
    '    else:\n',
    '    elif complete and cluster_ids.issubset(terminal_ids):\n'
    '        reason = (\n'
    '            "resolution search conclusively rejected the signal under existing "\n'
    '            "freshness, deduplication, legal/fiction, or AI-relevance rules"\n'
    '        )\n'
    '    elif complete and cluster_ids.issubset(noncandidate_complete_ids):\n'
    '        reason = (\n'
    '            "bounded source-neutral resolution completed; at least three distinct "\n'
    '            "reporting hosts matched every required signal, but none provided "\n'
    '            "verified candidate evidence, so the event remains excluded"\n'
    '        )\n'
    '    else:\n',
)

repl(
    p,
    '    quality = prepared.get("retrieval_quality")\n'
    '    if (\n'
    '        prepared.get("retrieval_quality_contract_version") == RETRIEVAL_QUALITY_CONTRACT_VERSION\n',
    '    publication_date = str(prepared.get("publication_date") or "")\n'
    '    signals = _required_signals(publication_date) if publication_date else []\n'
    '    saved_attempt = _latest_resolution_attempt(prepared) if signals else None\n'
    '    if saved_attempt is not None:\n'
    '        recomputed = _quality_from_resolution_attempt(signals, saved_attempt)\n'
    '        if recomputed.get("status") == "complete":\n'
    '            prepared["retrieval_quality_contract_version"] = RETRIEVAL_QUALITY_CONTRACT_VERSION\n'
    '            prepared["retrieval_quality"] = recomputed\n'
    '            prepared["unresolved_resolution"] = copy.deepcopy(recomputed)\n'
    '            prepared["audit_status"] = "complete_with_gaps"\n'
    '            prepared["audit_state"] = "completed_usable"\n'
    '            prepared["audit_error"] = None\n'
    '            prepared["validation_error"] = None\n'
    '            prepared["error"] = None\n'
    '            prepared["status"] = "ok"\n'
    '            budget = prepared.get("search_budget")\n'
    '            if isinstance(budget, dict):\n'
    '                budget["stop_reason"] = "saved_quality_resolution_reclassified"\n'
    '    quality = prepared.get("retrieval_quality")\n'
    '    if (\n'
    '        prepared.get("retrieval_quality_contract_version") == RETRIEVAL_QUALITY_CONTRACT_VERSION\n',
)

needle = '''    terminal_negative_ids = _terminal_negative_signal_ids(\n        payload.get("rejections"), cluster\n    )\n    cluster_ids = {item for item in signal_ids if item}\n    negative_complete = bool(\n        cluster_ids and cluster_ids.issubset(terminal_negative_ids)\n    )\n'''
replacement = '''    terminal_negative_ids = _terminal_negative_signal_ids(\n        payload.get("rejections"), cluster\n    )\n    bounded_unverified_ids = _bounded_unverified_signal_ids(\n        payload.get("rejections"), cluster, api=metadata,\n        actual_queries=metadata.get("actual_queries"),\n        allowed_domains=UNRESOLVED_RESOLUTION_DOMAINS,\n    )\n    cluster_ids = {item for item in signal_ids if item}\n    noncandidate_complete_ids = terminal_negative_ids | bounded_unverified_ids\n    negative_complete = bool(\n        cluster_ids and cluster_ids.issubset(noncandidate_complete_ids)\n    )\n'''
repl(p, needle, replacement)
repl(
    p,
    '        "terminal_negative_signal_ids": sorted(terminal_negative_ids),\n',
    '        "terminal_negative_signal_ids": sorted(terminal_negative_ids),\n'
    '        "bounded_unverified_signal_ids": sorted(bounded_unverified_ids),\n',
)
repl(
    p,
    '            else ("terminal_negative" if negative_complete else "unresolved")\n',
    '            else (\n'
    '                "terminal_negative"\n'
    '                if cluster_ids and cluster_ids.issubset(terminal_negative_ids)\n'
    '                else ("bounded_unverified_exhausted" if negative_complete else "unresolved")\n'
    '            )\n',
)
repl(
    p,
    '                if complete and negative_complete\n'
    '                else "high-confidence unresolved evidence remains after the single resolution slot"\n',
    '                if complete and cluster_ids.issubset(terminal_negative_ids)\n'
    '                else (\n'
    '                    "bounded source-neutral resolution completed; at least three distinct "\n'
    '                    "reporting hosts matched every required signal, but none provided "\n'
    '                    "verified candidate evidence, so the event remains excluded"\n'
    '                    if complete and negative_complete\n'
    '                    else "high-confidence unresolved evidence remains after the single resolution slot"\n'
    '                )\n',
)
repl(
    p,
    '    plan["unresolved_resolution"] = copy.deepcopy(plan["retrieval_quality"])\n'
    '    if not complete:\n',
    '    plan["unresolved_resolution"] = copy.deepcopy(plan["retrieval_quality"])\n'
    '    budget = plan.get("search_budget")\n'
    '    if isinstance(budget, dict):\n'
    '        budget["stop_reason"] = (\n'
    '            "retrieval_quality_resolution_completed"\n'
    '            if complete else "retrieval_quality_resolution_unresolved"\n'
    '        )\n'
    '    if not complete:\n',
)
repl(
    p,
    '    prepared = _prepare_prior_for_quality(prior_plan, search_window)\n'
    '    # Let v8 finish/retry all mandatory directions first.',
    '    prepared = _prepare_prior_for_quality(prior_plan, search_window)\n'
    '    if completed_quality_audit(prepared):\n'
    '        return copy.deepcopy(prepared)\n'
    '    # Let v8 finish/retry all mandatory directions first.',
)

repl(
    'AGENTS.md',
    '## CI ownership boundary\n',
    '''## Incident/fix verification gate\n\nProduction incident fixes require evidence beyond a plausible diff or green CI.\nBefore merge, the agent must inspect the exact failing run/job and saved artifact;\nreproduce the failure offline from that artifact when possible; define and test\nneighboring success/failure/recovery cases; verify architecture, search-budget,\nsource-freshness, publication and at-most-once recovery invariants; inspect the\nfinal PR diff and CI on the exact head SHA; and verify the resulting `main` after\nmerge. A required check that remains `not verified` blocks a claim of full\nverification and blocks merge.\n\nFor paid production pipelines, independent regression work must use assistant-owned\nor saved artifacts and must not spend the owner's production API budget without\nseparate explicit permission. Recovery after a late-stage failure must prefer the\nalready-paid same-day artifact and prove that completed paid stages will not be\nrepeated. Merge must use the exact reviewed head SHA (`expected_head_sha` or an\nequivalent race-safe guard). Green CI by itself is never sufficient evidence.\n\n## CI ownership boundary\n''',
)

repl(
    'automation/ARCHITECTURE.md',
    'завершённый search с пустым publishable pool может завершиться успешным\n'
    '`editorial_stop` без искусственного наполнения выпуска.\n',
    'завершённый search с пустым publishable pool может завершиться успешным\n'
    '`editorial_stop` без искусственного наполнения выпуска.\n\n'
    'Retrieval Quality использует свободный седьмой slot для одного source-neutral\n'
    'resolution search по high-signal evidence. `unverified` не становится\n'
    '`verified` и не попадает в publication. Но завершённый resolution считается\n'
    '`bounded_unverified_exhausted`, если каждый required signal поддержан минимум\n'
    'тремя matching `unverified` rejection с трёх разных source hosts, search\n'
    'завершил ровно одну operation, сохранил ровно один query и не использовал\n'
    'domain filter. Один/два host, same-host repetition, unrelated evidence,\n'
    'multiple search operations или technical/API ambiguity остаются fail-closed.\n'
    'Same-day recovery детерминированно переиспользует такой сохранённый seventh\n'
    'slot без повторной Web Search operation.\n',
)
repl(
    'README.md',
    '`error` блокируют Image API, commit и deploy. Для короткого выпуска сохраняется\n'
    'пометка «Новостей сегодня меньше, чем обычно».\n',
    '`error` блокируют Image API, commit и deploy. Один evidence-rich source-neutral\n'
    'Retrieval Quality resolution может завершиться `complete_with_gaps`, если\n'
    'минимум три разных source hosts подтверждают наличие того же high-signal\n'
    'сообщения, но ни один не даёт verified evidence; такой сюжет остаётся\n'
    'исключённым, а thin/ambiguous evidence остаётся fail-closed. Для короткого\n'
    'выпуска сохраняется пометка «Новостей сегодня меньше, чем обычно».\n',
)
repl(
    'automation/README.md',
    '- `scripts/ensure_story_coverage.py` — fallback Coverage public entrypoint;\n',
    '- `scripts/ensure_story_coverage.py` — fallback Coverage public entrypoint;\n'
    '  evidence-rich unverified exhaustion может завершить bounded quality check\n'
    '  без публикации слуха и без повторного search при same-day recovery;\n',
)
