# 2026-09-22 short-selection publisher-override incident

Status: controlled zero-paid incident replay and proposed deterministic remediation.

## Production failure

- workflow run: `35676364066`
- exact production head: `fefb11c504a93b9ca1c964db9d46c5c293613fd6`
- failure stage: mandatory Coverage / editorial completion
- final validator error: `Издатель 'techcrunch' представлен 3 сюжетами без diversity override с причиной.`
- saved final research pool: 13 candidates
- saved editorial selection: 5 stories
- selected TechCrunch primary-publisher stories: `cand-001`, `cand-002`, `cand-003`
- Coverage: 6/6 required directions, 7/7 allowed searches, 0 added candidates
- production API spend was already incurred by the failed run; this remediation replay uses 0 new OpenAI calls and 0 Web Search operations.

## Root cause

Two deterministic publisher repairs already existed, but neither owned this shape.

1. The preserved short-pool repair runs only when the complete baseline-eligible
   pool is below the normal target of 7. The saved Sep22 pool has 13
   baseline-eligible candidates, so that guard correctly stayed closed.
2. The active full-pool repair requires a normal-size selection plus stronger
   score/recommendation conditions. Sep22 editorial intentionally returned a
   5-story short digest, so that guard also stayed closed.

The editorial model nevertheless explicitly partitioned all 13 candidates into 5
selected and 8 excluded, marked `short_digest=true`, emitted a non-empty
`low_news_volume` reason, selected every baseline-eligible
`recommendation=include` candidate, and chose three independent TechCrunch
primary-source events. It omitted only the mechanically required reasoned
publisher override. The protected editorial completion made one additional text
response but omitted the override again, so the canonical validator correctly
blocked publication.

## Proposed bounded remediation

Add a complementary zero-paid normalizer in the active
`editorial_policy_runtime.py`. It never changes selected/excluded IDs and does
not touch retrieval. It may synthesize exactly one missing publisher override only
when all of these guards hold:

- selected count is 1-6 while baseline-eligible count is at least 7;
- `short_digest=true`, non-empty `low_news_volume`, and non-empty
  `selection_summary`;
- selected/excluded IDs are a complete non-overlapping partition of the current
  candidate IDs;
- every baseline-eligible `recommendation=include` candidate is selected;
- exactly one publisher exceeds the soft cap, by exactly one story;
- that publisher's selected stories are baseline-eligible
  `include|consider` with distinct primary subjects and primary URLs;
- no reasoned override for that publisher already exists.

The preserved true-short-pool repair remains unchanged and owns its original
case. The existing full-pool repair remains unchanged and owns its original case.

## Offline replay

Assistant-owned replay used only the saved Actions artifact.

Baseline on the Sep22 shape:

- deterministic short-pool repair: no change because eligible count is 13;
- deterministic full-pool repair: no change because selection count is 5;
- publisher validator: FAIL on 3× TechCrunch without override.

Proposed guard:

- adds one reasoned `publisher=TechCrunch` override;
- keeps all 5 selected IDs and all 8 excluded IDs byte-for-byte in the same order;
- publisher diversity validation becomes clean.

Negative controls remain fail-closed:

1. an unselected baseline-eligible `include` candidate;
2. missing `low_news_volume`;
3. incomplete selected/excluded partition;
4. repeated primary subject inside the over-cap publisher group;
5. normal seven-story selection;
6. genuinely short eligible pool, which remains owned by the preserved base path.

No Terra experiment is applicable because query wording, provider/domain routing,
ranking, search allocation and search counts do not change. No production API or
paid Web Search was used for this remediation validation.
