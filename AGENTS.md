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
authoritative current time for research, hybrid completeness, every coverage
pass, and the recall sentinel. Do not let model/system calendar dates override
that timestamp. Legacy recovery data from a cross-midnight local/UTC window must
not be reused as final research or a terminal zero-pool stop unless it carries
the current temporal-anchor contract version.

The canonical continuity anchor is still the previous successfully published
`search_cutoff_at`; it is never moved backwards in the archive. Fresh Primary
Recall may, however, use an **effective discovery window** beginning up to 24
hours before that anchor. This bounded healing overlap exists only to recover
important events missed by the preceding digest. Exact source URLs already
present in the archive must be rejected before merge, semantic archive checks
still apply downstream, and the overlap must never become an unbounded lookback
or a reason to republish yesterday's story.

The effective window has two distinct retrieval roles. The first 24 hours from
effective start to the continuity anchor are **healing overlap**. The main
continuity period starts at the anchor and ends at `search_window.end_at`.
Primary, Hybrid and fallback Coverage search queries use short date-free
relative-freshness wording; neither the continuity period nor healing overlap is
encoded as calendar dates in query text. Exact timestamps remain authoritative
for post-retrieval eligibility, and the full effective window remains valid for
healing a major missed event.

Only internally generated runtime research may carry this wider effective
window through the legacy generator. The trusted bridge lives under the ignored
`automation/fixtures/research/.runtime/` subtree. Arbitrary caller-supplied
`--research-input` paths remain restricted by the existing generator guard and
must not be allowed to request a wider window.

## Primary recall v2 contract

Fresh production research uses deterministic **Primary Recall v2** instead of
letting one agentic Responses call allocate the entire 12-search budget. The
hard primary budget remains exactly twelve completed Web Search **search
operations**, each assigned to one mandatory direction:

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

A primary pass must complete exactly **one `action.type=search` operation and
one logical search query**. Do not use `max_tool_calls=1` as the search-budget
mechanism: `open_page` and `find_in_page` are also hosted tool calls. Current
passes allow up to three navigation tool actions after the one search so the
model can verify source date and facts. Diagnostics must count search operations,
logical queries, total web-search tool items and navigation actions separately.
A second search action or a batched multi-query search is a contract violation.

Each Primary Responses pass has `max_output_tokens=6000`. This is structured-output/reasoning headroom, not additional Web Search budget: the pass still must complete exactly one search operation. The 2026-08-14 live relative-freshness smoke showed the final `independent_missing_events` search and all three navigation actions completing successfully, but the response becoming `incomplete` solely at the former 3500-token ceiling.

Broad safety nets are source-neutral: `global_breaking` and
`independent_missing_events` have no API domain filter. `major_agencies` remains
an extra Reuters/AP/Bloomberg/FT high-signal route. Do not turn this source route into a
project-wide whitelist; source quality is still validated after retrieval.

Search prompts carry the exact effective window only as the authoritative
eligibility boundary. The **actual search query is date-free**: use a short
natural-language relative-freshness cue such as `latest`, `recent`, `current` or
`breaking`; do not copy calendar dates, years, month names, `after:`/`before:` or
other explicit temporal boundaries into the query. The full saved effective
window remains authoritative for final freshness validation.

High-signal routing stays source-diverse without increasing the 12-search
budget:

- `global_breaking` is a source-neutral broad current-AI catch-all without an API
  domain filter;
- `major_agencies` is an additional Reuters/AP/Bloomberg/FT sweep using the exact date-free query `latest AI chips data centers investments deals policy security`;
- `independent_missing_events` is a source-neutral broad missing-events sweep
  after seeing the current candidate pool.

These are ranking routes, not a candidate whitelist. A stronger official primary
source or other authoritative source may still be the final source of a
candidate. All non-`major_agencies` Primary directions remain without API domain
filters.

Wikipedia and Reddit must not be used as primary confirmation of a fresh news
event. ArXiv is allowed as the primary source of a genuinely material research
result, but it must not crowd out current product, infrastructure, corporate,
security, legal, or policy news.

Do not collapse the two China/Asia passes back into one broad regional search
without a new recall experiment and explicit approval. The 2026-08-11
regression showed that a broad China pass found the other control events but
missed the Apple/Qwen product-integration story; a separate integrations /
partnerships pass recovered it without increasing the 12-search primary budget.
The historical benchmark is `automation/fixtures/recall/2026-08-11.json`.

