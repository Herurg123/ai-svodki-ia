# Primary raw-zero outcome diagnostics P1 — 2026-09-02

## Problem

Primary Recall persists `raw_candidates`, model rejection rows, validator
rejections and provider `action.sources`, but the ordinary operator view reduces
many different outcomes to `raw=0`. That makes source-pool, model-output and
post-model failures look identical.

This P1 changes diagnostics only. It does not modify Primary search execution,
queries, domain routing, candidate validation, ranking, freshness, editorial,
recovery, publication or search budgets.

## Exact production replay

Control artifact:

- run: `33577674132`;
- artifact: `9827509780`;
- publication date: `2026-09-02`;
- Primary searches completed: `12/12`;
- raw-zero Primary directions: `8`.

The compact replay fixture is
`automation/fixtures/recall/primary-raw-zero-2026-09-02.json`.

Every saved raw-zero lane had:

- a completed one-search Primary pass;
- non-empty `consulted_sources` / `action.sources` metadata;
- one or more model rejection rows;
- zero raw candidate rows;
- zero validator rejections, because no candidate reached the validator.

The eight lanes were:

- `major_agencies`;
- `models_products_agents`;
- `infrastructure_chips_cloud`;
- `business_investment_partnerships`;
- `china_asia_models`;
- `china_asia_integrations`;
- `security_safety`;
- `legal_regulation`.

Under P1 they classify as `model_rejections_only`, while preserving
`source_metadata_state=present` and the consulted-source count.

## Important non-claim

`model_rejections_only` is a **response-shape diagnosis**, not event-level
causality. It means the model returned rejection rows and no candidate rows for
that pass. It does **not** prove that a particular independently missed event was
present in the provider source pool, nor that the model explicitly saw and
rejected that exact event.

This distinction matters for the four Sep-2 hard misses. The saved artifact still
does not contain their exact URLs/events in retrieval traces, so the supported
root cause remains upstream retrieval/ranking/source-routing incompleteness. P1
only makes the lane-level response anatomy less ambiguous.

## Outcome vocabulary

`primary_zero_outcome.py` classifies saved directions into:

- `technical_incomplete`;
- `candidate_accepted`;
- `validator_rejected_all`;
- `raw_candidate_not_accepted`;
- `model_rejections_only`;
- `provider_sources_present_no_candidate_or_rejection`;
- `provider_source_pool_empty`;
- `provider_source_metadata_unavailable`.

An explicit `action.sources=[]` is distinguishable from missing/null source
metadata. A non-empty provider source list is also retained separately from model
output state.

## Integration

The classifier is embedded under the already-existing Discovery Health Primary
lane in final `pipeline-status.json`:

`discovery_health.lanes.primary.details.primary_outcome_diagnostics`

Raw-zero outcome labels are informational. They do not change Primary health by
themselves and are not a publication gate.

## Cost / invariants

- OpenAI calls added: `0`;
- Web Search operations added: `0`;
- network calls added: `0`;
- Primary remains exactly `12` searches;
- Agency Rescue remains max `1`;
- Hybrid remains `4`, conditional `5` only for double regional gap;
- Coverage remains max `7`;
- whole-pipeline ceilings remain `24 / conditional 25`.

The replay uses only the saved production artifact and offline tests.
