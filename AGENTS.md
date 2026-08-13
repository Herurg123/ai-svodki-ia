# Repository instructions

`README.md` and `automation/README.md` are part of the maintained project
contract. They must describe the current implementation, not a previous version.
Any material change to architecture, workflows, schedules, configuration,
retrieval/editorial rules, budgets, publication, deployment, recovery, cleanup
or operator commands must update every affected README in the same pull request.
Before declaring the work complete, compare documentation against code and
workflows and run the relevant offline checks.

## GitHub change workflow

Do not commit project changes directly to `main`. Use a dedicated branch and a
pull request, run CI, and inspect the resulting diff before merge.

A prepared pull request is **not** merged merely because checks are green or an
earlier message said to continue. Merge only after the project owner gives a
separate explicit merge command for that prepared PR. Production publication or
recovery that depends on a change must wait for that merge command.

## Permanent pre-hybrid search baseline

The repository state immediately before hybrid completeness is permanently
preserved at commit `d926a3abf8b9443f58f303d984ef79fdc289fc3e` and branch
`archive/search-baseline-pre-hybrid-2026-08-09`. The companion manifest is
`automation/archive/search-baselines/2026-08-09-pre-hybrid.md`.

Never move, rewrite, repurpose or delete that branch. Repository hygiene must
always classify it as `protected` with reason `permanent_archive_branch`.
Future baselines use new archive branches/manifests rather than modifying this
one.

## Repository hygiene and retention

Scheduled repository hygiene may mutate only explicitly classified ephemeral
GitHub objects: old merged branch refs, safe Actions artifacts, enabled state of
orphaned workflows, and completed runs older than 14 days only when the workflow
is independently `safe_disable`. It must not edit tracked project files, `main`,
releases, tags, permanent archive branches or published/editorial content.

The five-merged-PR branch grace is capped at 7 days. Closed-unmerged branches may
become `safe_delete` after 14 days only when current HEAD still exactly matches
the closed PR head. Orphan workflows absent from current `main` may be disabled
under the documented canonical-absence rules. GitHub-managed dynamic Pages
workflows remain diagnostic and must not be sent to the ordinary disable REST
endpoint when Pages is disabled.

Tracked source/config/test/prompt/spec orphan detection is report-only. Tracked
file cleanup still follows branch → PR → CI → diff review → separate merge
command.

The separate content cleanup retains canonical editorial metadata and removes
public dated content only under the existing **32-day** retention contract.

## Permanent digest footer asset

`posts/_footer-scr.png` is a permanent production asset, not dated release
content. Every newly rendered digest page and RSS article must end with a linked
footer image pointing to `https://dzen.ru/rybv`; image source is
`https://rybalka.one/posts/_footer-scr.png`, displayed width at most 50%.

FTP deployment must verify the remote asset and restore it if missing. Content
cleanup must never classify or delete it.

## Temporal contract for nightly research

For nightly production, exact `search_window.end_at` is the authoritative current
time for Primary Recall, hybrid completeness, every fallback coverage pass and
the recall sentinel. Do not let model/system calendar dates override it.

The canonical continuity anchor is the previous successfully published
`search_cutoff_at` and is never moved backwards. Fresh Primary Recall may use an
**effective discovery window** starting up to 24 hours before that anchor to
heal important misses. Exact archived source URLs and semantic duplicates remain
blocked, so overlap must not become unbounded backfill or republishing.

Only internally generated runtime research may carry the wider window through
the legacy generator. The trusted bridge is the ignored
`automation/fixtures/research/.runtime/` subtree. Arbitrary caller-supplied
`--research-input` paths remain restricted and cannot request a wider window.

## Primary Recall v2 contract

Fresh production uses deterministic Primary Recall v2 with exactly **12 completed
Web Search search operations**, one mandatory Responses request per direction:

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

Each pass must complete exactly one `action.type=search` and one logical search
query. A second search or batched multi-query is a contract violation.
`open_page` and `find_in_page` are navigation calls, not additional search
operations; current passes may use up to three navigation actions after the one
search. Diagnostics must count searches, logical queries, total web-search tool
items and navigation separately.

