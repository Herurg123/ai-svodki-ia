# 2026-08-24: false-zero agency retrieval and manual recovery audit

## Scope

Independent audit of scheduled production run `32674034063` at main commit
`ca1cd7f4b2acaf429f0a1dd9d9fc4bc6b9a0ff6d`, plus a bounded assistant-side
source-routing experiment. No user production API key was used.

The interactive environment did not expose a standalone Terra control for an
isolated `medium` versus `high` `search_context_size` A/B. Assistant-side web
search was therefore used only for independent source-discovery controls; the
production Terra artifact remains the source of truth for the failed run.

## Production artifact facts

Artifact: `daily-production-2026-08-24`.

Effective discovery window:

- start: `2026-08-22T02:35:04+03:00`;
- continuity anchor: `2026-08-23T02:35:04+03:00`;
- end/cutoff: `2026-08-24T02:35:38+03:00`.

Search accounting:

- Primary: 12;
- agency discovery rescue: 1;
- Hybrid: 4;
- Coverage: 7;
- total: 24.

Final candidate pool: 0. Coverage ended in a completed usable zero-pool
`editorial_stop`.

`major_agencies` already used provider-level routing for Reuters, Bloomberg, FT,
AP News and AP. Its exact query was
`latest AI chips infrastructure financing earnings business deals policy security`.
The ranked source list nevertheless contained predominantly stale Bloomberg
pages from March-May 2026, one old AP layer and old FT PDFs, with no useful fresh
Reuters result.

The existing `agency_discovery_rescue` triggered on `major_agencies_raw_zero`,
performed exactly one source-open search using
`latest Reuters AP AI chips infrastructure financing earnings business deals`,
and added nothing. Its 26 consulted sources were dominated by Investing,
TradingView, Yahoo, MarketScreener, WTAQ, AOL, Reddit and old documents. Direct
fresh Reuters discovery did not reach candidate validation.

Source Freshness Proof saw zero candidates: `eligible_before=0`,
`eligible_after=0`, `excluded_outside_window=0`, `excluded_unverified_freshness=0`.
Therefore the false-zero is not caused by an over-strict freshness rejection.
The defect is upstream source discovery/ranking.

## Out-of-sample positive control

Reuters published the Alibaba share-placement event on 23 August 2026 at
approximately `04:47 UTC`, inside the saved effective window. The placement was
about HK$80 billion / $10.2 billion and the stated use of net proceeds was
full-stack AI, including chips, infrastructure and model development/deployment.
It is a strong AI-business/financing control and was absent from the production
candidate pool.

## Assistant-side bounded comparison

### Baseline

The source-open rescue formulation is not absolutely incapable of returning
Reuters on every replay, but it is unstable and the actual production artifact
shows a polluted ranked pool. That makes it unsuitable as the only bounded
second chance after a known agency quality gap.

### Reuters-only provider route

A single provider-filtered Reuters route with publisher-neutral, date-free query

`latest AI chips infrastructure financing earnings business deals policy security`

independently surfaced the Alibaba placement and recent Reuters regression
controls including Google/Marvell, Broadcom financing, Alibaba earnings and Nvidia
server-pricing. A second publisher-specific search was not required.

A Reuters+AP one-pass variant did not show meaningful positive-control recall
benefit and reintroduced older/unrelated AP results. The minimal source-aware
choice is therefore Reuters-only, still one search.

### Context size

No isolated assistant-side Terra `medium`/`high` A/B was available. The failed
Primary `major_agencies` route already used `high`. Consequently there is no
independent basis to change the rescue from `medium`; this patch deliberately
leaves context size unchanged.

## Negative controls and unchanged fail-closed layers

The patch does not weaken any downstream rule:

- stale Reuters remains rejected by Source Freshness Proof;
- analysis/opinion does not receive Must Include status merely for being Reuters;
- Yahoo/TradingView/MarketScreener syndication is not a direct Reuters source;
- same-event duplicates remain blocked;
- events after cutoff remain ineligible;
- a quiet window may legitimately return zero rescue candidates;
- archive and semantic dedupe, significance and editorial remain unchanged.

## Recovery audit

`daily-production.yml` automatically chooses a reusable same-day artifact when
`recovery_run_id` is absent. A completed usable zero-pool `editorial_stop` from
automatic recovery is terminal-reused without paid APIs. Therefore a plain rerun
after a retrieval hotfix can reuse run `32674034063` and never execute the new
retrieval code.

Minimal operator fix:

- add manual boolean `force_fresh_research`, default `false`;
- apply it only to `workflow_dispatch`;
- when true, skip automatic recovery selection so fresh research may run on
  current `main`;
- reject `force_fresh_research=true` together with explicit `recovery_run_id`
  before paid API work;
- keep scheduled/default recovery unchanged;
- keep `publish=false` as manual dry-run and `publish=true` on the normal publish
  path.

This mechanism is for an explicitly authorized production rerun after merge. It
is not permission to spend user API budget during experiments or debugging.

## Architecture verdict

**Hypothesis A: confirmed.** The 24-Aug false-zero occurred at retrieval/ranking
before candidate freshness validation.

**Hypothesis B: confirmed for the bounded minimal change.** The source-open rescue
is too polluted/unstable; a one-search Reuters-only provider route is a better
independent quality-gap path on the saved regression set. It remains discovery,
not a Reuters quota. Coverage `fresh_agency_rescue` remains same-event
corroboration.

Search ceiling remains exactly **24 = 12 Primary + 1 conditional agency rescue +
4 Hybrid + 7 Coverage**.
