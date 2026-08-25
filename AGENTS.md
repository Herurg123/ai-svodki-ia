# Repository instructions

`README.md` and `automation/README.md` are part of the project's maintained
contract. They must describe the current project, not a previous version of it.

Any pull request that materially changes project behavior or structure must
update every affected README in the same pull request. This includes changes to
architecture, workflows and schedules, configuration and defaults, models and
budgets, editorial rules, publication and deployment, recovery, cleanup, and
operator-facing commands.

Before declaring such a change complete:

1. Compare the affected README sections with the implemented code, workflows,
   configuration, and canonical specifications.
2. Update the README text and any documentation-contract tests in the same
   change.
3. Run the relevant offline checks.

Do not merge a material project update while an affected README still describes
the old behavior. If a change truly has no documentation impact, state that
explicitly in the pull request description.

## GitHub change workflow

Do not commit project changes directly to `main`. Use a dedicated branch and a
pull request, run CI, and inspect the resulting diff before merge.

A pull request must not be merged merely because its checks are green or because
a previous message asked to continue the work. Merge only after the project
owner gives a separate explicit merge command for that prepared pull request.
Production recovery or publication that depends on the change must wait for that
merge command; preparation, diagnostics, CI and diff review may proceed before
it.

## NotebookLM video subproject boundary

`automation/notebooklm-video/` is an independently maintained local Windows
downstream subproject inside the wider AI-Svodki repository. It consumes an
already-published daily digest and produces NotebookLM video assets; it does not
participate in the main nightly retrieval/editorial GitHub Actions production.

Do not modify files under `automation/notebooklm-video/` as a side effect of
tasks about retrieval, editorial policy, RSS/site generation, the main FTP
deploy, cleanup, audits, or repository hygiene unless the task explicitly
targets that subproject. Its own `AGENTS.md`, `README.md`, and `DEPLOYMENT.md`
are authoritative for that scope. Conversely, work on the video subproject does
not authorize unrelated production changes.

## Permanent pre-hybrid search baseline

The repository state immediately before the hybrid completeness architecture is
permanently preserved at commit
`d926a3abf8b9443f58f303d984ef79fdc289fc3e` and branch
`archive/search-baseline-pre-hybrid-2026-08-09`.

This baseline is a long-lived analytical and rollback reference for releases
created by the previous search mechanism. Do not move, rewrite, repurpose or
delete the branch. The commit SHA is the canonical immutable identity; the
branch is the stable human-readable pointer. Any future baseline must use a new
archive branch and manifest instead of changing this one. The companion manifest
is `automation/archive/search-baselines/2026-08-09-pre-hybrid.md`.

Repository hygiene must always classify this exact branch as `protected` with
reason `permanent_archive_branch`, independent of PR age, branch age, Actions
history or the normal stale-branch lifecycle.

## Repository hygiene operational boundary

The scheduled repository hygiene workflow may mutate only explicitly classified
ephemeral GitHub objects: old merged branch refs, safe Actions artifacts, the
enabled state of orphaned Actions workflows, and completed runs older than 14
days only when their workflow is independently classified `safe_disable`. It
must not edit tracked project files, `main`, releases, tags, permanent archive
branches, or published/editorial content. The five-merged-PR branch grace is
also capped at 7 days, so quiet periods cannot protect stale refs forever.
Closed-unmerged branches may age into `safe_delete` after 14 days only when their
current HEAD still exactly matches the closed PR head. An orphan workflow absent
from current `main` whose latest run was on the default branch may be disabled
once it has no live run; absence from current `main` is the canonical proof that
the workflow was removed. An active orphan workflow with no runs may also be
disabled on the same canonical-absence proof; already-disabled no-run workflow
metadata is report-only. GitHub-managed dynamic Pages workflows are diagnostic
objects: when Pages is disabled they must not be sent to the normal
workflow-disable REST endpoint, which GitHub rejects for this platform-managed
workflow.

Source-code, test, prompt, configuration, fixture, and specification orphan
detection is report-only. Any tracked-file cleanup still follows the normal
branch → pull request → CI → diff review → separate explicit merge command.

