# 2026-09-03 full-pool publisher diversity runtime repair

## Incident

Production recovery run `33716335547` ran on `main` commit
`b63cb1c7de8799cf8c87696b80076399b7ca2e2d`, so the prompt/policy clarification
from PR #143 was definitely active. Recovery reused run `33714393042`, skipped
fresh Primary research and did not perform any Coverage Web Search operation.
The one required editorial completion call nevertheless returned seven selected
stories with three candidates whose `primary_source.publisher` was
`HuggingNews`, plus no publisher diversity override.

The existing validator correctly stopped publication with:

`Издатель 'huggingnews' представлен 3 сюжетами без diversity override с причиной.`

## Why PR #143 was insufficient

The exact `editorial-prompt-input.txt` saved by run `33716335547` contains all
three machine-readable instructions added by #143:

- publisher identity is `primary_source.publisher`;
- `supporting_sources` and the displayed article citation do not change publisher
  identity;
- the editor must recount `selected_candidate_ids` by primary publisher before
  returning JSON.

Therefore this failure is not a deployment/configuration miss. The model received
the rule and did not comply. A static prompt-contract test can prove that the rule
was supplied; it cannot prove that a probabilistic model will obey it on every
response.

## Exact saved replay

The compact offline replay fixture is
`automation/fixtures/recall/editorial-full-pool-publisher-2026-09-03.json` and is
derived from artifact `9878662137` of run `33716335547`.

Selected HuggingNews-primary candidates had significance scores:

- `cand-002`: 4, Tencent;
- `cand-006`: 4, Meta;
- `cand-008`: 3, Perplexity.

They are distinct primary subjects and distinct primary URLs. The best unselected,
baseline-eligible candidates from **other publishers** had significance score 2:
`cand-003` (Havoptic), `cand-011` (TechCrunch) and `cand-013` (Havoptic).
Additional unselected HuggingNews candidates do not provide publisher diversity.

The canonical editorial specification already says that, for a normal 7-12 story
pool, publisher caps are soft balancing factors among comparable candidates and
that independent sufficiently significant events may be retained with a reasoned
`diversity_override`. In this exact pool no different-publisher alternative is
comparable by the existing significance score.

## Runtime repair

The active runtime now performs a zero-paid deterministic normalization before the
existing editorial validator. It does **not** change selected story IDs. It may add
one publisher override only when all of these conditions hold:

1. the baseline-eligible pool and selected set both meet the normal target;
2. exactly one publisher is over the soft cap;
3. the excess is exactly one story;
4. no reasoned publisher override already exists;
5. every selected story of that publisher is `include`, baseline eligible and has
   `significance_score >= 3`;
6. the over-cap stories have distinct primary organizations and distinct primary
   source URLs;
7. every unselected baseline-eligible candidate from another publisher has a
   strictly lower significance score than the weakest selected over-cap story.

If any guard fails, no repair is made and the canonical validator remains
fail-closed. Organization diversity is never synthesized by this repair.

## Regression layers

The incident is now covered at three levels rather than only prompt text:

- contract: the canonical validator still rejects three same-publisher stories
  without a reason;
- exact artifact replay: the Sep-3 saved selection is deterministically repaired
  and then passes the unchanged publisher validator with zero API/search calls;
- negative boundaries: equal-strength alternative, repeated primary subject,
  over-cap by more than one, non-`include` over-cap story and existing override do
  not trigger repair; an unrelated organization-diversity violation remains an
  error after publisher repair.

This is the important testing distinction for LLM pipelines: prompts are tested as
inputs, while enforceable invariants are tested as deterministic runtime behavior.

## Budget and recovery invariants

Regression and repair use:

- OpenAI calls: 0;
- Web Search operations: 0;
- network calls: 0.

No Primary, Agency Rescue, Hybrid or Coverage budget changes are introduced. No
new editorial model retry is added. The same-day recovery path continues to reuse
the already-paid artifact; after this change the invalid publisher reason is
normalized locally before validation instead of spending another model call just
to ask for the missing explanation.

## Internal compatibility split

The previously established deterministic editorial runtime corrections are kept
unchanged in `editorial_policy_runtime_base.py`; the active
`editorial_policy_runtime.py` re-exports that behavior and layers the new repair on
top. This base is an active compatibility dependency, not an inert archive. It
should be re-audited for consolidation on the next material editorial-runtime
refactor or after 2026-10-03.

## Documentation impact

The canonical editorial specification and production topology do not change. The
runtime now deterministically implements an exception already documented in
`automation/specs/editorial-policy.md`; search/recovery/publication topology is
unchanged. README and `automation/ARCHITECTURE.md` remain accurate at their
current level of detail.