The 2026-08-12 production failure is a second permanent regression benchmark:
`automation/fixtures/recall/2026-08-12.json`. It records the runtime-ingress
failure and fresh Reuters controls including IBM/Together AI/Nvidia, Nvidia
Nemotron/NeMo and CoreWeave, plus the bounded backfill control for Meta Muse
Glimmer. Future retrieval changes must not silently recreate that false-zero
class.

The later fresh production run `31566813147` is an additional live quality
regression. It completed Primary Recall, editorial and coverage, but
`major_agencies` had no consulted source and the selected pool was dominated by
low-signal Wikipedia/Reddit/arXiv retrieval. It also exposed a metadata seam:
trusted fresh Primary Recall was labelled `editorial_from_saved_research` while
correctly recording 12 fresh search operations. Current normalisation must
canonicalize proven fresh Primary Recall to
`pipeline=primary_recall_v2_then_editorial` and
`research.settings.source=trusted_runtime_primary_recall` before artifact
validation.

The 2026-08-14 production run is a separate recall-quality regression class. It
completed all 12 Primary searches, four Hybrid searches and six Coverage
searches, yet most actual queries used dates spanning the healing overlap plus
the main continuity period. The expanded date range surfaced stale/overlap
material while fresh high-signal continuity-period events were absent from the
candidate pool. Future query changes must keep the full effective window for
validation but must not restore equal ranking priority to the first 24-hour
healing segment. The same run also demonstrated that two Reuters-focused broad
slots are not meaningfully independent source coverage, hence the source-neutral
`major_agencies` rule above.


A fresh 2026-08-14 recovery attempt after continuity-first routing exposed a further
source-ranking failure: the Reuters text-anchored pass returned old Reuters mirrors,
while the four-domain agency pass returned stale Bloomberg hub/video pages and failed
fresh agency source-health. The regression rule is therefore stronger: high-signal
source diversity must be enforced by disjoint API domain filters, not merely publisher
names in query text. Do not remove these filters without a new live recall experiment.

Fresh Primary Recall is also subject to a fail-closed source-health guard before
publication. `major_agencies` must have at least one consulted source, and the
combined twelve-pass diagnostics must contain at least two consulted source URLs
outside Wikipedia, Reddit and arXiv. This guard is deliberately minimal: it does
not impose a project-wide whitelist or require every pass to find a candidate;
it only prevents a technically completed but obviously degraded retrieval run
from being mistaken for a healthy low-news day.

Primary is **discovery-first**. A pass should surface plausible meaningful
fresh events into the candidate pool, using `consider` when final significance
is uncertain, rather than performing aggressive editorial rejection during
retrieval. Strict source, freshness, legal/curiosity, significance and
deduplication checks still run through the existing story-coverage validator and
editorial stages after discovery.

The configured final candidate cap must **not** be enforced incrementally in
search order. All twelve passes first contribute to a larger validated and
deduplicated discovery pool. Only after every mandatory pass completes may the
normal final cap be applied globally. The selection must preserve the strongest
unique contribution of each direction before filling remaining slots by global
rank, so early broad searches cannot starve later China/Asia, Russia, security,
legal, or missing-events passes. This is retrieval-pool fairness, not a quota on
published stories. Diagnostics must record both the validated discovery-pool
size and any events dropped only by the final cap.

All twelve directions are mandatory for a fresh production run. A technical
failure or incomplete Web Search in any direction is a red, fail-closed primary
failure and must never be reinterpreted as a low-news day. A completed direction
may legitimately return zero candidates. Primary diagnostics must preserve the
actual queries, consulted sources, raw candidates, model rejections and
validator rejections for each direction.

The final `independent_missing_events` pass receives a compact list of already
found candidates and explicitly searches for significant events absent from the
pool. It is a last-mile recall check, not another editorial filter.