The existing 32-day repository/public-content cleanup remains a separate,
documented operational workflow. The repository hygiene exception does not
broaden its scope or weaken its retention and validation rules.

## Permanent digest footer asset

`posts/_footer-scr.png` is a permanent production asset, not dated release
content. Every newly rendered digest page and the RSS article content for a new
release must end with a linked footer image pointing to `https://dzen.ru/rybv`;
the image source is `https://rybalka.one/posts/_footer-scr.png` and its displayed
width must not exceed 50%.

Every FTP deployment must verify the actual remote presence of
`_footer-scr.png` after normal synchronization and restore it if it is missing.
The scheduled 32-day content cleanup must never classify or delete this file.

## Temporal contract for nightly research

For nightly production, the exact `search_window.end_at` timestamp is the
authoritative current time for Primary, bounded agency discovery rescue, hybrid
completeness, every Coverage pass, and the recall sentinel. Do not let
model/system calendar dates override that timestamp. Legacy recovery data from a
cross-midnight local/UTC window must not be reused as final research or a
terminal zero-pool stop unless it carries the current temporal-anchor contract.

The canonical continuity anchor is still the previous successfully published
`search_cutoff_at`; it is never moved backwards in the archive. Fresh Primary
Recall may use an **effective discovery window** beginning up to 24 hours before
that anchor. This bounded healing overlap exists only to recover important events
missed by the preceding digest. Exact source URLs already present in the archive
must be rejected before merge, semantic archive checks still apply downstream,
and the overlap must never become an unbounded lookback or a reason to republish
yesterday's story.

Primary, conditional agency rescue, Hybrid and fallback Coverage queries use
short date-free relative-freshness wording. Exact timestamps remain authoritative
for post-retrieval eligibility. Only internally generated runtime research may
carry this wider effective window through the legacy generator; the trusted
bridge lives under `automation/fixtures/research/.runtime/`. Arbitrary
caller-supplied `--research-input` paths remain restricted by the existing guard.

## Primary recall v2 contract

Fresh production research uses deterministic **Primary Recall v2**. The hard
Primary budget remains exactly twelve completed Web Search **search operations**,
one per mandatory direction:

1. `global_breaking`;
2. `major_agencies`;
3. `models_products_agents`;
4. `infrastructure_chips_cloud`;
5. `business_investment_partnerships`;
6. `china_asia_models`;
7. `china_asia_integrations`;
8. `russia`;
9. `developer_tools`;
10. `security_safety`;
11. `legal_regulation`;
12. `independent_missing_events`.

A Primary pass must complete exactly **one `action.type=search` operation and one
logical query**. Do not use `max_tool_calls=1` as the search-budget mechanism:
`open_page` and `find_in_page` are hosted tool calls too. Current passes allow up
to three navigation actions after the one search. A second search action or a
batched multi-query search is a contract violation.

Each Primary Responses pass has `max_output_tokens=6000`. This is reasoning/JSON
headroom, not additional search budget.

Broad safety nets `global_breaking` and `independent_missing_events` have no API
domain filter. `major_agencies` remains an extra Reuters/AP/Bloomberg/FT
high-signal route using exact date-free query
`latest AI chips infrastructure financing earnings business deals policy security`.
Do not turn this route into a project-wide publisher whitelist. The route's API
domain filter remains part of the mandatory Primary contract.

Search prompts carry exact effective window only as eligibility boundary. Actual
queries are short, date-free and use `latest`/`recent`/`current`/`breaking` cues.
Do not copy calendar dates, years, month names, `after:`/`before:` or huge Boolean
lists into query text.

Wikipedia and Reddit must not be used as primary confirmation of a fresh news
event. ArXiv is allowed as primary for genuinely material research but must not
crowd out current product, infrastructure, corporate, security, legal or policy
news.

Do not collapse the two China/Asia passes. `china_asia_models` remains the
model/product/release route. `china_asia_integrations` keeps integrations,
partnerships and deployments while also covering major business, earnings,
revenue and strategy using
`latest China Asia AI business earnings revenue strategy cloud partnerships deployments`.
`russia` remains a separate mandatory Primary search and must not be consumed by
agency/Asia changes.

