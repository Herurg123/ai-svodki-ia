# Independent release audit: 2026-09-02

## Scope

This audit reviews scheduled production run `33577674132`, the resulting full seven-story digest, and the retrieval architecture after the two Sep-1 P0 fixes.

Production research head: `7e144100775c2b933a561cacc6265d130d516717`.
Publication commit: `19e329c55d55b013586e331c36dc9afa4cb5137b` (`Publish AI digest for 2026-09-02`).
Actions artifact: `daily-production-2026-09-02`, artifact id `9827509780`, digest `sha256:08245c086fa58dc4a1d21bcb6e6a727c9412ffca279abdd91824950fd251c03f`.

Effective saved search window:

- start: `2026-08-31T04:49:39+03:00`;
- continuity anchor: `2026-09-01T04:49:39+03:00`;
- end/cutoff: `2026-09-02T04:01:28+03:00`.

No owner production API budget was used for this audit. Independent discovery used assistant-owned web-search resources plus the saved production artifact.

## Executive verdict

**Operational release: PASS. Freshness/editorial correctness: PASS. P0 fixes: PASS in production. Retrieval completeness: MATERIAL FAIL, but materially improved.**

The system produced and deployed a normal seven-story digest, consumed the intended normal maximum of 24 Web Search operations, and did not publish a stale or obviously invalid selected story in the audited set. Both Sep-1 P0 fixes worked in real production: Source Pulse no longer collapsed into parser recursion and contributed a published candidate; Agency Rescue correctly triggered and consumed its single Reuters slot when `major_agencies` was empty.

However, full story volume did not mean full discovery. Four independently verified Must-Include events inside the exact saved window were absent from all saved production retrieval traces. On the deliberately conservative bounded reference set of seven published eligible events plus four hard misses, demonstrated recall is `7 / 11 = 63.6%`. This improves on Sep-1's `4 / 8 = 50%`, but still represents material incompleteness.

The important architectural conclusion is therefore:

> **story volume and discovery health are different signals. A seven-story release can still be retrieval-degraded.**

## What production published

The final digest selected seven stories:

1. OpenAI Astra reached a critical cyber-capability threshold with restricted rollout.
2. OpenAI changed direct Cursor access arrangements.
3. ChatGPT Health integrated with Epic.
4. Anthropic announced Fable/Mythos 5.1 and Enterprise Frontier Safeguards.
5. Google introduced Pics in Workspace.
6. NVIDIA and CrowdStrike announced FAL.CON / SafeMind agentic cyber-defense work.
7. Russia proposed tax incentives for developers of sovereign/national AI models.

The final release is `short_digest=false`.

## P0 verification in real production

### Source Pulse v1.3 recursion fix: PASS

The saved Source Pulse report configured 13 fixed sources. Ten completed with source status `ok`; three were unavailable. No `RecursionError` occurred.

Source Pulse produced three window leads. The NVIDIA/CrowdStrike lead passed deterministic direct-page freshness and AI relevance, was promoted into the candidate pool, and became one of the seven published stories. The NVIDIA GeForce lead was correctly rejected because the direct page was outside the saved window. The Yandex lead was rejected because direct-page publication-date evidence could not be proved.

This is the intended safety behavior: Source Pulse now contributes real recall without bypassing the downstream freshness gate.

### Freshness-aware Agency Rescue: PASS

`major_agencies` finished Primary with `raw=0 / accepted=0`. Agency Rescue therefore triggered with reason `major_agencies_raw_zero`, reserved and executed exactly one Reuters-only search, and finished `completed_no_addition` with zero accepted candidates.

The new health bridge did not suppress the rescue. No second rescue search was attempted. At-most-once semantics and the existing budget ceiling held.

The rescue report did expose a remaining observability problem: the provider response contained one search action but no source metadata, so `source_metadata_available=false`. This does not prove a zero Reuters source pool; it means the publisher-route outcome is indeterminate at the source-pool level.

## Retrieval anatomy

### Primary Recall

All 12 mandatory searches completed. Final Primary candidate count was 8 before Source Pulse promotion.

Several completed directions returned zero raw candidates despite non-empty consulted-source pools:

