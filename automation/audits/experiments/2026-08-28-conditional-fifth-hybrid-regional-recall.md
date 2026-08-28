# Controlled experiment: conditional fifth Hybrid regional recall

Date: 2026-08-28

## Question

Would one additional Hybrid Web Search, used only when Search-derived regional
health simultaneously reports zero accepted recall for Russia and China/Asia,
improve regional discovery coverage without turning a fifth Hybrid call into the
normal daily baseline?

This experiment evaluates the architecture and triggering contract. It does not
claim a global recall percentage and it does not use the user's production
OpenAI/API budget.

## Compared allocation

Previous zero-extra-cost double-gap allocation:

```text
2 broad Hybrid passes
+ 1 China/Asia pass
+ 1 Russia pass
= 4 Hybrid searches
```

Proposed conditional paid allocation:

```text
3 broad Hybrid passes
+ 1 China/Asia pass
+ 1 Russia pass
= 5 Hybrid searches
```

All other paths keep the existing baseline:

```text
no regional gap: normal Hybrid baseline, usually 3 and at most 4
one regional gap: 3 broad + 1 regional = at most 4
both regional gaps: 3 broad + China/Asia + Russia = at most 5
```

The rest of the pipeline remains unchanged: Primary 12, conditional agency
rescue at most 1, Coverage at most 7, Source Pulse 0 Web Search/OpenAI calls.
Therefore the ordinary theoretical ceiling stays 24 operations and the
conditional double-gap ceiling becomes 25.

## Assistant-owned deterministic state-machine test

A separate assistant-side test enumerated regional health states without calling
the user's production API. The modeled inputs were the two authoritative Primary
flags `asia.health_check_needed` and `russia.health_check_needed`.

Observed allocation contract:

| Asia gap | Russia gap | Hybrid behavior | Maximum |
|---|---|---|---:|
| false | false | normal baseline | 4 |
| true | false | 3 broad + Asia | 4 |
| false | true | 3 broad + Russia | 4 |
| true | true | 3 broad + Asia + Russia | 5 |

Additional boundary cases:

- a lowered baseline cap of 3 does not activate the paid extension;
- an oversized requested limit such as 99 is clamped and cannot create a sixth
  Hybrid search;
- the fifth call is conditional on **both** Search-derived regional flags, not on
  story count, editorial preference, Source Pulse promotion or a publication
  quota;
- Source Pulse promotion does not recompute/erase Primary regional health, so the
  second discovery plane cannot suppress the paid double-gap trigger;
- additional regional Coverage searches are not activated by this experiment.

## Independent retrieval probe

The assistant also ran independent web retrieval checks using assistant-side web
search, not the user's production OpenAI API. Standalone Terra was not exposed in
this environment, so this was **not** a Terra experiment.

The China/Asia regional query surfaced current high-signal China AI material,
including Reuters coverage on 2026-08-27 of Huawei's AI/pharma expansion and a
separate Reuters investigation into China's humanoid-robot/embodied-AI sector.
This supports keeping China/Asia as a dedicated search rather than merging it
with Russia into one mixed query.

The Russian broad query remained much less reliable. Independent source-aware
checks nevertheless confirmed that Russian first-party surfaces can contain
fresh AI events missed by a broad query: the Yandex company-news index currently
shows 2026-08-26 teacher-AI training and 2026-08-24 medical-AI-assistant items.
The registered TASS AI tag is also independently reachable as a named surface,
but direct automated fetch currently returns HTTP 403. This validates the Source
Pulse v1.2 policy: TASS belongs in the reliable Russian source inventory, but a
403 must be recorded as degraded/unavailable rather than converted into a fake
successful poll.

This probe is targeted evidence about retrieval geometry. It is not a complete
reference set and is not used to estimate overall recall.

## Cost boundary

The experiment authorizes exactly one new paid search-operation possibility:

```text
+1 Hybrid Web Search only when both Russia and China/Asia Search gaps are open
```

No new OpenAI model-only stage is added. No extra Coverage search is added.
Source Pulse stays at 0 paid API calls and 0 Web Search operations.

## Deferred options

Two ideas are intentionally recorded but **not implemented**:

1. add 1–2 regional Coverage searches when regional health is still red after
   Hybrid even if digest volume is already sufficient;
2. add a separate LLM semantic-event matcher for difficult deduplication.

Both require future production audits and a separate explicit cost decision.

## Result

**PASS for implementation under the bounded contract.** The conditional fifth
Hybrid operation restores the third broad Hybrid pass on the double-gap path,
while no-gap/single-gap costs remain unchanged. Regression tests must enforce the
trigger and no-sixth-call boundary, and full repository CI must pass before merge.
