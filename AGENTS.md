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
must not edit tracked
project files, `main`, releases, tags, permanent archive branches, or
published/editorial content. The five-merged-PR branch grace is also capped at
7 days, so quiet periods cannot protect stale refs forever. Closed-unmerged
branches may age into `safe_delete` after 14 days only when their current HEAD
still exactly matches the closed PR head. An orphan workflow absent from current
`main` whose latest run was on the default branch may be disabled once it has no
live run; absence from current `main` is the canonical proof that the workflow
was removed. An active orphan workflow with no runs may also be disabled on the
same canonical-absence proof; already-disabled no-run workflow metadata is
report-only. GitHub-managed dynamic Pages workflows are diagnostic objects:
when Pages is disabled they must not be sent to the normal workflow-disable REST
endpoint, which GitHub rejects for this platform-managed workflow.

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

## Primary recall v2 contract

Fresh production research uses deterministic **Primary Recall v2** instead of
letting one agentic Responses call allocate the entire 12-search budget. The
hard primary budget remains exactly twelve completed Web Search operations, but
each operation is assigned to one mandatory direction and each Responses call
gets `max_tool_calls=1`:

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

Do not collapse the two China/Asia passes back into one broad regional search
without a new recall experiment and explicit approval. The 2026-08-11
regression showed that a broad China pass found the other control events but
missed the Apple/Qwen product-integration story; a separate integrations /
partnerships pass recovered it without increasing the 12-search primary budget.
The historical benchmark is `automation/fixtures/recall/2026-08-11.json`.

Primary is **discovery-first**. A pass should surface plausible meaningful
fresh events into the candidate pool, using `consider` when final significance
is uncertain, rather than performing aggressive editorial rejection during
retrieval. Strict window, source, freshness, legal/curiosity, significance and
deduplication checks still run through the existing story-coverage validator and
editorial stages after discovery.

All twelve directions are mandatory for a fresh production run. A technical
failure or incomplete Web Search in any direction is a red, fail-closed primary
failure and must never be reinterpreted as a low-news day. A completed direction
may legitimately return zero candidates. Primary diagnostics must preserve the
actual queries, consulted sources, raw candidates, model rejections and
validator rejections for each direction.

The final `independent_missing_events` pass receives a compact list of already
found candidates and explicitly searches for significant events absent from the
pool. It is a last-mile recall check, not another editorial filter.

Primary Recall v2 is injected into the existing generator through its
`--research-input` interface so editorial policy and artifact validation remain
shared with recovery. A caller-supplied `--research-input` still means recovery
or editorial rerun and must skip paid fresh primary. The internally generated
primary research-input is different: it represents fresh paid primary and may
be followed once by hybrid completeness. Recovery must not repeat already paid
primary work.

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
Web Search operations. Each pass gets `max_tool_calls=1`; API domain filtering
is deliberately disabled, and source quality is validated after retrieval.

New candidates are merged through the existing strict story-coverage validator
and editorial is rerun only when at least one candidate is actually accepted.
The completeness layer never runs recursively for caller-supplied
`--research-input` editorial reruns or recovery, so already-paid
primary/completeness work is not repeated. A transport or
completeness-editorial failure must preserve or restore the completed primary
artifact and remain diagnostic rather than destroying an otherwise publishable
primary result. Short/empty pools still proceed to the existing mandatory
six-direction coverage audit and zero-pool recall sentinel.

The total retrieval ceilings remain **12 primary + up to 4 hybrid + up to 7
fallback coverage = 23 completed search operations** in the theoretical worst
case. Improving recall must not silently raise these limits.

## Editorial zero-pool stop

A completed zero-pool result is a normal successful `no-publish`, not a
production failure, but only after the current temporal-anchor contract, all
six mandatory coverage directions, and the current recall sentinel have
completed successfully with no publishable candidate. In that state Image API,
commit, and deploy must remain skipped. Technical partial/error audits remain
fail-closed and red. Recovery must reuse a proven completed editorial stop
without repeating paid research or coverage.