- `major_agencies`;
- `models_products_agents`;
- `infrastructure_chips_cloud`;
- `business_investment_partnerships`;
- `china_asia_models`;
- `china_asia_integrations`;
- `security_safety`;
- `legal_regulation`.

A raw zero alone is not proof of degradation. It is recorded here because the independent reference set contains misses corresponding to multiple zero-raw lanes, while the saved provider source pools were not empty.

### Source Freshness

The merged Primary + Pulse pool contained 9 candidates before Source Freshness and 8 after it. No selected event was rejected as a stale event-origin. One Codex candidate was excluded because source publication freshness could not be proved.

The gate also demonstrated why source-specific recovery must stay conservative: one OpenAI first-party page returned HTTP 403, while an Anthropic first-party page returned HTTP 200 but no generic machine-readable publication date. Supporting fresh sources saved those particular candidates. Broad body-date scraping would weaken the existing fail-closed contract and is not justified by this audit.

### Hybrid

Hybrid used the normal 4/4 searches. Russia had a viable Search-derived survivor; China/Asia remained an unresolved Search-derived gap. The report correctly ended with `retrieval_health.status=complete_with_regional_gaps` and `unresolved_regional_gaps=["asia"]`.

The conditional fifth Hybrid search was not allowed because only one regional gap was open. This is correct under the current architecture.

### Coverage

Coverage consumed all 7 allowed operations. All six mandatory directions completed, and the seventh bounded Retrieval Quality resolution handled the Perplexity/NVIDIA signal. Retrieval Quality v1 ended `complete`; no new candidate was added.

Whole-pipeline paid search count therefore remained the ordinary ceiling:

```text
12 Primary + 1 Agency Rescue + 4 Hybrid + 7 Coverage = 24
```

No conditional 25th search was used.

## Independently verified hard misses

The following events are inside the saved window, significant enough for the main digest, and absent from the entire saved artifact, including raw retrieval traces. They are therefore classified as upstream discovery/ranking misses, not freshness or editorial rejections.

### 1. OpenAI ChatGPT Ads reaches $1B annualized revenue run rate

Official source:
`https://openai.com/index/expanding-access-to-ai-with-chatgpt-ads/`

OpenAI published the announcement on 31 August 2026. It states that ChatGPT Ads reached `$1B` in annualized revenue run rate in under 200 days and expanded self-service/global availability.

**Classification:** Must Include / business-product retrieval miss.

### 2. European Commission designates ChatGPT as a VLOSE under the DSA

Official source:
`https://digital-strategy.ec.europa.eu/en/news/commission-designates-chatgpt-reddit-roblox-under-digital-services-act`

The Commission published the designation on 31 August 2026. ChatGPT was designated a Very Large Online Search Engine under the Digital Services Act after declaring at least 45 million average monthly EU users, beginning a four-month period for additional obligations.

**Classification:** Must Include / legal-regulation retrieval miss.

### 3. Anthropic publishes alignment/security response after cyber-evaluation incidents

Official source:
`https://www.anthropic.com/news/improving-alignment-security-efforts`

Anthropic published the update on 31 August 2026. It describes containment and monitoring changes, resumption of cyber evaluations under new controls, broader internal hardening and the temporary reassignment of roughly 150 engineers to security/reliability/privacy work.

**Classification:** Must Include / security-safety retrieval miss.

### 4. Anthropic signs a $35B cloud-computing deal with Lambda

Reuters:
`https://www.reuters.com/technology/anthropic-signs-35-billion-cloud-deal-with-nvidia-backed-lambda-source-says-2026-08-31/`

Reuters reported a `$35B` cloud-computing agreement with Nvidia-backed Lambda for Texas AI infrastructure on 31 August 2026, within the production window.

**Classification:** Must Include / infrastructure-business retrieval miss.

## Bounded recall metric

Conservative denominator:

- 7 published eligible stories;
- 4 independently verified hard misses.

Demonstrated bounded eligible-event recall:

```text
7 / 11 = 63.6%
```

This is not an estimate of exhaustive global AI-news recall. It is a lower-bound diagnostic set containing only events strong enough to defend as eligible controls.

## Root-cause update after the P0 fixes

The Sep-1 structural defects are no longer sufficient to explain the remaining misses.