Permanent regression references include:

- `automation/fixtures/recall/2026-08-11.json` for separate China integration;
- `automation/fixtures/recall/2026-08-12.json` for false-zero/runtime ingress;
- `automation/fixtures/recall/2026-08-13.json` for high-signal agency controls;
- `automation/fixtures/recall/2026-08-21-agency-asia.json` for agency/Asia
  semantics;
- `automation/fixtures/recall/2026-08-24-agency-recovery.json` for the Aug 24
  false-zero, Reuters-only rescue routing, and manual fresh-research recovery.

Fresh Primary remains subject to fail-closed source-health before publication.
`major_agencies` must have at least one consulted source, and the combined matrix
must contain at least two consulted source URLs outside Wikipedia, Reddit and
arXiv. A technical failure or incomplete search in any mandatory direction is
red. A technically completed route may legitimately return zero candidates.

Primary is discovery-first. The final candidate cap must not be enforced
incrementally; all 12 passes first contribute to a larger validated/deduplicated
pool, then the final cap is applied globally while preserving a strongest unique
contribution per direction before global fill.

Primary is injected through the existing generator `--research-input` interface.
Fresh internal research lives under trusted ignored `.runtime`; caller-supplied
`--research-input` means recovery/editorial rerun and must not execute paid fresh
Primary.

Recovery must not resurrect known-bad artifacts. Any source with
`artifact-normalization.json.status=error` or
`artifact-validation.json.status=error` is non-reusable. Saved modern Primary
must repeat current source-health validation even for a full artifact.

## Bounded agency missing-event discovery rescue v3

After the saved Primary/provisional-editorial checkpoint and **before Hybrid**,
production may run `automation/scripts/agency_discovery_rescue.py`. This layer is
not a 13th mandatory Primary pass. It is conditionally enabled only when the
mandatory `major_agencies` route technically completed and has either
`raw_count == 0` or `accepted_count == 0`. Never use total candidate count or
story count as its trigger.

The rescue may perform at most **one** additional Web Search operation. The
actual query is fixed, date-free and publisher-neutral:
`latest AI chips infrastructure financing earnings business deals policy security`.
Use a provider-level Reuters-only route with
`allowed_domains=["reuters.com"]`; do not redundantly add `Reuters`, `AP`, dates,
`site:` or Boolean publisher lists to the query text. In v3 search context is
`high`. The evidence for this narrow change is fresh production run
`32691255059`: v2 used the same Reuters-only route and exact query with `medium`
but returned `consulted_sources=[]` and `raw_count=0`, leaving the in-window
Alibaba share-placement positive control undiscovered. Independent Reuters-
focused search with the same neutral query can surface that control. The current
environment still does not expose an assistant-side Terra interface with an
explicit `medium/high` switch, so do not describe this as an isolated Terra A/B.
Treat `high` as the next bounded production-supported reliability hypothesis.
Do not change the query, add a second search, broaden domains, or weaken
freshness/significance/dedupe in the same experiment. The global ceiling remains
24.

Downstream acceptance is defense-in-depth narrow: a discovered event needs a
direct Reuters (`reuters.com`) primary URL. Yahoo, TradingView, MarketScreener,
Investing and other syndicated/aggregator URLs do not satisfy the direct-source
condition. AP remains available through the mandatory `major_agencies` Primary
route and downstream same-event corroboration; do not silently add a second AP
rescue search.

This is **missing-event discovery**, not Coverage's same-event corroboration.
Every returned candidate still passes the ordinary story-coverage validator,
archive dedupe, and a deterministic same-event guard using
`organization + event_type + published_date`. If the event already exists under a
different URL, do not create a duplicate. Source upgrades for existing events
remain the responsibility of the downstream corroboration layer.

A discovered candidate must pass unchanged Source Freshness Proof before
editorial. Reuters never grants significance privilege or automatic inclusion.
Stale, weak, analysis/opinion-only, duplicate and zero-result outcomes are normal
diagnostics. A rescue transport/validation failure is supplemental and must not
destroy a previously publishable Primary artifact. Do not weaken freshness,
editorial significance or archive dedupe to compensate for retrieval misses.

