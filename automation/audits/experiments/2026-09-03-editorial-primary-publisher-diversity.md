# 2026-09-03 editorial primary-publisher diversity incident

## Scope

This note records the second failed same-day recovery for production run
`33714393042`, using the saved paid artifact from original run `33702310841`.
Regression work is offline and uses zero OpenAI calls and zero Web Search
operations.

## Observed failure

Manual recovery correctly restored the paid artifact and did not rerun fresh
Primary research. The saved artifact was classified as `partial_editorial` and
Coverage required editorial completion. The editorial rerun then failed the
existing diversity validator:

`Издатель 'huggingnews' представлен 3 сюжетами без diversity override с причиной.`

The rerun selected seven stories, including three candidates whose
`primary_source.publisher` was `HuggingNews`. One of those candidates also had an
Axios supporting source and the generated article could cite Axios, but the
canonical validator correctly counts publisher diversity by the selected
candidate's primary source, not by a supporting or displayed citation.

## Root cause

The deterministic validator was correct. The editorial prompt already stated the
soft two-story publisher limit but used the human phrase "от одного издателя"
without making the identity field explicit. Because a candidate can carry both a
primary source and supporting sources, the model could treat the displayed
supporting citation as publisher diversification even though the validator uses
`primary_source.publisher`.

The second recovery proves this is repeatable model interpretation, not a single
malformed response: the rerun changed the selected HuggingNews story but still
returned three HuggingNews-primary candidates and no publisher override.

## Fix under test

The existing machine-readable editorial policy, which is embedded verbatim into
every editorial prompt, now states explicitly:

- publisher identity field is `primary_source.publisher`;
- `supporting_sources` do not change publisher identity;
- the source cited in `article_html` does not change publisher identity;
- before returning JSON, the editor must recount `selected_candidate_ids` by
  `primary_source.publisher`;
- an over-cap full-pool selection must either replace an excess comparable story
  or provide the already-required reasoned publisher `diversity_override` for
  independently high-significance events.

No deterministic full-pool override is synthesized. The existing validator stays
fail-closed.

## Exact regression shape

The test fixture reproduces today's ambiguity:

- `cand-002`: primary `HuggingNews`;
- `cand-006`: primary `HuggingNews`, supporting `Axios`;
- `cand-010`: primary `HuggingNews`.

Expected result without override remains exactly one publisher-diversity error for
three `huggingnews` primaries. A non-empty reasoned publisher override remains the
only accepted exception in that synthetic full-pool shape.

## Architecture and budget audit

Unchanged:

- Primary: 12 mandatory searches;
- Agency Rescue: at most 1 search;
- Hybrid: 4 normally, conditional 5 only for simultaneous Asia+Russia gaps;
- Coverage: at most 7 searches;
- pipeline ceilings: 24 normally / 25 conditional;
- Event Freshness and Source Freshness contracts;
- candidate schema and research ranking;
- Source Pulse registry and polling;
- publication validation and diversity validator;
- recovery at-most-once semantics.

The fix adds no API call, no Web Search operation and no automatic editorial
retry. A later manual recovery will use the same existing one-editorial-call
completion path rather than introducing a new paid retry mechanism.

## Documentation impact

No topology, workflow, search-budget or public publication contract changes. The
existing README/architecture description of editorial validation and diversity
remains accurate; this change only makes the already-enforced publisher identity
explicit inside the machine-readable editorial policy supplied to the model.
