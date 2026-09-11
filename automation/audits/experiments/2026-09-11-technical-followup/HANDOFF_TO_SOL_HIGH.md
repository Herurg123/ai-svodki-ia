# HANDOFF TO SOL HIGH

## Status and scope

Prepared on 2026-09-11. This is the technical follow-up to audit PR #166, **not**
the previously numbered optimization plan. Runtime is unchanged. No production
API calls, paid searches, dispatch, publication, dependency installation or runtime
merge was performed by this follow-up. The companion probe executes saved inputs
and mocks transports locally; it demonstrates baseline defects, not a repaired
system. Ordinary assistant-side Terra reference checks are documented separately.

The owner explicitly authorized immediate merge **if a solution unequivocally
fixes the problem**. This overrides the attachment's older permission restriction;
do not ask again solely for merge permission. It does not waive incident gates,
exact-head CI, independent regression evidence or paid-operation restrictions.

The requested Astra stopping boundary has been reached: the remaining work is
implementation of the contracts below, negative tests, evidence capture and
controlled experiments. Stop Astra here. Start Sol High with this document and
its evidence directory; do not rerun the architectural investigation by default.
Empirical uncertainty is explicitly retained, especially P1 raw-feed provenance,
P2 provider behavior and P5 historical parser input. It is not permission to guess.

### Shared branch / commit / PR / CI record (applies to every P0–P5 below)

- Runtime baseline: `5d15b0f0a220f55a6753412b6e712fd2cd96b06a`.
- Baseline tree: `c93584810bdba4f11c95d9fb7d0ca0c30b0fd8da`.
- Audit branch: `audit/2026-09-11-technical-handoff`.
- Evidence commit: the commit containing this document; obtain the exact immutable
  SHA with `git log -1 --format=%H -- automation/audits/experiments/2026-09-11-technical-followup/HANDOFF_TO_SOL_HIGH.md`.
  The associated audit PR records the exact head and CI links. A document cannot
  embed its own content-dependent commit hash.
- Runtime branches / runtime PRs: **none created for P0–P5**.
- Runtime fix CI / acceptance: **not run; no fix exists**. Audit PR CI, even green,
  only checks that this inert evidence integrates with the unchanged baseline.
- Local verification completed: `probe_baseline.py` reproduced every result in
  `baseline-results.json` without network or a model call.
- All six tasks: changed only this audit/probe/evidence set; runtime code, prompts,
  configuration, workflows, release contents and budgets remain unchanged.
- Before implementation: fetch current main, compare intervening changes with the
  baseline, create one controlled branch per boundary below, and record its exact
  SHA/PR/CI in the implementation handoff. Do not silently inherit another fix.

## Independent verification: confirmed, corrected, additional

### Actions and saved evidence