Persist `agency-discovery-rescue.json` before the paid call (`search_started`) and
after the response. At-most-once semantics are mandatory: automatic recovery
must never repeat `search_started`, because the provider-side consumption is
unknown. `search_completed` or `merge_failed` may resume merge from saved
response without another search. If recovery finds a modern full artifact whose
`major_agencies` trigger applies but no rescue attempt has started, downgrade it
to `partial_editorial` so normal text-runtime prerequisites are available for the
one legitimate first attempt. If a saved response still needs merge/freshness/
editorial, recovery is also text-needed.

If rescue successfully adds a candidate and Hybrid later fails, that candidate
must still reach the existing trusted-runtime Source Freshness Proof/editorial
path. Do not silently restore Primary and discard the rescue addition. If the
recovery freshness gate itself errors, remove supplemental rescue-origin rows
rather than leaving an unverified candidate in the recovered pool.

The historical source-open fixture remains
`automation/fixtures/recall/2026-08-22-agency-discovery-rescue.json`. The current
out-of-sample contract is
`automation/fixtures/recall/2026-08-24-agency-recovery.json`, which adds Alibaba
share placement and explicit stale/opinion/syndication/duplicate/after-cutoff/
quiet-window negatives. The global search ceiling remains 24.

## Manual fresh-research recovery after a terminal zero-pool

`daily-production.yml` normally reuses the best same-day artifact, including a
completed usable zero-pool `editorial_stop`. That is correct for cost control,
but it means a plain rerun after a retrieval hotfix may never execute the new
retrieval code.

For this specific operator case, `workflow_dispatch` exposes
`force_fresh_research` with default `false`. When and only when a manual run sets
it to `true`, automatic same-day artifact selection is disabled and the workflow
is allowed to execute fresh research on current `main`. Scheduled behavior and
default manual behavior must remain unchanged.

`force_fresh_research=true` and an explicitly supplied `recovery_run_id` are
mutually exclusive. Reject that conflict before any paid API call rather than
inventing precedence. The `publish` input remains independent: manual
`publish=false` is still a dry-run; `publish=true` follows the normal publish path
only after successful fresh research.

Use this flag only after the relevant retrieval patch is merged and only when the
project owner explicitly authorizes a real production rerun that may spend
`OPENAI_API_KEY`. Architecture experiments, A/B comparisons, debugging and
regression validation must use assistant-owned resources and offline tests. A
request to fix code is not permission to spend production API budget.

## Source Pulse v1 production shadow contract

Stage 2 Dual Discovery runs `source_pulse_shadow.py` only after mandatory Primary and
conditional agency-discovery rescue (including rescue Source Freshness Proof), and
strictly before Hybrid gap planning. This placement is intentional: Pulse must never
mask `major_agencies raw=0/accepted=0`, change the rescue trigger, occupy Primary caps,
or suppress the existing optional regional Hybrid health check.

The current production mode is **shadow only**. `automation/config/source-pulse-v1.json`
must keep `candidate_influence=false` and `repoll_on_recovery=false`. Source Pulse may
collect fixed-source leads and produce Search/Pulse fusion diagnostics, but it must not
add/remove/rank candidates, grant significance, bypass Source Freshness Proof, or create
a China/Russia publication quota. Tier B sources are lead-only and have no authority
privilege. Candidate influence or any model-based Pulse triage requires a separate
controlled experiment, explicit production-cost review, documentation update and PR.

Source Pulse itself performs zero OpenAI calls and zero Web Search operations. The
global Web Search ceiling remains **24 = 12 Primary + 1 agency rescue + 4 Hybrid + 7
Coverage**. Source/HTTP/DNS/parser failure is fail-open and must leave `candidates.json`
unchanged. Persist `source-pulse.json` in the dated artifact plus a production-daily
diagnostic mirror. Persist `fetch_started` before network polling; a second invocation
for the same artifact reuses the saved snapshot and must not silently repoll mutable
sources, including an interrupted `fetch_started` state. Normal same-day recovery reuses
the saved artifact and does not create a fresh Pulse snapshot.