### Query discipline and source routing

Actual search queries must be short natural-language phrases, normally about
6–18 meaningful words, with relevant calendar dates written normally. Do not put
`after:`, `before:`, `site:`, long Boolean `OR` chains, parentheses or giant
company/domain lists in queries. Exact saved timestamps remain authoritative for
freshness validation.

The 2026-08-13 recall experiment showed that one generic multi-domain agency
query could return stale author/newsletter/event pages while missing fresh major
stories. Without increasing the 12-search budget, three broad slots therefore
have distinct **source-focused retrieval roles**:

- `global_breaking`: Reuters-focused business/funding/cloud/infrastructure sweep;
- `major_agencies`: Reuters-focused models/products/chips/infrastructure sweep,
  while its API filter still permits Reuters, AP, Bloomberg and FT;
- `independent_missing_events`: independent Associated Press-focused sweep of
  consumer AI, major technology/product and policy gaps after seeing the current
  candidate pool.

These query anchors affect retrieval ranking only; they are **not** a whitelist
for accepted candidates. A stronger primary source may replace the discovery
source after retrieval. Other primary passes remain broad and validate source
quality downstream. `models_products_agents` must treat major consumer-device,
OS or service launches as AI news when AI is a material part of the launch.

`major_agencies` remains the only intentional primary API-domain-filtered pass.
Do not turn its Reuters/AP/Bloomberg/FT filter into a project-wide whitelist.

Wikipedia and Reddit are not valid primary confirmation of a fresh news event.
ArXiv may be primary for a genuinely material research result but must not crowd
out current product, infrastructure, corporate, security, legal or policy news.

### Discovery, fairness and mandatory execution

Primary is discovery-first. Surface plausible meaningful fresh events as
`consider` when final editorial significance is uncertain rather than rejecting
aggressively during retrieval. Strict window, freshness, verification,
legal/curiosity, significance and deduplication checks remain downstream.

The final `maximum_candidates` cap is applied only after all 12 passes finish.
The validated pool first preserves the strongest unique contribution of each
direction, then fills remaining slots by global rank. This is retrieval-pool
fairness, not a publication quota.

All 12 directions are mandatory. Technical failure, incomplete search, second
search or malformed multi-query makes fresh Primary fail closed. A technically
healthy pass may legitimately return zero candidates. Diagnostics must preserve
actual queries, consulted sources, raw candidates, model rejections and validator
rejections.

`independent_missing_events` receives the compact existing pool and searches for
significant missing events, not another editorial filter.

### Permanent recall regressions

- `automation/fixtures/recall/2026-08-11.json`: a broad China/Asia pass found 5/6
  historical controls; separate `china_asia_integrations` recovered Apple/Qwen
  without increasing the budget. Do not collapse these passes without a new
  experiment and explicit approval.
- `automation/fixtures/recall/2026-08-12.json`: production run `31548550639`
  recorded the false-zero/runtime-ingress failure and controls for IBM/Together
  AI/Nvidia, Nvidia Nemotron/NeMo, CoreWeave and Meta Muse Glimmer backfill.
- `automation/fixtures/recall/2026-08-13.json`: production run `31652757802`
  published all four candidates it had, proving the miss occurred before
  editorial. Source-focused natural-language Reuters/AP experiments recovered
  the recorded Pixel 11/Gemini, Nebius, River AI, IBM/Together and Nvidia
  Nemotron controls without raising the 12-search budget.

Future retrieval changes must preserve these regression controls and must not
silently recreate false-low-news behavior.

### Source-health and fresh Primary metadata

Fresh Primary is fail-closed before publication when retrieval diagnostics are
obviously degraded:

- `major_agencies` must complete its mandatory search and have at least one
  consulted source;
- all twelve passes together must contain at least two consulted URLs outside
  Wikipedia, Reddit and arXiv;