The 2026-08-16 source-health failure is a permanent regression case. A generic
`latest major artificial intelligence news` agency query completed but ranked
hubs instead of enough fresh direct agency stories, even though fresh Reuters
evidence existed in the effective window. The `major_agencies` route therefore
uses Reuters/AP/Bloomberg/FT API routing plus the exact high-signal date-free
query above without increasing the 12-search Primary budget. Agency rescue target
ranking must normalize event-type families such as `acquisition_closed` to the
`acquisition` family. Regional classification must keep metadata-only secondary
organizations such as `Writer; Z.ai` out of the China section while recognizing
a tracked secondary party explicitly named in the story title, such as
`Uber; Pony.ai`. Coverage editorial reruns must echo child output before raising
so the real validation error remains visible in Actions diagnostics.

Primary Recall v2 is injected into the existing generator through its
`--research-input` interface so editorial policy and artifact validation remain
shared with recovery. Fresh internally generated research is staged in the
trusted ignored `.runtime` subtree and also copied to preview diagnostics. A
caller-supplied `--research-input` still means recovery or editorial rerun and
must skip paid fresh primary. Recovery must not repeat already paid primary work.

Recovery must also not resurrect a known-bad paid artifact. Any saved source
whose `artifact-normalization.json` or `artifact-validation.json` already has
`status=error` is non-reusable. If a saved artifact contains
`primary-recall.json`, recovery must repeat the same source-health guard before
selecting it, even when all canonical digest files are present. A `full` artifact
must never bypass research/source-health validation merely because it reached a
late stage in an earlier failed run.

## Hybrid search completeness contract

A fresh completed Primary Recall v2 run is followed by the separate
budget-capped hybrid completeness layer as independent insurance rather than as
a substitute for primary coverage.

The completeness layer performs three fixed one-search passes:

1. models/products/agents/research;
2. infrastructure/chips/business;
3. safety/security/policy/major regional gaps.

After those passes, deterministic cluster coverage may authorize at most one
adaptive gap search when a whole cluster is still absent from the combined
primary + completeness candidate pool. The hard ceiling is four completed
Web Search **search operations**. Each pass follows the same one-search rule as
primary and may use limited navigation tool actions for source verification.
API domain filtering is deliberately disabled in hybrid; source quality is
validated after retrieval.

Hybrid query planning must follow the same continuity-first temporal contract.
Its `_time_hint` shifts the query start by 24 hours from effective start back to
the continuity anchor, while full effective-window validation remains intact.
Do not revert Hybrid to using the healing-overlap start date as an equal query
boundary.

New candidates are merged through the existing strict story-coverage validator
and editorial is rerun only when at least one candidate is actually accepted.
The completeness layer never runs recursively for caller-supplied
`--research-input` editorial reruns or recovery, so already-paid
primary/completeness work is not repeated. Accepted merged research is staged
through the same trusted `.runtime` bridge. A transport or
completeness-editorial failure must preserve or restore the completed primary
artifact and remain diagnostic rather than destroying an otherwise publishable
primary result. Short/empty pools still proceed to the mandatory six-direction
coverage audit and zero-pool recall sentinel.

Fallback coverage also distinguishes search operations from navigation tool
items. Its production targeted passes request one search operation and may use a
small navigation allowance to verify pages. Historical multi-search callers
retain their old hard `max_tool_calls` cap rather than silently gaining budget.
Coverage query text must also prioritize the main continuity period after the
24-hour healing overlap, while candidate validation remains against the full
effective window.

The total retrieval ceilings remain **12 primary + up to 4 hybrid + up to 7
fallback coverage = 23 completed search operations** in the theoretical worst
case. Navigation tool actions do not raise this search-operation ceiling, though
they do increase the total number of hosted tool calls. Improving recall must
not silently raise the 23-search limit.

## Editorial zero-pool stop

A completed zero-pool result is a normal successful `no-publish`, not a
production failure, but only after the current temporal-anchor contract, all
six mandatory coverage directions, and the current recall sentinel have
completed successfully with no publishable candidate. In that state Image API,
commit, and deploy must remain skipped. Technical partial/error audits remain
fail-closed and red. Recovery must reuse a proven completed editorial stop
without repeating paid research or coverage.

## Source-focused recall contract after 2026-08-13 and 2026-08-14

Production run `31652757802` is a permanent retrieval-quality regression: its
candidate pool contained exactly four events, editorial selected all four and
all four were published. The failure was therefore upstream of editorial.
`automation/fixtures/recall/2026-08-13.json` records five high-signal controls
that independent source-focused searches recovered in the same effective
window: Pixel 11/Gemini, Nebius, River AI, IBM/Together AI and Nvidia Nemotron.