Diagnostics must expose source health plus `pulse_only`, exact/event `both`,
`search_only`, cutoff ambiguity and archive duplicates. The daily independent audit is
permanent and, whenever Source Pulse diagnostics are present, must separately assess
Search-vs-Pulse recall, Pulse-only high-signal leads, false positives/noise, source
outages/parser drift, China/Asia and Russia benefit, and whether any shadow behavior
accidentally influenced publication. Do not interpret a Pulse-only lead as automatic
Must Include; the independent reference set remains authoritative for recall analysis.

## Hybrid search completeness contract

A fresh completed Primary plus its conditional agency rescue is followed by the
separate budget-capped Hybrid layer. Hybrid performs three fixed one-search
passes:

1. models/products/agents/research;
2. infrastructure/chips/business;
3. safety/security/policy/major regional gaps.

Deterministic cluster coverage may authorize at most one adaptive gap search.
Hybrid hard ceiling is four search operations. API domain filtering is disabled.
The optional fourth slot may become a Russia/Asia completeness-health check when
Primary regional routes are valid but empty; this is not a publication quota.

Hybrid query planning follows the same date-free relative-freshness contract and
full effective-window validation. New candidates are merged through the ordinary
validator. Editorial reruns only when a candidate is actually accepted.
Caller-supplied `--research-input` must not recurse into Hybrid. Hybrid failure
must preserve/restore a usable Primary artifact, and any accepted agency rescue
candidate must survive the failure and remain available to editorial/Coverage.

Fallback Coverage also distinguishes search operations from navigation items.
Production targeted passes request one search operation and may use a small
navigation allowance; historical multi-search callers retain their hard caps.

The total theoretical retrieval ceiling is **12 Primary + up to 1 bounded
agency discovery rescue + up to 4 Hybrid + up to 7 Coverage = 24 completed search
operations**. Navigation actions do not raise this search-operation ceiling.
Do not silently raise 24 without a new controlled experiment and architecture
review.

## Editorial zero-pool stop

A completed zero-pool result is a normal successful `no-publish`, not a
production failure, but only after current temporal-anchor contract, all required
quality/search stages, six mandatory Coverage directions, and the applicable
current sentinel have completed successfully with no publishable candidate.
Technical partial/error audits remain fail-closed and red. Recovery must reuse a
proven completed editorial stop without repeating paid work unless a manual
`force_fresh_research=true` run explicitly opts out after an authorized hotfix.

## Source-focused recall contract after 2026-08-13 and 2026-08-14

Production run `31652757802` is a permanent retrieval-quality regression: its
candidate pool contained exactly four events, editorial selected all four and all
four were published. `automation/fixtures/recall/2026-08-13.json` records five
high-signal controls recovered by independent source-focused searches.

The 2026-08-14 fresh production demonstrated that source-focused routing alone is
insufficient when explicit date ranges distort ranking. Across Primary, rescue,
Hybrid and Coverage, actual search strings use short date-free natural-language
queries; exact effective window remains post-retrieval validator.

Do not increase the mandatory 12-search Primary matrix to solve this class. The
conditional rescue is a separate quality layer justified later by repeated
out-of-sample agency misses. Mandatory source-diverse routing remains:

- `global_breaking`: source-neutral broad current-AI catch-all;
- `major_agencies`: Reuters/AP/Bloomberg/FT filtered mandatory route;
- `independent_missing_events`: source-neutral missing-events sweep.

For modern Primary diagnostics, source-health must prove at least one fresh
in-window Reuters/AP/Bloomberg/FT evidence across the matrix. This is a technical
health check, not an agency-story quota.

## Search diagnostic secret hygiene

Provider-returned URLs may contain temporary signed credentials. Before
persisting Primary, agency rescue, Hybrid or Coverage diagnostics, strip
credential/token/signature query parameters while preserving source identity.
Never weaken artifact secret scanning to permit signed credentials.

## Paid-stage recovery and image provenance

A validated digest is a paid-stage checkpoint. Once text validation succeeds, a
later cover/build/commit/deploy failure must not automatically repay completed
Primary, agency rescue, Hybrid, Coverage or editorial work. Recovery reuses the
highest-completeness valid artifact and resumes from first incomplete stage.