Scheduled run [34549170782](https://github.com/Herurg123/ai-svodki-ia/actions/runs/34549170782),
job `103108275359`: pinned SDK install and full research/editorial succeeded;
Mandatory Coverage failed with `retrieval_quality_resolution_unresolved`; paid
artifact `10180407321` was uploaded.

Recovery run [34553236194](https://github.com/Herurg123/ai-svodki-ia/actions/runs/34553236194),
job `103120346361`: artifact restoration succeeded, SDK installation and full
research/editorial were skipped, Coverage nevertheless returned success, then
validation/build/publication completed. Deploy job `103120770521` also succeeded.
Final artifact: `10181609687`. Publication: `67ba38be203d72281b2e3873508ea7257b78c81f`.

The four saved research/editorial/digest/story files are byte-identical between
paid and final artifacts; SHA-256 values and artifact identities are in
`manifest.json`. This proves reuse in this incident, not universal at-most-once
safety for a later editorial repair. Both complete Coverage reports are preserved
here, with the final report's original hash in the manifest. Original ZIP hashes
are retained; ZIP binaries and unrelated rendered files are not duplicated.

Final Coverage says `status=ok`, `editorial_rerun_required=true`,
`editorial_rerun_performed=false`, one added candidate and
`existing_digest_after_editorial_repair_error`. The traceback is an import of
`openai` through `run_digest_preview.py` → `generate_digest_preview.py`.
The late candidate is the Kommersant Dutch-politician AI-post investigation
(`https://www.kommersant.ru/doc/8940954`); acceptance into the pool does **not**
prove the editor would select it.

### Corrections to the previous diagnosis

1. **P0 is wider than an SDK condition.** The fallback explicitly returns success
   after failed required repair. In the local counterexample it also rolls back
   an already-written simulated editorial response. A second restoration keeps
   the merged candidate, treats it as a duplicate, makes no editorial child call
   and changes `rerun_required` to false. The completed retrieval plan is injected
   from saved evidence; the actual merge, policy, rollback and restore code run.
   This is a bounded mechanism reproduction, not an end-to-end paid-stage test.
2. **P1 saved lead timestamps are normalized observations, not sufficient new
   publication proof.** The generic RSS parser accepts `updated` as publication
   time. Raw feed/date-field provenance and redirect history were not retained.
   Old normalized reports cannot safely be upgraded into trusted raw evidence.
3. **P2 provider routing failure is not established.** The actual request passes
   `allowed_domains=[reuters.com]` and requests `web_search_call.action.sources`.
   Local wire probes distinguish missing metadata from an explicit empty list.
   A model note saying no results is not an independently observed provider result.
4. Sep6, Sep7, Sep10 and Sep11 committed Agency reports show zero additions and
   unavailable source metadata. Sep8 has no committed report; Sep9 says
   `diagnostics_missing`. Neither missing case proves an executed zero-result call.
5. **P4 contains two weekday claims about two events.** Blindly comparing every
   weekday in a paragraph to one date would introduce false conflicts. The real
   candidate is fresh at Event Freshness in baseline despite the Thursday/Wednesday
   mismatch; the prior audit records later Source Freshness exclusion. No evidence
   here establishes a false-fresh published article from that candidate.
6. **P5 HTTP 200/zero parsed is an unproven parser result, not proof of its exact
   cause.** A simulated JS shell is incorrectly marked healthy by current code.
   Historical Qualcomm raw HTML is unavailable; JS rendering versus selector drift
   versus a legitimate empty/filtered response remains unestablished.
7. Terra verified event/source support for ten reference controls, but directly
   established strict UTC-window timestamps for only five. The other five have
   date-only support. The old 30% strict-recall statistic is therefore **not a
   re-certified metric**. One Reuters Senate link resolves to a related different
   event; the Axios control supports the intended event. See `terra-reference.md`.

## Dependency map and implementation order

Current path:

- Workflow restoration chooses SDK/API readiness from recovered story/image state.
- Coverage may still extend the pool and invoke editorial after that choice.
- Editorial invokes the generator, paid transport, parsing and validation.
- Coverage rollback restores a directory; recovery independently restores merged
  research and a saved Coverage report. No durable repair obligation binds them.
- Source Pulse parses feeds/pages → supplement promotes leads → research ingress
  → Event/Source Freshness → archive/dedupe → editor → publication.
- Agency and Primary rejected-signal queues feed bounded Coverage resolution;
  source identity, event identity and publication time are separate gates.
- Source Pulse health/value diagnostics consume earlier stage counts; missing
  parser/lineage evidence must not become a zero or proof of publication.

| Task | Architecture / regression risk | Contract now | Sol scope | Remaining uncertainty |
|---|---|---|---|---|
| P0 | High / high: workflow, paid transport, rollback, recovery | Specified below | First runtime PR, durable completion + dependency wiring | Interrupt/response replay tests not implemented |
| P1 | High / high: two freshness gates, provenance, redirects | Narrow trusted-feed contract | Separate evidence-capture/resolver PR | Historical raw feed unavailable; positive transport evidence still needed |
| P2 | Medium / medium: provider boundary and cached searches | Diagnostic axes + fixed budget | Diagnostics PR, then evaluation report | Actual provider cause and treatment benefit unknown |
| P3 | High / high: event identity and shared seventh slot | Conservative queue + exact binding | Queue preservation first; upgrade separately | No proved retrieval uplift; unavailable slot stays deferred |
| P4 | Medium / medium: multi-event text and local dates | Deterministic scoped claims | Helper + optional schema/legacy boundary tests | Ambiguous text must stay unknown |
| P5 | Medium / medium: transport/parser/filter separation | Stage health semantics | Diagnostics first, parser only with captured input | Exact Qualcomm parser repair and NSA route unknown |

No further Astra-level choice is currently necessary to start these bounded units.
Escalate only if an implementation counterexample invalidates an invariant; do not
expand scope or buy API evidence to avoid reporting an unknown. P0 first; P1 needs
P0 recovery preservation if evidence crosses a repair. P3 upgrades need existing
Freshness (and optionally P1), and must not bypass either. P4/P5 diagnostics can
be developed independently. Keep their runtime PRs separate.

## Global invariants and verification commands

Read `AGENTS.md`, `automation/ARCHITECTURE.md`, both maintained READMEs, project
DOCX and `automation/specs/search-change-validation-matrix.md` before runtime work.
Update affected architecture, README and documentation-contract tests with each
changed behavior. This audit alone changes no active contract or entry point.

Preserve Primary 12, Agency <=1, Hybrid 4 or conditional 5, Coverage <=7 and total
24/25. No new regional/publisher quotas, no forced inclusion, no ranking rewrite,
no extra live search on recovery, no publication based on weak/ambiguous evidence.
Do not merge deferred optimization point 4 to implement this follow-up.

Reproduce the baseline in a checkout containing this evidence and the baseline
commit (the probe imports runtime from `--repo`; changing it is intentional A/B):

```bash
python automation/audits/experiments/2026-09-11-technical-followup/probe_baseline.py --repo . --output /tmp/sep11-baseline.json
```

Expected baseline defects are listed in `baseline-results.json`. Do not modify
expected failure output to pretend it is fix acceptance. Write real regression
assertions for the repaired behavior, with strict fake transports that fail on any
unplanned call. Run the targeted existing tests named in each task using:

```bash
python -m unittest discover -s automation/tests -p 'test_recovery*.py' -v
python -m unittest discover -s automation/tests -p 'test_source_pulse*.py' -v
python -m unittest discover -s automation/tests -p 'test_agency*.py' -v
python -m unittest discover -s automation/tests -p 'test_event_freshness.py' -v
```

Use corresponding patterns for new tests and Primary/Coverage/publication adapters.
For final runtime acceptance, execute exactly the Main CI commands from
`.github/workflows/ci.yml`: compile, full unittest discovery, editorial contract,
archive, production contract, Dzen feed, sitemap and structured-data validators.
Do not dispatch production. Verify `Required PR Gate` on the exact final head,
inspect the final diff, merge with an expected-head guard only after all incident
criteria pass, then verify post-merge Main CI. Green tests alone are insufficient
for retrieval claims. Record baseline/treatment, negative results and missing data.

## P0 — durable editorial completion on recovery

**Problem/root cause.** SDK setup is gated by recovered full-story/text readiness,
while Coverage can add a candidate later. `ensure_story_coverage_policy.py` returns
success after failed repair when the old digest was publishable. Its rerun decision
is based on newly added items rather than a persistent obligation. Restored merged
research therefore makes the same candidate a duplicate and can erase that decision.
Rollback also discards response evidence in the snapshot directory.

**Files.** `.github/workflows/daily-production.yml` (restore outputs around 410–468,
SDK around 469, full research around 526, Coverage around 548);
`automation/scripts/ensure_story_coverage_policy.py` (`main`, snapshot/restore,
`rerun_editorial`, error/empty fallback branches around 2005–2016);
`recover_digest_artifact.py`, `recover_digest_artifact_v1_base.py`
(`restore_merged_coverage_research`, `restore_prior_coverage_audit`, `recover`);
`run_digest_preview.py`; `generate_digest_preview.py` (SDK import, client retries,
editorial call/write/parse/validate); tests and recovery docs. `usage_observer.py`
is diagnostic-only and fail-open: it is **not** a durable replay journal.

**Already changed:** no runtime changes; the actual rollback/duplicate counterexample
and both reports are saved here. Shared branch/SHA/PR/CI record above applies.

**Implement next, as one coherent correctness boundary:**

1. Install pinned `openai==2.45.0` for every nonterminal path able to invoke editorial
   completion. Installing dependencies does not authorize a paid call. Retain the
   full-research reuse skip. Validate text API configuration when repair is admitted,
   including recovery where an image is already present.
2. Persist an editorial-repair obligation **before** invoking the child, separately
   from completed Coverage search state. Bind it to release/window, selected artifact
   identity, post-Freshness candidate-pool hash, archive, model/prompt/schema contract.
   Do not select independently the first same-date report and research file from
   different extracted artifact roots.
3. Use explicit states, for example `required -> prepared -> request_started ->
   response_saved -> validated`. `failed_before_request` can retry safely;
   `unknown_after_request` blocks automatic repeat. `response_saved` replays parse/
   validation offline; `validated` reuses output. Missing or changed inputs must not
   create a second intent while an earlier request might have run.
4. Persist state atomically outside the rollback directory, under a production daily
   location always included in failed-run artifacts. Save the raw editorial response
   before parsing. Fail before transport if mandatory persistence fails. Restore the
   journal and response on recovery with identity/hash checks; preserve them on error.
5. Provide a dedicated editorial-completion path using saved research only. Ensure
   provisional/Hybrid/rescue helpers cannot introduce paid work. For this protected
   transport disable automatic ambiguous SDK retries (scope to repair; do not globally
   change search clients). A connection loss after request admission is unknown,
   never evidence of zero billing. Clearly distinguish logical-stage from wire-level
   at-most-once; a provider crash cannot be solved by guessing whether it charged.
6. Neither seven old stories, zero new additions after dedupe nor old valid content
   clears a pending repair. Failed required completion is a nonzero terminal result;
   old files may remain for forensics but publication is blocked. Apply to the error
   and empty-rerun fallbacks. A completed retrieval plan retains its true state even
   when no new search runs; fix the saved `not_started`/remaining-zero inconsistency.
7. Legacy artifacts lacking a journal require explicit compatibility handling. A saved
   required/not-performed flag is a pending obligation. Only a proven pre-request
   failure (such as this exact SDK import traceback) permits safe admission; ambiguous
   historical failures block auto-repeat. Document removal conditions for compatibility.

**Do not change:** paid Primary/editorial reuse, search slots, initial legitimate
no-candidate/no-repair behavior, independent freshness/archive checks, image reuse,
publication validators, usage observer's diagnostic contract.

**Fixtures/tests:** use both saved Coverage reports and baseline committed Sep11
research/editorial/digest/stories; reduce fixtures only with documented transforms.
Expand `test_recovery_completed_audit.py`, `test_story_coverage.py`,
`test_zero_research_recovery.py`, `test_image_complete_recovery.py` plus a dedicated
repair-journal suite. Required cases: (a) no new candidate/no pending obligation,
(b) one new candidate, (c) repair success, (d) failure before request, (e) old valid
seven-story digest plus pending repair, (f) completed original paid stages reused.
Also test response saved then validation fails; crash before/after each journal
transition; write failure; SDK missing with image present; unknown transport result;
legacy missing state; mixed artifact roots; changed pool/prompt; deduped new item
on second recovery; empty editor response. Strict call counters must prove zero
fresh-research calls, zero extra search calls, no second repair transport after
`request_started`, and offline replay after `response_saved`.

**Commands/expected result:** targeted recovery, story coverage and new repair tests,
then all shared final gates. Baseline reproduces success-on-failure; treatment blocks
publication until the same obligation validates, preserves the response and never
rebuys an ambiguous/completed stage. A repair failure can legitimately remain blocked.

**Not verified/completion:** journal, child isolation, interruption matrix and exact
workflow environment behavior are unimplemented. P0 is complete only after all six
requested cases plus interruption/recovery negatives pass independently on the exact
PR head. SDK installation alone is not P0 completion. No runtime PR to merge yet.

## P1 — narrow official feed publication evidence

**Problem/root cause.** OpenAI feeds discover exact articles but promotion fetches the
page before producing a candidate; 403 excludes it. The later freshness resolver also
runs only after successful fetch lacking a date. Fixing that resolver alone cannot
recover the earlier loss. Normalized Pulse leads lose date-field and redirect proof.

**Files:** `source_pulse.py` (`ParsedItem`, `PulseLead`, `parse_rss`),
`source_pulse_supplement_v12.py` (promotion/fetch), v13 overlay,
`source_freshness.py`, `source_freshness_v1.py`, `publication_evidence_adapters.py`,
shared fetch transport, research ingress allowlists, recovery artifact copying and
Source Pulse/value diagnostics. Add a shared trusted-evidence module rather than
replicating validation in promotion and Freshness. Paths are under automation/scripts.

**Already changed:** no runtime changes; `updated_only_feed` baseline probe proves
why old normalized timestamps are insufficient. Shared revision/status applies.

**Implement next:**

1. At collection, preserve bounded raw feed/item bytes, raw link/GUID, publication
   field name and value, description, feed requested/effective URL, HTTP status,
   redirect chain, collection/run/window identity and registry version. Hash the
   raw capture and bind it to the selected artifact; a hash alone is not authenticity.
2. Initially allow only the preconfigured OpenAI feed and exact `openai.com` article
   host/path contract. Accept RSS pubDate or Atom published with aware time, never
   updated/dateModified or dates guessed from GUID. Validate conflicting duplicate
   items before dedupe, filtering or truncation. No blanket trust of arbitrary RSS.
3. Exact URL association only. Reject userinfo, unexpected ports, lookalike/subdomain
   hosts, encoded/query/fragment aliases or canonical mismatches without an explicitly
   proven equivalence. A feed URL is an exact link claim, not proof of an unseen
   page canonical. If page canonical/redirect evidence exists it must agree.
4. Use a bounded no-redirect transport for the P1 feed/article path; direct 403 at
   the exact requested article may use trusted feed publication evidence. Any redirect
   or unknown redirect history blocks fallback. Keep generic other-host fetching
   unchanged. Existing successful page publication evidence remains authoritative;
   conflicts must be rejected, not overwritten by whichever date passes the window.
5. Both promotion and Source Freshness call the same resolver against trusted captured
   evidence, never model-supplied proof. Preserve raw capture/proof through ingress,
   Freshness and recovery; do not repoll the feed on recovery.
6. Feed proof establishes publication time, not article accessibility, factual detail
   or event age. Keep 403 transport diagnostics. Construct candidate facts only from
   adequate captured title/description; title-only insufficient leads remain leads.
   Apply Event Freshness, archive, dedupe, source selection and candidate cap normally.
   Do not revive an excluded stale event or another material's candidate.

**Do not change:** global unknown/fail-closed behavior, arbitrary publisher trust,
search count, event-age requirement, editor ranking. No fuzzy company matching.

**Fixtures:** exact Pulse URLs for Financial Services `/index/introducing-chatgpt-financial-services`,
GSA `/index/expanding-ai-access-us-government`, Data `/index/put-data-to-work`,
antimicrobial `/index/using-codex-chatgpt-to-search-for-new-antimicrobials`.
Sep11 normalized Pulse records 07:00Z for Finance/GSA, 15:00Z Data, 16:00Z
antimicrobial on Sep10. Three unique leads failed 403; antimicrobial was already
found by both paths, so not unique uplift. These are historical observations,
**not** byte-preserved raw RSS. Neither ZIP contains raw source RSS/newsroom input.
Constructed XML using these pairs is a labeled contract fixture only; historical
positive proof requires an original raw capture. New captures must be labeled with
their real collection date and cannot retroactively authenticate Sep11.

**Tests:** shared resolver and both end-to-end gates; exact positive 403 + trusted
capture; normal 200; stale item/event; conflicting pubDates; duplicate conflicts
outside truncation; updated-only; missing description; redirects; missing redirect
history; canonical mismatch; spoofed host; similar different URL; old same-company
article; byte/hash mismatch; candidate-injected proof; wrong run/window; cold recovery.
Expand `test_publication_evidence_adapters.py`, Pulse supplement/research-boundary
and Source Freshness tests. Run shared commands + search-change matrix.

**Expected result/completion:** valid trusted exact evidence can support publication
freshness through both gates while all negatives remain excluded/unknown. No extra
paid operation or stale inclusion. Capture authenticity, dual-gate integration and
historical positive evidence are unverified. A synthetic happy path alone cannot
justify claiming the Sep11 leads now work in production. Separate this runtime PR.

## P2 — Agency observability before query/routing changes

**Problem/root cause:** merge result `completed_no_addition` does not identify provider
failure, model rejection or healthy zero. Current evidence is insufficient to assign
an internal provider cause; metadata extraction/request filtering work in local probes.

**Files:** active `agency_discovery_rescue.py` versioned v5/v4/v3 chain, transport
request and source metadata extraction, Agency recovery state, diagnostics consumers,
`test_agency_discovery_rescue.py`, `test_agency_discovery_recovery.py`,
`test_agency_health_viability.py`, `test_agency_rescue_target_propagation.py`.

**Already changed:** no runtime changes. Saved historical comparison and SDK-shaped
wire probe are in baseline results. The fixed request is `latest AI models research
chips infrastructure financing earnings business deals policy security`, with Reuters
filter, metadata include and max_tool_calls=4 (one search plus navigation allowance).

**Implement next:** add independent diagnostic fields for request contract, transport
completion, response parse/schema, source metadata absent/null/empty/nonempty/malformed,
model candidate/rejection counts, host/schema/window rejection, dedupe/cap and actual
addition. Unknown is null/unknown, never inferred zero. Keep existing merge-state
compatibility; `validated_count` is currently measured before actual merge validation,
so add a correctly named post-validation count rather than silently changing consumers.
Persist a bounded redacted request + raw response before parsing, without secrets.
Instrumentation must not reserve a new slot, change request parameters or retry.
Reused `search_completed`/merge-failed output is consumed offline; `search_started`
continues to reserve the sole operation.

**Do not change:** Reuters slot ceiling, routing/default query until measured,
Freshness, publisher quotas, fallback call count, completed paid-stage reuse.

**Fixtures/tests:** Sep6–Sep11 matrix, explicitly retaining Sep8 missing report and
Sep9 diagnostics_missing; recover original Actions artifacts if available via read-only
access. Simulate request failure, malformed output, missing/empty metadata, actual
sources with zero candidates, wrong host, stale/deduped/capped candidates, interruption
and replay. Prove no second wire call in diagnostics/recovery paths.

**Commands/expected result:** Agency targeted suites then shared final gates.
Diagnoses become distinguishable without pretending the provider's hidden reason is
known. A fixed-budget historical A/B must compare baseline/treatment at equal slots,
raw metadata availability, verified unique additions, stale/false positives, rejection
causes and cost counters. Retain all failures; no cherry-picked single-day success.
Old response fixtures permit transformation replay, not alternative retrieval output.

**Not verified/completion:** production-equivalent query A/B Sep6–Sep11 has not run.
Assistant Terra reference search is not that experiment. No owner API spend is
authorized; use an actually compatible assistant-owned tool if available, otherwise
record the evaluation as blocked on empirical evidence. Sol can finish diagnostics
and the offline harness now. Query/routing repair is not complete or mergeable until
an eligible fixed-budget experiment demonstrates benefit without regression.

## P3 — weak-source signal retention and exact authoritative binding

**Problem/root cause:** Primary retains the DeepSeek weak_source rejection but
`collect_unresolved_signals` selects unverified signals, so no resolution signal is
produced. Existing company/token overlap is insufficient proof of event identity.
The seventh Coverage slot may already have a required resolution obligation.

**Files:** `primary_recall_search.py` signal extraction, `ensure_story_coverage.py`
(`resolution_cluster`, `build_resolution_query`, `_eligible_resolution_candidate`,
negative closure functions, `_run_resolution`), Coverage policy/plan recovery and
source verification. Read but do not merge the deferred optimization point4 branch.

**Already changed:** none in runtime; real DeepSeek rejection and empty emitted
signal list are preserved by the baseline probe. Shared revision/status applies.

**Implement next in two boundaries:** first retain qualified weak-source product
signals with source/reason provenance and explicit organization, product/model version
and lifecycle/action anchors. This queue alone does not make a candidate eligible.
Then admit authoritative resolution only within existing navigation allowance from
an exact surfaced official link, or the existing optional seventh search when free
and with no higher-priority required obligation. Keep the mandatory six and current
required resolution priority. No slot available means `deferred_capacity`, not closed.
Exact event binding requires meaningful product/version/action equality, retaining
numeric/version tokens. Preview, general availability and a new model are distinct;
no invented aliases or company-only/fuzzy acceptance. Ambiguous signals stay unresolved.
An independently valid candidate may enter the ordinary pool without closing an
unmatched signal. Authoritative URL/date/event/archive gates remain mandatory.

**Do not change:** weak-source publication exclusion, search ceiling or occupied slot
replay, forced regional inclusion, freshness, archive duplication and mandatory routes.

**Fixtures/tests:** saved DeepSeek weak rejection plus exact official identity (Terra
reference report); same company/different event; old release; similar version name;
preview versus GA; duplicate announcement; false identity alias; no source proof;
occupied seventh slot; order permutations; interrupted/restored spent slot. Queue
positive is not a retrieval positive. Expand Primary signal and Coverage search/
query/recovery tests, then shared gates and search-change matrix.

**Expected result/completion:** qualified awareness survives with truthful unresolved
state; exact verified new evidence can close only its own event in the existing
budget. No guaranteed DeepSeek recovery is claimed for Sep11 because its seventh slot
was already used. Queue preservation is independently finishable; automated upgrade
requires identity negatives and fixed-budget acceptance. Retrieval uplift remains
unverified. Shared runtime branch/PR/CI: none until Sol creates the separate PR.

## P4 — scoped calendar consistency

**Problem/root cause:** a saved candidate sets event_date=2026-09-10 while describing
the relevant reaction as Wednesday. Baseline calendar says Thursday, but Event
Freshness returns fresh. Evidence also mentions a different Tuesday advisory, so a
paragraph-wide weekday regex would be unsafe.

**Files:** `event_freshness.py` evaluation, date normalization/candidate evidence
schema and ingress field allowlists if adding optional structured claims;
`test_event_freshness.py`, Primary temporal boundary tests, Source Freshness integration.

**Already changed:** none; real candidate-derived calendar conflict reproduced.

**Implement next:** pure deterministic helper taking an explicitly bound claim
(event versus publication, date, weekday, timezone/offset). Compare weekday in the
claimed local calendar before UTC conversion. Missing weekday is not a conflict;
weekday-only cannot invent a date. Conflicting explicit claims cannot establish
Event Freshness. Legacy multi-event/ambiguous text yields unknown consistency, not
an automatic day correction; use optional structured fields or a narrowly safe
legacy parser with an ambiguity result. Do not require new fields for all saved
artifacts. Machine publication evidence remains independent; LLM weekday text must
not overwrite authoritative page time or turn page freshness into event freshness.

**Do not change:** window boundaries, healing overlap, source date authority, automatic
plus/minus-day correction, paid query counts. Never compare unrelated weekdays.

**Fixtures/tests:** actual China/AP evidence; weekday-only; explicit correct/conflicting
weekday; UTC/local day boundary; month/year rollover; unknown zone; daylight-saving
boundary where applicable; two events/two weekdays; negated weekday; old artifact
without new fields; clean unrelated candidate. Run event and Primary temporal suites,
then shared gates. Expected conflict/ambiguous event claims cannot independently
produce fresh, while correct local claims retain their date.

**Not verified/completion:** helper/schema integration is unimplemented. Complete when
scoped positive/negative/legacy tests and independent Freshness interactions pass;
no runtime PR or CI exists yet. No further Astra reasoning needed for this contract.

## P5 — distinguish route, parser and filtering health

**Problem/root cause:** HTTP 200 and zero parsed items currently count healthy;
v12 flags dated-item issues only when parsed count is positive. A JS shell therefore
looks like an empty healthy source. Exact historical Qualcomm HTML was not captured.
NSA 403 is correctly transport unavailable; no safe alternate route has been proved.

**Files:** `source_pulse.py`, v12 supplement/parser health, registry consumers and
Source Pulse trace/value reports; existing source_pulse/v12/global-official/value tests.
OpenAI promotion belongs to P1, not a second P5 exception.

**Already changed:** none; minimal unrecognized HTML health counterexample reproduced.

**Implement next:** separate transport result, parser recognition/error, raw parsed
items, source-filtered items, dated/window items, accepted leads and promoted candidates.
Recognized empty RSS may be healthy empty. Unrecognized HTML/JS shell is indeterminate
or degraded, never proof of no news. All-filtered-out is distinct from parser failure.
Unknown stage counts remain null. Keep existing diagnostic consumers compatible with
additive fields and documented semantics. Capture actual Qualcomm input before any
selector fix; label current captures current, not historical. Do not infer a correct
parser from a constructed page. Leave NSA unavailable until a legitimate verified
route exists; do not evade 403 or add replacement registry sources.

**Do not change:** registry membership, paid calls, recovery polling, freshness,
source-value counting semantics (missing does not equal zero), global candidate cap.

**Fixtures/tests:** recognized empty XML, unrecognized 200 HTML/JS shell, malformed
feed, all-old items, all-filtered items, undated parsed items, 403, redirect failures,
truncation/count stages; captured real Qualcomm page for any later parser PR.
Run Pulse/v12/value targeted tests then shared gates. Expected health distinguishes
unknown parsing from verified zero fresh leads, without manufacturing candidates.

**Not verified/completion:** exact Qualcomm parser and NSA route causes remain unknown.
Health repair can finish independently with the stage matrix; a route/parser repair
requires captured real input and demonstrated contribution. Shared runtime status:
no changes, no branch/PR/CI. Keep P1 and this health PR separate.

## Astra completed

Independent code/Actions/artifact verification; preserved reports and hashes;
local counterexamples for repair-obligation loss/response rollback, parser health,
updated-only feed dates, weekday inconsistency and weak-signal loss; Agency request/
metadata and historical availability checks; bounded independent Terra reference
verification; explicit architecture contracts, negative tests and PR boundaries.

## Ready for Sol High

P0 implementation first, then the separated P1–P5 units above. Sol can implement and
verify the contracts without redoing the broad investigation. Empirical acquisition
and controlled A/B are separate acceptance work, not permission to invent evidence.

## Still needs Astra-level reasoning

None currently required to begin these specified units. Return only for a concrete
counterexample that cannot be resolved within the contracts, especially ambiguous
paid-state recovery, proof provenance or event-binding precision. Missing provider
observations alone require evidence collection, not more speculative reasoning.

## Do not merge yet

There are no runtime fix PRs in this follow-up. Do not merge any future P0–P5 runtime
branch until its stated evidence and exact-head gates pass. This is a verification
condition, **not** a request for another merge authorization: the owner already
provided conditional permission. The audit handoff itself does not fix production;
leaving its evidence PR open preserves progress without claiming incident closure.
