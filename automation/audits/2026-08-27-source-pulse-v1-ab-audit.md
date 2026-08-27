# Independent audit: Source Pulse v1 production shadow and A/B test — 2026-08-27

## Executive verdict

**Architecture concept: PASS WITH CONDITIONS. Production implementation: FAIL for any promotion beyond shadow mode.**

Source Pulse v1 is correctly isolated as a zero-OpenAI, zero-Web-Search, fail-open shadow discovery plane between agency rescue and Hybrid. Those safety boundaries worked in the 2026-08-27 production run. However, the live collector was functionally blind: it completed with `status=complete`, 9 of 12 configured sources returned HTTP-successful payloads, yet the snapshot contained **0 leads** and both pre- and post-Hybrid fusion reported **0 Pulse hits / 8 Search-only candidates**.

Independent source checks on the same registered source families found multiple items inside the effective Pulse window. At least three were editorially strong regional/AI controls that Search missed or only partially captured: Alibaba's QwenWork International Edition launch, Alibaba's HK$80bn placement completion with explicit AI-infrastructure use of proceeds, and MWS Q2 results with +71% MWS AI external revenue plus Cotype 3 and AI-agent launches. IT之家 also carried the final GLM-5.3-Flash release/open-weight event, while Search had only the immediately preceding Ox Alpha attribution/release-announcement state.

The central defect is not the Source Pulse idea. It is the production adapters and source-health semantics: the generic HTML adapter does not reliably associate ordinary visible sibling dates with article links, so parsed links often receive no date and are then rejected by the window gate. Several registry endpoints also have availability or inventory problems. A second, lower-severity defect exists in fusion diagnostics: exact lexical title/date event fingerprints are fragile across Russian/English/Chinese paraphrases and can overstate `pulse_only` once leads begin flowing.

**Do not enable `candidate_influence=true` yet. Do not remove the second discovery plane. Repair and re-run it in shadow first.**

## Scope and evidence

Audit basis:

- repository: `Herurg123/ai-svodki-ia`;
- audited production release: `2026-08-27`;
- producing workflow run: `33037786098`;
- producing run base SHA: `367277279216d83349a66e6828654782e66fdefe`;
- published SHA: `78f4e8901542d382ebfa9707fbfeb61e8c5eed60`;
- production artifact: `daily-production-2026-08-27`, artifact id `9632829652`;
- Source Pulse snapshot hash: `d72b22b32ae7bd315912c2ed3bc825f184a4e57598f8001f8343d3d4fb56e5d0`;
- Pulse window: `2026-08-25T02:37:34+03:00` → `2026-08-27T06:55:27+03:00`;
- no user production API calls were made for this audit or A/B work.

The audit used the saved production artifact, current repository code/config/tests, deterministic local reproductions of the parser/fingerprint logic, and assistant-side independent web retrieval. Terra was **not available** in the audit environment; assistant web search/fetch was used instead. The production run itself used its normal configured retrieval stack; this audit did not rerun it.

This is an audit-only change. No production behavior, configuration, README, AGENTS, or architecture documentation is modified here.

## Architecture reviewed

Current order is:

1. Primary Recall;
2. conditional agency discovery rescue and its Source Freshness proof;
3. Source Pulse v1 production shadow;
4. Hybrid gap planning/search;
5. Coverage when required;
6. editorial/publication.

The shadow contract is intentionally conservative:

- `candidate_influence=false`;
- `repoll_on_recovery=false`;
- fixed HTTPS allowlist;
- Tier A official surfaces, Tier B lead-only regional surfaces;
- zero OpenAI calls;
- zero Web Search operations;
- Source Pulse failure is fail-open and does not mutate `candidates.json`;
- the saved snapshot is reused for post-Hybrid fusion and normal same-day recovery.

These architecture-level safety boundaries passed on 2026-08-27.

## Production observation: the shadow plane completed but discovered nothing

From the saved `source-pulse.json`:

- `status=complete`;
- `state=completed`;
- configured sources: 12;
- sources OK: 9;
- unavailable: 3;
- parser errors: 0;
- parsed source links existed on most successful sources;
- `lead_count=0`;
- `eligible_new_lead_count=0`;
- `tier_a_leads=0`;
- `tier_b_leads=0`;
- pre-Hybrid: Pulse 0, both 0, Search-only 8;
- post-Hybrid: Pulse 0, both 0, Search-only 8;
- total fetch elapsed time: 80,887 ms;
- maximum single-source attempt path: 20,429 ms.

Per-source result:

| Source | Production transport | Parsed | In-window | Leads | Independent observation |
|---|---:|---:|---:|---:|---|
| `baidu_ir` | timeout | 0 | 0 | 0 | current endpoint exposes Aug 26 items; availability path is unstable |
| `alibaba_ir_hkex` | HTTP 200 | 25 | 0 | 0 | current index visibly contains Aug 26 filings |
| `alibaba_cloud_blog` | HTTP 200 | 0 | 0 | 0 | current page visibly contains Aug 26 QwenWork and other posts |
| `marvell_current_reports` | HTTP 200 | 20 | 0 | 0 | no material in-window control found; latest visible 8-K is Aug 19 |
| `nvidia_recent_news` | HTTP 200 | 20 | 0 | 0 | current page visibly contains Aug 25 item |
| `yandex_ir` | HTTP 200 | 25 | 0 | 0 | registered index currently stops at Aug 24 despite a direct Aug 26 Yandex release |
| `xpeng_ir` | timeout on RSS + fallback | 0 | 0 | 0 | source family is relevant but live registry path was unavailable |
| `deepseek_official_news` | HTTP 200 | 25 | 0 | 0 | no independently established in-window official control in this audit |
| `mws_news` | HTTP 200 | 30 | 0 | 0 | current index visibly contains Aug 25 MWS results |
| `vk_press` | HTTP 200 | 25 | 0 | 0 | current index visibly contains Aug 25 releases, mostly non-AI noise controls |
| `ithome_ai` | HTTP 200 | 29 | 0 | 0 | Aug 26 GLM-5.3-Flash reporting exists on IT之家 |
| `cnews_ai` | HTTP 404 | 0 | 0 | 0 | configured `/news/line/` endpoint is dead; current CNews routes differ |

The zero-lead result is therefore not a quiet-source day.

## Root cause 1 — generic HTML date association is incompatible with real registry pages

The collector's HTML parser captures a date for a link only when:

- a JSON-LD article object provides `datePublished`; or
- a `<time datetime="...">` context is associated with the anchor.

A normal visible date in a sibling `<div>`, `<span>`, table cell, or inside the anchor's text is not parsed and associated with the item. `within()` rejects an HTML item that has neither `published_at` nor `published_date`.

A deterministic local reproduction using the current parser logic produced:

- `<a>Alibaba filing</a><div>August 26, 2026</div>` → link extracted, date `None`;
- `<a>25 августа 2026 г. MWS ...</a>` → link extracted, date `None`;
- `<a>NVIDIA article</a><div>August 25, 2026</div>` → link extracted, date `None`;
- `<time datetime="2026-08-26"><a>...</a></time>` → date parsed successfully.

This matches the production pattern: `alibaba_ir_hkex`, `mws_news`, `nvidia_recent_news`, `vk_press`, and `ithome_ai` all parsed many links but reported `window_items=0`.

Independent source controls make the failure concrete:

- Alibaba HKEX index visibly lists `COMPLETION OF PLACING OF NEW SHARES UNDER GENERAL MANDATE` dated August 26. The page itself states its data service is delayed by at least one hour, while the Pulse fetch happened many hours after August 26 began, so this is a strong parser/shape control rather than a near-cutoff propagation case.
- MWS news index visibly lists the August 25 Q2 results item. The item is well inside the two-day overlap, not a cutoff-edge case.
- NVIDIA Recent News visibly lists an August 25 article. Even though that particular article is not an editorial Must Include, it is a clean adapter/date control.
- VK press visibly lists August 25 releases. Their low AI relevance is useful as a noise control, but the collector should still be able to timestamp them before relevance triage.

**Severity: P0 for Source Pulse functionality.**

## Root cause 2 — one successful source returned zero parsed items despite visible current content

`alibaba_cloud_blog` returned HTTP 200 but `parsed_items=0`. Independent retrieval of the same registered page shows multiple article links and dates, including the August 26 QwenWork International Edition launch.

This indicates a live-payload/HTML-shape/adapter incompatibility distinct from the date-window problem. The allowlist intentionally permits subdomains of `alibabacloud.com`, so the observed zero cannot be explained simply by the public article living on `community.alibabacloud.com`. The exact raw production payload was not persisted, so this audit does not claim a narrower cause than the evidence supports.

**Severity: P0 for that registry source; add raw-shape fixture capture/redacted parser diagnostics before changing behavior.**

## Root cause 3 — source availability and registry health are weaker than `status=complete` suggests

Three of 12 configured sources were unavailable in the live snapshot:

- `baidu_ir`: timeout after retries;
- `xpeng_ir`: RSS timeout plus fallback timeout;
- `cnews_ai`: HTTP 404.

The CNews failure is deterministic registry drift, not transient network noise. Independent search finds current CNews news surfaces under routes such as `/news`, while configured `/news/line/` returns 404.