Image provenance uses separate identities. `image_request_id` is mandatory for
the image operation; `source_editorial_request_id` is optional provenance and
must not block valid recovery. Preserve provider `x-request-id` when available.
Automatic image retries remain disabled.

## Fresh-agency Coverage corroboration

For modern non-zero pools, source-health may require one bounded same-event agency
corroboration after six mandatory Coverage directions. Use only the otherwise
free seventh Coverage slot. Zero-pool sentinel and non-zero
`fresh_agency_rescue` are mutually exclusive **within Coverage**; Coverage hard
cap remains seven.

This downstream rescue targets one **existing** high-significance agency-likely
event. It performs exactly one Web Search without API domain filter, while
acceptance requires direct Reuters/AP/Bloomberg/FT URL, in-window freshness and
exact same-event match by `organization`, `event_type`, `published_date`. A
successful corroboration changes the source of the existing candidate and must
never create a duplicate story.

Do not confuse this with pre-Hybrid `agency_discovery_rescue`: corroboration
finds a stronger source for an existing event; discovery finds an event missing
from the candidate pool. The global ceiling including the separate discovery
slot is 24, while Coverage itself remains capped at seven.

## Exact agency cutoff

All agency evidence respects exact saved temporal boundary. Timezone-aware
`published_at` compares directly with `search_window.start_at/end_at`. Date-only
evidence on the cutoff calendar day is not proof that an article existed before
the saved cutoff and must fail closed. Keep start-day date-only compatibility for
bounded healing overlap.

## Regression rule: terminal agency source-health

Do not turn absence of a fresh agency candidate into a standalone fatal gate if
mandatory `major_agencies` and applicable bounded quality layers technically
completed. Terra/Web Search ranking is nondeterministic. A zero-result from the
conditional discovery rescue is diagnostic, not an instruction to publish weak
material or to fail an otherwise usable digest. Technical failure of mandatory
routes, broken search contract, incomplete Coverage and invalid temporal evidence
remain fail-closed.

## Retrieval Quality v1

- Preserve potentially large `unverified` Primary evidence in
  `unresolved_signals`; mandatory resolver is reserved for strict high-signal
  evidence.
- `entities`, `anchors`, `source_hint` are evidence/hints, not company or
  publisher whitelists.
- Targeted unresolved resolution uses only the existing seventh Coverage slot and
  does not increase Coverage above 7.
- Coverage adaptive priority remains mandatory technical retry first, then
  unresolved resolution; without unresolved signal, existing same-event
  fresh-agency rescue / zero-pool sentinel rules apply.
- Russia/Asia zero-result is a completeness-health check through existing
  optional fourth Hybrid slot, not a regional story quota.
- Global production search ceiling is **24**: 12 Primary + up to 1 conditional
  agency discovery + up to 4 Hybrid + up to 7 Coverage.
- Modern full recovery without current Retrieval Quality is downgraded to partial
  editorial recovery. Agency discovery has an independent recovery contract and
  may also require that downgrade without replaying completed paid work.
- Recovery artifacts remain bound to exact `daily-production-YYYY-MM-DD` date.
- Live Terra smoke is diagnostic; do not require one exact external agency URL in
  deterministic CI.

## Source Freshness Proof v1

Trusted production research must not publish a candidate merely because a model
populated `published_date`/`published_at`. Before each editorial pass fed by an
internal Primary/rescue/Hybrid/Coverage runtime bridge, `source_freshness.py`
fetches only source URLs already cited by that candidate and extracts
machine-readable publication evidence such as `article:published_time` or JSON-LD
`datePublished`. `dateModified` never counts as publication evidence.

Timezone conversion and comparison against exact saved effective window are
deterministic Python operations. Date-only evidence on cutoff day fails closed.
An already-cited supporting source may be promoted to primary when it provides
the valid date. Never run a new search or invent a date merely to pass freshness.
Outside-window source yields `exclude / old_reprint`; no verifiable date yields
unconfirmed and blocks publication.