The following fresh production on 2026-08-14 showed that source-focused routing
alone is insufficient if query dates still give equal ranking weight to the
healing overlap. It also showed that duplicating Reuters anchors across two
broad slots is not independent source coverage.

Do not increase the 12-search Primary budget to solve this class. Keep the
source-diverse routing and continuity-first query contract:

- `global_breaking`: Reuters-focused funding/acquisition/M&A/major business;
- `major_agencies`: source-neutral major-AI query inside the existing
  Reuters/AP/Bloomberg/FT API domain filter;
- `independent_missing_events`: Associated Press-focused consumer-AI / major
  technology / policy gap sweep after seeing the current candidate pool.

These source names are retrieval routing for ranking, not a candidate whitelist.
`models_products_agents` must also treat a major device, OS or mass-market
service launch as relevant when the AI layer is materially part of the launch.

Across Primary, Hybrid and fallback Coverage, actual search strings must use
short natural-language queries, roughly 6–18 meaningful words, with calendar
dates of the main continuity period after the first 24-hour healing overlap. Do
not use `after:`, `before:`, `site:`, long Boolean `OR` chains, parentheses or
huge entity/domain lists. `general_coverage_gaps` already has its own API domain
filter and must not recreate it as a giant `site:` query.

For modern Primary diagnostics that contain `search_window`, source-health must
also prove at least one fresh in-window Reuters/AP/Bloomberg/FT evidence among
`global_breaking`, `major_agencies` and `independent_missing_events`. A dated
Reuters/Bloomberg/FT consulted URL or a verified agency raw candidate whose
`published_date` is in the effective window counts. Stale author, newsletter,
event or old document pages do not count. This is a fail-closed technical health
check, not a quota requiring an agency story in every published digest.


## Search diagnostic secret hygiene

Provider-returned URLs may contain temporary signed credentials. Before persisting Primary, Hybrid or Coverage diagnostics, strip credential/token/signature query parameters while preserving source identity. Never weaken the artifact secret scanner to permit signed credentials.


## 2026-08-14 relative-freshness retrieval regression

A live `gpt-5.6-terra` A/B showed that explicit calendar dates in Web Search
queries can degrade ranking and create false-zero retrieval. Production uses
date-free relative-freshness queries for Primary, Hybrid, Coverage and the final
broad zero-pool sentinel, while the exact effective window remains a strict
post-retrieval validator. `global_breaking`, `independent_missing_events` and the
sentinel are source-neutral catch-alls. If Hybrid finds valid candidates but its
immediate editorial rerun fails, the merged candidate pool must still be handed
to Coverage instead of being lost when the primary editorial artifact is
restored.


Source-health после перехода на source-neutral routing проверяет свежую Reuters/AP/Bloomberg/FT evidence по **всей 12-pass Primary matrix**, а не только в `global_breaking`/`major_agencies`/`independent_missing_events`: тематический pass вправе первым обнаружить сильный agency-материал. При этом `major_agencies` всё равно обязан завершить свою search operation и иметь хотя бы один consulted source, а общий anti-junk gate по источникам не ослабляется.

## Paid-stage recovery and image provenance

A validated digest is a paid-stage checkpoint. Once `Validate publishable story
count and short digest marker` has succeeded for a publication date, a later
cover/build/commit/deploy failure must not cause Primary, Hybrid, Coverage or
editorial to be repaid automatically. Recovery must reuse the highest-completeness
non-expired artifact and resume from the first incomplete stage. A successfully
validated cover is a still later checkpoint; FTP-only failure must reuse the
committed release instead of regenerating research or the cover.

Image provenance uses separate identities. `image_request_id` is mandatory for
the image operation. `source_editorial_request_id` is optional provenance and
must never block an otherwise valid recovered digest from reaching the Images
API. Never fabricate an editorial ID from an image ID. A real Images API call
should preserve the provider `x-request-id` when available. Image failures must
be classified as local preflight, transport/HTTP, or response/contract failures
so operators can distinguish a zero-cost metadata failure from a billable API
attempt. Automatic image retries remain disabled; one production cover means at
most one Images API call unless an operator explicitly starts a new recovery run.

