# Independent release audit — 2026-09-01

## Scope and verdict

This audit reviews the published 2026-09-01 digest independently of the production research model. It uses the saved production artifact plus assistant-owned web search. No production OpenAI/API budget was spent for the audit or experiment.

The user-linked workflow run [`33461204146`](https://github.com/Herurg123/ai-svodki-ia/actions/runs/33461204146) was a later manual `workflow_dispatch` that correctly no-op'd after detecting that the digest had already been published. The actual scheduled generation was run [`33460195587`](https://github.com/Herurg123/ai-svodki-ia/actions/runs/33460195587). The publication commit is [`3ff9244f0cf7d534030a3a89d7e36fb72655557e`](https://github.com/Herurg123/ai-svodki-ia/commit/3ff9244f0cf7d534030a3a89d7e36fb72655557e).

Continuity window used for strict current-event auditing:

- previous publication anchor: `2026-08-31T04:22:46+03:00` (`2026-08-31T01:22:46Z`);
- current cutoff: `2026-09-01T04:49:39+03:00` (`2026-09-01T01:49:39Z`).

Overall verdict:

| Dimension | Result | Audit conclusion |
| --- | --- | --- |
| Publication / deploy | PASS | Scheduled generation, publication, Main CI and deploy completed successfully. |
| Idempotency | PASS | The later manual rerun safely skipped already-published work. |
| Source freshness | PASS | A stale AP Kimi result was rejected instead of being promoted as current news. |
| Archive dedupe | PASS | The Sony/Warner–Anthropic lawsuit was recognized as already covered and did not become a duplicate story. |
| Coverage fallback | PARTIAL PASS | Coverage recovered Apple and Instagram, but exhausted all seven allowed searches and still left major gaps. |
| Source diversity | WEAK | Three of four published stories ultimately relied on TechCrunch as the editorial support source. |
| Source Pulse | FAIL | `0/13` configured sources were healthy; ten ended in parser `RecursionError`, three were unavailable, and zero leads were accepted. |
| Completeness | FAIL | Four independently verified strict Must Include events were absent from the release. |

On a deliberately bounded reference set consisting of the four valid published stories plus the four independently verified strict misses below, demonstrated important-event coverage is **4/8 = 50%**. This is not a claim of exhaustive world recall; it is a conservative, evidence-backed lower-bound test set.

## Published stories: validity check

All four published stories are genuine current-window events and are editorially defensible:

1. **Nvidia / MediaTek — $3.5B investment and NVLink Fusion expansion.** Current, major AI-infrastructure event. Production used TechCrunch; Reuters and Nvidia also independently confirm the Aug. 31 announcement.
2. **Pentagon / GenAI.mil — Grok for Government and ChatGPT Mil.** Current government deployment. Production retained the official Department of War release as the story source, with TechCrunch used during freshness/support handling when the first-party page was difficult to fetch.
3. **Apple / OpenAI — new court allegations in the trade-secret dispute.** Current material court filing/development, recovered by Coverage after not surviving Primary.
4. **Instagram — reach limits for undisclosed AI-generated people/profiles.** Current platform-policy/product update, recovered by Coverage.

No published story failed the audit's event-freshness or archive-dedupe checks.

## Strict Must Include misses

### 1. Anthropic signs a $35B cloud-compute deal with Lambda

**Classification:** Must Include — business / infrastructure.

Reuters reported on Aug. 31 that Anthropic signed a roughly $35 billion cloud-computing agreement with Nvidia-backed Lambda for capacity tied to a Texas data center of roughly 350 MW.

Evidence:

- Reuters: <https://www.reuters.com/technology/anthropic-signs-35-billion-cloud-deal-with-nvidia-backed-lambda-source-says-2026-08-31/>

Why this is a hard miss: the magnitude is far above the normal threshold for an AI-infrastructure/business event, it is directly tied to frontier-model compute demand, and it occurred inside the strict continuity window. Primary `business_investment_partnerships` accepted zero candidates.

### 2. Anthropic resumes external cyber evaluations with new safeguards

**Classification:** Must Include — security / safety.

Anthropic published a new Aug. 31 material update describing safeguards adopted after earlier evaluation incidents and stating that external cyber evaluations had resumed. Reuters independently reported the same-day development.

Evidence:

- Anthropic, Aug. 31: <https://www.anthropic.com/news/improving-alignment-security-efforts>
- Reuters: <https://www.reuters.com/technology/anthropic-resume-external-testing-ai-models-following-security-incidents-2026-08-31/>

Production's mandatory `security_safety` Primary lane returned `raw=0`. The later world-security Coverage search did retrieve Anthropic's **older July 30 incident page**, but not this Aug. 31 material update. Therefore this audit does **not** label the miss as a proven candidate-formation failure. The stronger evidence is retrieval/ranking failure to surface the fresh update while surfacing a closely related stale page.

### 3. European Commission designates ChatGPT a VLOSE under the DSA

**Classification:** Must Include — regulation / policy.

On Aug. 31 the European Commission designated ChatGPT as a Very Large Online Search Engine under the Digital Services Act, with additional DSA obligations applying after the compliance period.

Evidence:

- European Commission: <https://digital-strategy.ec.europa.eu/en/news/commission-designates-chatgpt-reddit-roblox-under-digital-services-act>

This is a direct regulatory status change for a major AI product and is clearly inside the continuity window. Primary `legal_regulation` accepted zero current candidates.

### 4. FSB warns G20 that frontier-AI cyber risk is the most immediate AI concern for the financial system

**Classification:** Must Include — policy / security.

The Financial Stability Board published Andrew Bailey's Aug. 31 letter to G20 finance ministers and central-bank governors. It states that the most immediate financial-system concern from frontier AI is its impact on cyber risk and calls for resilience and safe, responsible release/deployment.

Evidence:

- FSB: <https://www.fsb.org/2026/08/fsb-chairs-letter-to-g20-finance-ministers-and-central-bank-governors-august-2026/>
- Reuters: <https://www.reuters.com/legal/litigation/ai-driven-cyber-risk-is-top-concern-global-financial-stability-watchdog-says-2026-08-31/>

The event spans policy and security, two areas in which Primary produced no accepted current candidate.

## Significant additional omissions below the strict denominator

These are important and plausible digest candidates, but the audit keeps them outside the conservative 4/8 denominator so that the hard-failure claim does not depend on borderline editorial judgments.

- **LUMI-AI:** EuroHPC signed a €387.8M contract with Bull for an AI-optimized supercomputer in Finland, using next-generation AMD Instinct MI430X GPUs. First-party: <https://www.eurohpc-ju.europa.eu/eurohpc-ju-signs-contract-deploy-lumi-ai-supercomputer-2026-08-31_en>. Reuters also covered it.
- **SLB / Kelvion:** Reuters reported SLB's $4.1B acquisition of data-center cooling company Kelvion, explicitly tied to expansion into the AI/data-center market.
- **Humain / DataVolt:** Reuters reported an agreement for an initial roughly 100 MW data-center phase in NEOM/Oxagon, another material regional AI-infrastructure buildout.

These reinforce the diagnosis that infrastructure/business recall was thinner than the four-story publication suggests.

## Failure anatomy

### Primary Recall was sparse exactly where the independent audit found misses

Saved artifact counts:

| Primary direction | Raw | Validated unique | Accepted |
| --- | ---: | ---: | ---: |
| `global_merge` | 2 | 1 | 1 |
| `major_agencies` | 1 | 1 | 1 |
| `models_products_research` | 0 | 0 | 0 |
| `infrastructure_chips_cloud` | 0 | 0 | 0 |
| `business_investment_partnerships` | 1 | 1 | 0 |
| `china_models` | 0 | 0 | 0 |
| `china_integrations_business` | 0 | 0 | 0 |
| `russia` | 0 | 0 | 0 |
| `developer_tools` | 0 | 0 | 0 |
| `security_safety` | 0 | 0 | 0 |
| `legal_regulation` | 1 | 1 | 0 |
| `independent_missing_events` | 2 | 1 | 1 |

The independent misses cluster in business/infrastructure, security and policy/legal, matching the weakest Primary lanes rather than appearing randomly across otherwise healthy retrieval.

### Agency rescue had a false-positive health signal

Primary `major_agencies` accepted one AP result about Kimi K3, so the pre-Hybrid agency rescue recorded `triggered=false`, `reason=not_needed`, `major_agencies_accepted_count=1`, and consumed zero of its one permitted search operation.

Later, source freshness correctly rejected that AP page because the actual source publication was July 20. The architecture therefore allowed a candidate that would later fail freshness to suppress the only Reuters/AP/Bloomberg/FT discovery-rescue opportunity.

This is a concrete stage-ordering defect: **pre-freshness agency acceptance is being used as the rescue health signal even when no fresh agency candidate survives.** It does not prove that the rescue query would have found every missed story, but it proves that the fallback was incorrectly prevented from trying.

### Source Pulse was operationally zero

The saved Source Pulse snapshot reports:

- `configured_sources = 13`
- `sources_ok = 0`
- `parse_error = 10`
- `source_unavailable = 3`
- `accepted_leads = 0`
- `paid_api_calls = 0`
- `web_search_operations = 0`

Ten sources failed with `RecursionError: maximum recursion depth exceeded`; Baidu IR and Xpeng IR timed out, while TASS returned 403 even after fallback. Thus the zero-paid second discovery plane contributed no recall on this release.

Code inspection shows that `source_pulse.py` recursively walks JSON-LD dict/list values without an explicit depth or node bound. That is a concrete parser-level risk consistent with the observed `RecursionError`, but the raw failing response bodies were not persisted in the artifact, so this audit does **not** claim that unbounded JSON-LD recursion is the proven sole root cause. It is the first code-level suspect to reproduce with fixtures.

### Coverage helped, but the search budget was fully exhausted

Mandatory Coverage used all seven allowed searches and recovered two publishable stories: Apple and Instagram. This is a real strength of the architecture: the digest did not stop at the sparse Primary set.

However, even after exhausting Coverage, the release remained at four stories and still missed the four strict events above. This means the remedy should not be "add more searches" by default. The existing slots need better health signals and better zero-raw recovery before raising the global budget ceiling.

### Late source visibility does not always imply a discoverable new candidate

A syndicated Reuters URL for the Anthropic–Lambda deal appeared in the source list of the final agency corroboration pass, but that pass was explicitly constrained to corroborating the already-selected Nvidia/MediaTek event. It was correctly not allowed to invent a different story.

This is not a bug by itself. It does show that result pools can contain high-value off-target events after the stage in which they can legally become candidates. Any future reuse of such signals must preserve stage contracts and the 24/25-operation search budget rather than silently turning corroboration into a second discovery plane.

### Source concentration remains high

Three of the four published stories used TechCrunch as their final editorial support source. The stories were valid, but the concentration is undesirable when first-party and agency reporting existed for some events. This is a quality/diversity warning, not a freshness failure.

### Apple exposed a stage-consistency issue

Apple's court development appeared in Primary material but did not survive the Primary path; Coverage later accepted it as publishable. The recovery is positive, but the disagreement is evidence that material-update validation is not fully stable across stages. It deserves instrumentation before policy changes are made.

## Russia and China/Asia checks

Independent checking did not verify a strict current-window Russia or China/Asia Must Include miss.

- A Russian AI law becoming effective on Sep. 1 traces back to a law adopted/signed in July. Treating a fresh effective-date page as a new Aug. 31 event would violate the project's event-freshness rule. It is better classified as a scheduled-boundary topic than a strict current-event miss.
- China/Asia searches surfaced several recent items, but the strongest candidates examined originated before the strict continuity window or did not clear the conservative Must Include bar.

This matters because the audit should not manufacture regional failures merely because those Primary lanes were empty.

## Independent A/B summary

A separate diagnostic experiment is recorded in [`automation/audits/experiments/2026-09-01-zero-raw-routing-ab.md`](experiments/2026-09-01-zero-raw-routing-ab.md).

Short version:

- A used the current generic production-style business, security, legal and infrastructure query families.
- B preserved the four slots but added the relevant Aug. 31 / Sep. 1 dates plus event verbs such as `announced`, `signed`, `resumed`, `designation`, `contract` and `award`.
- On the assistant-owned search surface, B recovered Anthropic–Lambda, the Anthropic security update, the EC/ChatGPT DSA designation and LUMI-AI more reliably than A.
- The result is **not** a causal production-provider A/B and B's calendar dates are less precise than the pipeline's timestamp continuity boundary.

Verdict: **NO-GO for blanket A→B replacement. GO for a bounded conditional experiment in already-budgeted slots when a mandatory lane is zero-raw or zero-current after freshness.**

## Recommended priorities

1. **P0 — make agency-rescue health freshness-aware.** Do not let a stale agency candidate suppress the one allowed rescue operation merely because it was accepted before source freshness ran. Preserve the one-operation rescue cap.
2. **P0 — repair and reproduce Source Pulse parser failures.** Add representative deeply nested/cyclic-looking JSON-LD fixtures, explicit traversal bounds, and clearer per-source parser diagnostics. Keep Source Pulse zero-paid and do not let it close Search-derived regional gaps.
3. **P1 — add zero-current-lane diagnostics.** Distinguish at least: no search result, only stale/duplicate related results, current source surfaced but candidate rejected, and current candidate accepted then removed later. Today's Anthropic case is specifically "related stale official result surfaced; fresh official update did not."
4. **P1 — test conditional date/event-verb rewriting inside existing search slots.** Do not globally replace the 12-query family, do not add a sixth Hybrid search, and do not raise the 24/25-operation ceiling without separate evidence.
5. **P2 — inspect stage consistency for material updates and source diversity.** Apple should not require a later stage to reverse an equivalent Primary judgment without an auditable reason.

## Change impact

This audit PR is documentation/evidence only. It intentionally changes no production workflow, prompt, search budget, freshness rule, dedupe rule, runtime code, `README.md`, `automation/README.md`, `AGENTS.md`, or `automation/ARCHITECTURE.md`.

The README and architecture entrypoints were reviewed for impact; because no runtime behavior or contract changes in this PR, no README update is required.