Source Freshness Proof itself makes no OpenAI or Web Search call. It does not
consume the new rescue slot. The project-wide search ceiling is 24 solely because
of the separate conditional agency discovery layer.

The 2026-08-17 AP/Anthropic incident remains the permanent stale regression:
actual source `datePublished` was 2026-07-31 despite production metadata claiming
2026-08-16. Keep that candidate excluded while preserving genuinely fresh offset
timestamps through Python timezone arithmetic.

## Independent audit journal and retrieval experiments

`automation/audits/independent-audit-journal.md` is the canonical long-lived
journal for independent Freshness/Completeness monitoring. Stored architecture
experiments belong under `automation/audits/experiments/`; machine-readable
historical contracts belong under `automation/fixtures/recall/`.

After each successful release:

1. resolve actual production run, artifact, published digest and exact effective
   window;
2. inspect Primary/agency rescue/Hybrid/Coverage candidate and rejection anatomy;
3. independently build a reference set using assistant-side Terra when actually
   available, otherwise clearly label the alternative search method;
4. classify stale, retrieval misses, editorial rejections, duplicates, material
   updates, after-cutoff and borderline signals separately;
5. check agencies, models/products/agents, chips/infrastructure/cloud,
   business/investment, legal, security, Russia and China/Asia;
6. update the same canonical journal with verdicts and architecture evidence.

This monitoring uses assistant-owned resources and must not spend the user's
production API budget. A single miss is evidence, not automatic permission to
mutate retrieval. Architecture changes require controlled experiment and
architecture-wide dependency/regression audit. If assistant-side Terra is not
exposed in the current environment, state that limitation explicitly rather than
pretending another search backend is a Terra A/B. Never use the user's production
API merely to resolve that tooling gap without explicit permission.

The 2026-08-21 agency/Asia experiment initially kept Primary at 12, Hybrid at up
to 4 and Coverage at up to 7, so its historical accepted patch retained the
23-search ceiling and deliberately avoided an immediate new agency slot. That
statement is historical, not the current architecture. Repeated Broadcom miss on
22 August plus out-of-sample Reuters/Nvidia miss on 23 August justified the
separate conditional agency discovery rescue.

The first 2026-08-24 zero-pool run proved that the mandatory four-domain agency
route ranked stale sources while the source-open rescue produced a polluted
aggregator/syndication pool. Independent assistant-side Reuters-focused replay
recovered the Alibaba placement and the recent Reuters regression set without
increasing the budget, which justified v2 Reuters-only provider routing. Fresh
run `32691255059` then tested that v2 route in production: the one Reuters-only
search with `medium` completed but returned zero consulted sources and zero raw
candidates, so Alibaba was still absent before freshness/editorial. V3 therefore
changes only `search_context_size` to `high`, keeping the exact neutral query,
Reuters-only domain filter, one-search cap, direct-source acceptance and global
ceiling 24. This is not presented as an isolated assistant-side Terra A/B. The
machine-readable regression fixture remains
`automation/fixtures/recall/2026-08-24-agency-recovery.json`; the v3 decision is
recorded in `automation/audits/experiments/2026-08-24-agency-context-high.md`.

## Cleanup resilience contract (2026-08-18)

The public-content cleanup must treat `posts/images/` as mandatory, but the
historical `posts/dzen-test/images/` directory may be absent after the final
legacy image has expired. Any retained legacy publication still requires its
exact page, primary legacy image and canonical mirror and must fail closed if any
is missing. Do not add `.gitkeep` merely to satisfy cleanup validation.

Repository hygiene may retry only idempotent GitHub API `GET` requests after
transient transport failures or HTTP `500`, `502`, `503`, or `504`. The current
bound is two retries after the initial attempt with short backoff. Mutating
`DELETE` and `PUT` requests must not be automatically retried; apply-time safety
checks remain authoritative.

The regression source for this contract is the pair of 2026-08-17 failures:
workflow run `32035035642` received a GitHub Actions API HTTP 500 while reading
jobs, while run `32078536750` failed because the already-retired empty
`posts/dzen-test/images/` directory was absent after checkout. Future cleanup
changes must preserve both regression cases in offline tests.