## Fresh-agency coverage rescue

For modern production artifacts with a non-zero candidate pool, source-health
may require one bounded last-mile agency corroboration after all six mandatory
Coverage directions complete. Use only the otherwise free seventh Coverage
search slot. Zero-pool recall sentinel v8 and non-zero `fresh_agency_rescue` v7
are mutually exclusive, so the worst-case retrieval ceiling remains 12 Primary
+ up to 4 Hybrid + up to 7 Coverage = 23 completed search operations.

The rescue must target one existing high-significance agency-likely event, not
open a new broad discovery stream. Prefer distinctive publisher-neutral factual
anchors for monetary events. It performs exactly one Web Search without an API
domain filter, but acceptance remains strict and fail-closed: the primary URL
must be direct Reuters/AP/Bloomberg/FT, fresh inside the effective window, and
match the target exactly by `organization`, `event_type`, and `published_date`.
A successful corroboration updates the existing candidate primary source,
moves the former primary into supporting sources, and triggers editorial rerun;
it must never create a duplicate story.

Versioned source-health recovery must reuse already-paid mandatory Coverage
passes and spend only the new rescue call when needed. Do not make the presence
of one specific external article in a live search index a deterministic CI gate;
keep live Terra/Web Search checks as retrieval diagnostics while production
acceptance itself remains fail-closed.

## Exact agency cutoff

Fresh-agency evidence must respect the exact saved temporal boundary during
recovery. When a candidate has a timezone-aware `published_at`, compare it
directly with `search_window.start_at/end_at`. A date-only agency source on the
cutoff calendar day is not proof that the article existed before the saved
cutoff and must fail closed. Keep start-day date-only compatibility for the
bounded healing overlap, but never let a later same-day recovery import
post-cutoff agency evidence.


## Regression rule: terminal agency source-health (2026-08-16)

Не превращать отсутствие свежего Reuters/AP/Bloomberg/FT кандидата в самостоятельный fatal gate, если обязательный `major_agencies` pass и bounded Coverage/rescue технически завершились. Terra/web-search ranking недетерминирован: такой zero-result должен сохраняться как заметный source-health warning, после чего решение о публикации принимают обычные editorial/validation gates. При этом незавершённый обязательный agency search, сломанный search contract, неполный Coverage audit и невалидная временная привязка найденного evidence остаются fail-closed. Не увеличивать search budget ради компенсации ranking-недетерминизма без отдельного проверенного архитектурного решения. В pipeline diagnostics приоритет имеет наиболее поздний фактически достигнутый terminal stage; recovery не должна маскировать последующую normalization/validation ошибку. Для subprocess editorial rerun всегда сохранять captured child output в JSON diagnostics.

## Retrieval Quality v1

- Не терять потенциально крупный `unverified` discovery: сохранять его в `unresolved_signals`; обязательный resolver разрешён только для strict high-signal evidence, слабые сигналы не блокируют выпуск.
- `entities`, `anchors`, `source_hint` являются hints/evidence, а не обязательными поисковыми фильтрами. Запрещено превращать их в company whitelist, publisher whitelist или длинный AND-query.
- Targeted unresolved resolution использует только существующий 7-й Coverage slot, source-neutral Web Search и не увеличивает Coverage budget выше 7.
- Приоритет adaptive Coverage slot: сначала обязательный technical retry; затем high-signal unresolved resolution; если unresolved нет, действуют существующие fresh-agency rescue / zero-pool sentinel правила.
- Russia/Asia zero-result проверяется как completeness-health через существующий optional 4-й Hybrid slot. Это не региональная story quota: отсутствие достойной новости после достаточного поиска является допустимым результатом.
- Общий production search ceiling остаётся 23: 12 Primary + до 4 Hybrid + до 7 Coverage.
- Modern full recovery без `retrieval_quality_contract_version=1` понижать до partial editorial recovery: переиспользовать уже оплаченные валидные mandatory-проходы и выполнить отсутствующий quality-slot, а не повторять весь research.
- Recovery artifacts привязаны к точной дате `daily-production-YYYY-MM-DD`; не переносить terminal/research artifacts между календарными выпусками.
- Live Terra smoke применять как диагностическую проверку query architecture. Не требовать конкретную live Reuters/AP/Bloomberg/FT URL в deterministic CI.