- for modern Primary diagnostics carrying `search_window`, the broad source-anchor
  layer (`global_breaking`, `major_agencies`, `independent_missing_events`) must
  show at least one **agency article inside the effective window**. A dated
  Reuters/Bloomberg/FT article URL or a verified in-window Reuters/AP/Bloomberg/FT
  raw candidate is evidence. Stale author, newsletter, event or old document
  pages are not.

The last condition is intentionally evidence-based, not a quota requiring an
agency candidate in every digest. Legacy Primary artifacts that predate
`search_window` keep their compatibility behavior.

Live run `31566813147` also exposed a metadata seam: internally generated fresh
Primary was labelled `editorial_from_saved_research`. Normalization must
canonicalize proven fresh Primary (mode `primary_recall_v2`, exactly 12 searches)
to `pipeline=primary_recall_v2_then_editorial` and
`research.settings.source=trusted_runtime_primary_recall`. Caller-supplied
recovery/editorial input never receives that rewrite.

Fresh internally generated Primary is staged under the trusted `.runtime`
research root and also copied to preview diagnostics. Caller-supplied
`--research-input` still means recovery/editorial rerun and skips paid fresh
Primary.

Recovery must not resurrect a known-bad artifact. Any saved artifact whose
`artifact-normalization.json` or `artifact-validation.json` has `status=error` is
non-reusable. If saved `primary-recall.json` exists, recovery must re-run current
source-health checks before selection, including for an otherwise `full`
artifact.

## Hybrid search completeness contract

A fresh completed Primary is followed by independent budget-capped Hybrid
Completeness v1. It performs three fixed one-search passes:

1. models/products/agents/research;
2. infrastructure/chips/business;
3. safety/security/policy/major regional gaps.

A deterministic cluster check may authorize at most one `adaptive_gap` search.
Ordinary hybrid cost is 3 search operations; absolute hard cap is 4. Each pass
has the same one-search plus bounded-navigation distinction as Primary. Hybrid
has no API domain filter.

Hybrid queries follow the same natural-language discipline: normal calendar
dates, roughly 6–18 meaningful words, no `after:`, `before:`, `site:` or long
Boolean `OR` constructions. This rule exists because the 2026-08-13 artifact
showed operator-heavy hybrid queries returning no useful recovery candidates.

New candidates pass the same strict story-coverage validation and dedupe.
Editorial reruns only if at least one candidate is accepted. Caller-supplied
`--research-input` skips hybrid so already-paid work is not repeated. Transport
or hybrid-editorial failure must preserve/restore the completed Primary artifact
rather than destroy it.

## Fallback coverage contract

If Primary + Hybrid still leaves a short/zero pool, fallback coverage runs six
mandatory one-search directions with at most one retry, for a hard ceiling of
**7 completed search operations**:

1. `security_world`;
2. `security_russia`;
3. `security_asia`;
4. `legal_copyright_scraping`;
5. `curiosity`;
6. `general_coverage_gaps`.

Coverage queries also use short natural-language date phrases and must not use
`after:`, `before:`, `site:` or huge `OR`/domain/company chains. In particular,
`general_coverage_gaps` already has an authoritative API-domain filter; the
query must not rebuild that filter with `site:foo OR site:bar ...`.

Fallback is fail-closed on partial/budget/error states. A fully completed audit
may produce a legitimate zero-pool `editorial_stop`; only then may Image API,
commit and deploy be skipped as a successful no-publish rather than a failure.

## Search-budget invariant

Production ceilings are measured in completed `action.type=search` operations:

- Primary: exactly 12;
- Hybrid: normally 3, maximum 4;
- fallback coverage: maximum 7 when needed.

The theoretical maximum stays **23 search operations**. Navigation calls do not
raise this ceiling. Recall fixes must not silently increase it.

## Editorial zero-pool stop

A zero-pool result is a valid successful no-publish only after the current
temporal contract, all mandatory coverage directions and the current recall
sentinel complete successfully with no publishable candidate. Technical partial
or error states remain red and fail closed. Recovery should reuse a proven
completed editorial stop without paying for the same research again.