Baidu's public IR home currently exposes Aug 26 items, demonstrating that a timeout in one execution path is not equivalent to a dead source. XPeng remains a useful source family but needs more reliable endpoint/fallback handling.

`source_pulse_shadow.py` marks the whole collector `status=complete` whenever `run_source_pulse()` returns normally, even if all successful sources yield zero leads. Thus `complete` currently means orchestration completion, not useful discovery health.

**Severity: P0 observability defect for promotion decisions.** A future daily audit or operator could read `complete` as a healthy second discovery plane when it discovered literally nothing.

## Root cause 4 — current registry does not guarantee inventory coverage even when a direct official release exists

The registered Yandex source is the 2026 IR press-release index. That index currently tops out at August 24, but a direct official Yandex IR release dated August 26 exists: the federal teacher-AI training program for up to 250,000 teachers.

This means a parser fix alone does not close all regional blind spots. Some official indexes lag or omit direct releases, so source health must include inventory/recency checks, not just HTTP 200 and parsed-link counts.

**Severity: P1 architecture/source-registry coverage weakness.**

## Root cause 5 — fusion event fingerprints are too lexical for cross-language diagnostics

Fusion first matches exact normalized primary URL, then falls back to an `event_fingerprint(title, published_date)` built from normalized title tokens.

That is intentionally conservative, but it is brittle when Search returns a Russian editorial title and Pulse retains an English or Chinese source title. Independent deterministic checks with the current fingerprint logic show different fingerprints for semantically identical events such as:

- English `Z.ai reveals Ox Alpha as GLM-5.3-Flash native multimodal model` versus Russian `Z.ai раскрыта как разработчик open-weight модели Ox Alpha`;
- English `Amazon just tripled its order of Nvidia chips...` versus Russian `Amazon расширяет партнерство с Nvidia: еще 2 млн GPU для AWS`.

Once Pulse begins producing leads, such cases can be labeled `pulse_only` even though Search found the same event through another URL/language. This does **not** affect publication today because matching is diagnostic-only and `candidate_influence=false`.

**Severity: P1 diagnostic fidelity defect, not a current editorial safety defect.**

## Regression-suite gap

The current Source Pulse tests cover:

- RSS/Atom datetime parsing;
- JSON-LD HTML article parsing;
- malformed source handling;
- URL safety and credential stripping;
- cutoff ambiguity;
- source failure/fallback behavior;
- archive duplicate tagging;
- snapshot determinism/reuse;
- exact URL and exact lexical event-fingerprint fusion.

They do not cover the dominant live shapes observed in the registry:

- adjacent/sibling visible dates;
- dates embedded in anchor text;
- table/list rows where date and headline are separate siblings;
- current production snapshots in which an HTTP-200 source parses N links but 0 timestamps;
- cross-language/paraphrased same-event fusion.

That explains how the implementation could be CI-clean while the first real production shadow produced zero leads.

## A/B test design

The live shadow makes a clean same-run comparison possible because B did not mutate A.

### Arm A — Search stack

Actual production discovery without Pulse influence:

- Primary + agency rescue + Hybrid;
- Coverage was not needed because the eligible candidate pool was not short;
- 8 selection-eligible Search candidates reached fusion;
- final digest published 7 stories.

### Arm B-live — Source Pulse v1 as implemented

Same production run, same effective window:

- 12 fixed registry sources;
- 9 transport-successful sources;
- 0 leads;
- 0 overlaps;
- 0 incremental regional leads.

### Arm B-oracle — independent source-aware control

This is not a rewritten production implementation. It is an assistant-side audit control: inspect the same fixed-source families and ask whether an in-window event was visibly present and editorially material.

High-signal controls:

| Event | Search A | Pulse B-live | B-oracle/source-aware | Audit classification |
|---|---|---|---|---|
| Alibaba QwenWork International Edition, Aug 26 | miss | miss | hit | strong China/Asia Consider; fresh global AI-agent product launch |
| Alibaba completion of HK$80bn placement for compute + hyperscale AI data centers, Aug 26 | miss | miss | hit | material China/AI-infrastructure update; strong Consider |
| MWS Q2: MWS AI external revenue +71%, Cotype 3, agents in 10+ directions, Aug 25 | miss | miss | hit | strong Russia Consider; repeated regional retrieval control |
| Z.ai GLM-5.3-Flash final release/open weights, Aug 26 | partial | miss | hit | material update to Search's earlier Ox Alpha attribution candidate |
| Yandex federal teacher AI program, Aug 26 | miss | miss | registry miss | direct official release exists but registered index is stale/incomplete |

For this deliberately **targeted regional high-signal control set**, not a claim of exhaustive global recall:

- Search A: 1 partial/hit out of 5, with 4 misses;
- Pulse B-live: 0/5;
- source-aware B-oracle: 4/5;
- A ∪ corrected B-oracle: 4/5, with Yandex still missed because of registry inventory design.

The precise percentages are intentionally not presented as global recall. The set is a diagnostic regional/control sample built to measure the second plane where the existing architecture has known blind spots.

## Historical A/B context

The independent 2026-08-25 weekly Source Pulse v0 bake-off found:

- 9/13 strict miss-day recoveries (69.2%);
- 8/11 unique strict missed events recovered (72.7%);
- strong recoveries included Wan3.0, XPeng robotics financing and NVIDIA Groq 3 LPX.

The live 2026-08-27 result does not invalidate that architectural signal. It shows that the production v1 adapter layer failed to reproduce the source-aware prototype's discovery capability.

## What passed

The new architecture did several important things correctly:

1. **Isolation passed.** Pulse did not mutate Search candidates or editorial output.
2. **Cost boundary passed.** Pulse used 0 OpenAI calls and 0 Web Search operations.
3. **Failure containment passed.** Three source failures and the zero-lead collector did not break publication.
4. **Recovery contract passed by design.** Snapshot persistence/reuse prevents silent repoll of mutable sources.
5. **Security boundary passed in code review.** HTTPS allowlists, public-DNS checks, redirect guards, response-size caps, credential-query stripping and opaque-id hashing remain intact.
6. **Placement passed.** Pulse runs after agency rescue/freshness and before Hybrid gap planning, so it does not hide the mandatory `major_agencies` failure signal.

These are reasons to repair the mechanism rather than remove it.

## What failed

1. **Live discovery utility: FAIL.** Zero leads on a non-quiet registry window.
2. **Regional benefit: FAIL in production.** Zero Russia and zero China/Asia Pulse leads despite material controls.
3. **Source-health semantics: FAIL.** `status=complete` is too optimistic for zero-lead/partial-source operation.
4. **HTML adapter realism: FAIL.** Current production registry shapes are not represented by the regression suite.
5. **Registry resilience: FAIL/PARTIAL.** 25% of sources unavailable; one deterministic 404; at least one stale/incomplete official index.
6. **Fusion diagnostic robustness: PARTIAL.** Exact URL is safe; title/date fallback is not language-robust.

## Recommended next experiment, before any candidate influence

Run a bounded **Source Pulse v1.1 shadow repair experiment** with no production API budget increase and no editorial influence.

Required changes for the experiment:

1. Add source-specific or structurally bounded date extraction for real registry shapes instead of a single generic link parser. Prefer explicit per-source adapters/fixtures over broad heuristic scraping.
2. Persist enough non-sensitive parser diagnostics to distinguish `parsed link but no date`, `date found but outside window`, `filtered URL`, and `source page empty/dynamic`.
3. Replace or repair the dead CNews endpoint and re-evaluate XPeng/Baidu endpoint reliability.
4. Add source-recency/inventory health: an HTTP-200 index with many links but no parseable dates should not look healthy.
5. Add real captured/redacted fixtures for Alibaba IR, Alibaba Cloud blog, NVIDIA recent-news, MWS, VK, IT之家, Yandex and at least one failure/fallback source.
6. Add cross-language fusion regression controls. Keep semantic matching diagnostic-only until false-positive behavior is measured; do not introduce an LLM matcher silently.
7. Re-run shadow for multiple daily windows and measure:
   - valid lead extraction rate by source;
   - high-signal Pulse-only events;
   - true Search/Pulse overlap after human-independent normalization;
   - regional incremental recall;
   - noise rate;
   - source outage rate;
   - parser-drift rate;
   - latency.

Promotion criterion should require multiple live windows with nonzero, independently validated incremental recall and acceptable noise. A single fixed day is insufficient.

## Explicit non-recommendations

Do **not**:

- enable `candidate_influence=true` now;
- inject raw Tier B leads directly into editorial;
- add hard Russia/China publication quotas;
- weaken Source Freshness Proof or archive/semantic dedupe;
- increase the 24-search ceiling to compensate for Source Pulse defects;
- replace the second plane with another broad query wording tweak;
- treat `HTTP 200 + parser did not throw` as source health.

## Final decision

**KEEP the dual-discovery architecture, HOLD Source Pulse in shadow, FIX the adapters/health diagnostics, then repeat live A/B.**

The 2026-08-27 production evidence is strong enough to reject promotion of the current implementation, but it is also strong evidence that the second discovery plane is pointed at the right problem. Search again missed material China/Russia controls; the independent fixed-source inspection found them. The machinery simply failed to turn those visible source events into timestamped leads.

That is a repairable implementation failure, not evidence that the architecture should be abandoned.