- Source Pulse is functioning and contributing candidates.
- Agency Rescue now triggers correctly.
- Freshness did not discard the four hard misses because none of them reached the candidate pool.
- Editorial did not discard them because none reached editorial.
- Hybrid and Coverage completed their allowed search budgets without finding them.

String-level inspection of the saved artifact found none of the four control URLs/events in the retrieved traces. The supported diagnosis is therefore **upstream retrieval/ranking/source-routing incompleteness**.

An assistant-owned wording check also cautions against a blanket query rewrite. Near-current production business/security wording can surface some of the repeated misses on an independent search surface, including the Anthropic/Lambda deal and Anthropic security update. A treatment business query that adds `revenue monetization ads earnings` improves the OpenAI Ads control, but wording alone does not explain why other current queries sometimes surface a control independently while production ranking misses it.

**Decision: NO-GO for a wholesale query-family rewrite in this audit PR.**

## Source Pulse inventory finding

The fixed Source Pulse registry currently has useful company/regional surfaces, but no OpenAI newsroom, Anthropic newsroom, European Commission digital-policy news, or broad global trusted-news surface.

Those three official indexes visibly expose dated entries for three of the four repeated misses, so expanding the zero-paid second discovery plane is a promising recall hedge. It is not merged blindly here because direct candidate promotion still requires the existing fail-closed page freshness proof. Production already demonstrated that OpenAI pages can return 403 and Anthropic pages can lack generic machine-readable publication dates. Any source-specific date repair must be narrow, tested and must not become generic body-date scraping.

## P1 implemented by this audit

### Volume-independent Discovery Health v1

The audit adds deterministic `discovery_health` diagnostics to the final production status.

It reads only already-saved reports from:

- Primary Recall;
- Source Pulse;
- Agency Rescue;
- Hybrid;
- Coverage / Retrieval Quality.

It performs **0 OpenAI calls and 0 Web Search operations** and does not change publication, editorial ranking, queries or budgets.

Health states are `healthy | degraded | indeterminate`.

Key policies:

- story count is never evidence that retrieval is healthy;
- explicit Source Pulse parser/source degradation is `degraded`;
- unresolved Hybrid regional retrieval gaps are `degraded`;
- an executed Agency Rescue with missing provider source metadata is `indeterminate`, not falsely healthy or falsely zero-source;
- Primary raw-zero lanes alone do not make the lane degraded;
- completed bounded Coverage can remain healthy even when its historical audit status is `complete_with_gaps`, provided mandatory directions are complete and current Retrieval Quality is complete;
- explicit degradation wins over indeterminate state at the overall level.

For the Sep-2 production-shaped replay, the expected health is:

```text
primary          healthy
source_pulse     degraded
major_agencies   indeterminate
hybrid           degraded
coverage         healthy
overall           degraded
```

This is deliberately publication-neutral in v1. It first makes the system tell the truth about discovery quality. A future publication/short-volume policy may consume this signal only after separate evidence and regression review.

## Deferred work

### P1/P2: improve zero-raw lane outcome diagnostics

Primary still collapses multiple possible outcomes into raw zero. A future diagnostic should distinguish at least:

- provider source pool empty/unavailable;
- provider sources present but no model candidate;
- model rejection;
- deterministic validator rejection;
- freshness rejection;
- editorial drop;
- viable survivor.

Today’s artifact proves this remains useful, but Discovery Health can be introduced without first rewriting every historical retrieval report.

### P2: controlled zero-paid source inventory expansion

Test OpenAI, Anthropic and European Commission official indexes against the real Source Pulse collector and direct-page freshness contract. Add only sources whose index parsing, host allowlist, page-date verification and recovery behavior can be proved without weakening generic freshness.

### P2: narrow query treatment only with source/ranking evidence

The `revenue monetization ads earnings` treatment is worth a controlled replay for the business lane. Do not rewrite all query families based on one day, because multiple repeated misses remain discoverable with near-current wording on independent search surfaces.

## Repository-change scope

This audit PR changes diagnostics, tests, documentation and dated audit evidence only. It does not:

- add a Web Search operation;
- add a model/API call;
- modify Primary/Agency/Hybrid/Coverage budgets;
- change queries or provider/domain routing;
- weaken Event/Source Freshness;
- change editorial selection or publication gating;
- repoll Source Pulse on recovery.
