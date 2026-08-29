# P4 regional-health viability and retrieval architecture audit — 2026-08-29

## Scope

P4 addresses a false-healthy regional retrieval state reproduced from production
run `33231413963`, artifact `9708618496`, SHA256
`b44c096424badb504e9e04be83db589f98cd80699ad4125cbedc051f0b6fe4e0`.
The effective window was `2026-08-27T04:43:51+03:00` →
`2026-08-29T05:16:40+03:00`.

The goal is not a Russia/China publication quota. The goal is narrower: if
Primary marked a regional route healthy only because candidates existed early,
and those exact Primary regional candidates later become non-viable after the
existing final-cap, Event/Source Freshness and editorial filtering, Hybrid must
see that Search-derived gap as open again.

P4 changes no search query text, provider/domain routing, source registry,
Coverage direction, model prompt, candidate ranking policy, freshness policy or
archive dedupe rule. No Terra/provider ranking experiment is required for the P4
patch itself because no query semantics change. No Terra-specific assistant tool
is exposed in this session, and no production API/Web Search was spent.

## Exact code path and root cause

Primary `regional_health` is created in `primary_recall_search.py` from per-pass
`accepted_count`:

- China/Asia uses `china_asia_models` + `china_asia_integrations`;
- Russia uses `russia`;
- `health_check_needed = primary_completed and accepted_candidates == 0`.

That annotation is copied into the research artifact before Source Pulse and the
first editorial. Source Pulse is intentionally forbidden from closing a Search-
derived regional gap.

The trusted research then passes deterministic Event Freshness and fail-closed
Source Freshness before the first editorial. `candidates.json` therefore already
contains the post-freshness/editorial recommendations when the stable Hybrid
entrypoint is reached.

Before P4, Hybrid v2/v3 read the old `regional_health` flag unchanged. A region
that was early healthy remained healthy even if every Primary regional candidate
was later excluded. Hybrid therefore could skip its dedicated regional health
search on a stale signal.

## Production-derived reproduction

Machine-readable fixture:
`automation/fixtures/recall/regional-health-viability-2026-08-29.json`.

Production shape:

- Primary Asia accepted candidates: 2;
- early `health_check_needed=false`;
- controls: GLM-5.3-Flash and Qwen-MT-Image 2.0;
- independent release audit established the GLM event origin outside the effective
  window; P1 now deterministically rejects that stale origin when reliable event
  evidence is present;
- Qwen is represented as editorial/source-filter excluded in the P4 replay;
- viable Primary Asia candidates after filtering: 0;
- Russia was already a Search-derived gap.

Expected P4 result:

- Asia re-opens `false → true`;
- Russia remains `true`;
- effective pre-Hybrid gaps become `asia + russia`;
- existing Hybrid v3 double-gap branch may use five searches rather than four;
- this is the already-approved conditional fifth Hybrid slot, not a new slot;
- pipeline maximum remains 25 on that path and 24 otherwise.

## Minimal implementation

`regional_health_viability.py` is pure deterministic logic. It uses Primary
provenance rather than geographic keyword heuristics:

1. collect raw candidates from the region's original Primary directions;
2. intersect them with `primary-recall.json.final_candidates`, so an early
   direction `accepted_count` cannot hide a candidate dropped by the Primary
   final cap;
3. match those exact final Primary regional candidates against current
   `candidates.json`; when both rows expose source URLs, shared source URL is
   authoritative, while normalized-title equality is only a compatibility
   fallback when source identity is absent on at least one side;
4. count a current row as viable only when its recommendation remains
   `include|consider` and it is not explicitly event-stale / `old_reprint`;
5. if all exact Primary regional candidates are deterministically matched and none
   is viable, re-open the gap;
6. if provenance/identity is incomplete, preserve the prior state instead of
   spending an extra search on uncertainty;
7. if a Primary Search gap was already open, never close it.

The source-first identity rule is deliberate. A Pulse-only or later copy with the
same title but a different URL cannot impersonate the Primary candidate and keep
a weak Search route marked healthy.

The stable `hybrid_search_completeness.py` runs this refresh immediately before
calling preserved Hybrid v3. It persists only the updated regional-health
metadata in `candidates.json`, so v3 consumes the correct gaps without rewriting
preserved v2/v3 implementations.

## Controlled offline experiment

Regression scenarios:

| Scenario | Expected |
| --- | --- |
| Asia early healthy; GLM stale; Qwen excluded | Asia re-opens |
| One exact Asia Primary candidate remains `consider` | Asia stays healthy |
| Same title but different source URL appears later | cannot impersonate Primary; prior state is preserved if identity is incomplete |
| Russia already Search-gap; later unrelated/Pulse Russia candidate exists | Russia stays gap |
| Primary/current identity cannot be proven | prior healthy state preserved |
| regional candidate accepted by a pass but absent from Primary final cap | region re-opens |
| event origin `unknown`, recommendation `include` | candidate remains viable |

The fixed production-derived case changes the effective Hybrid trigger from a
single Russia gap to a double Russia+Asia gap. This improves recall by spending
only the already-approved conditional fifth Hybrid operation. No new permanent
search is created.

## Architecture-wide non-regression audit after P1–P4

### Discovery stages and ceilings

Unchanged stage inventory:

1. Primary Recall: exactly 12 mandatory one-search passes.
2. Source Pulse v1.3: fixed-source HTTPS plane, 0 OpenAI / 0 Web Search.
3. Agency discovery rescue v5: at most 1 Reuters-only global search.
4. Hybrid v3: maximum 4 normally; maximum 5 only for simultaneous Russia +
   China/Asia Search-derived gaps.
5. Coverage: existing directions only, maximum 7 search operations.

Ordinary theoretical maximum remains `12 + 1 + 4 + 7 = 24`.
Double-gap theoretical maximum remains `12 + 1 + 5 + 7 = 25`.
P4 adds 0 query slots and 0 new Coverage directions.

### Recall and breadth

P4 does not remove or narrow any existing broad query. P3's representative
Russia/China/agency anchors remain unchanged. On the double-gap route, existing
Hybrid v3 still preserves all three broad Hybrid passes and adds the two dedicated
regional checks; P4 can only make that already-designed recovery path reachable
when early candidates became invalid.

Therefore P4 cannot reduce broad retrieval breadth. The only routing delta is
false-healthy → gap reopening.

### False-positive controls

P4 does not promote any candidate and does not alter editorial recommendation.
It cannot make a stale/unverified story publishable. It only decides whether an
existing regional health-check should run. Event Freshness P1 and fail-closed
Source Freshness remain authoritative.

### Source Pulse interaction

An already-open Search-derived gap is immutable in P4. A Pulse-only or unrelated
later candidate cannot close it. For an early-healthy region, only the exact
Primary regional candidates used for provenance can keep the region healthy.
When source URLs exist, a later same-title copy on a different URL is not treated
as that Primary candidate. This preserves the two-plane architecture and prevents
Pulse from masking a weak Primary route.

### P2 Yandex interaction

P4 does not parse dates and does not touch the Yandex first-party adapter. A
Yandex candidate that P2 successfully keeps viable can continue to count only if
it was one of the exact Primary regional candidates being assessed; a separate
Pulse-only Yandex candidate cannot close an existing Search gap.

### P3 routing interaction

No P3 query is changed. The global Reuters rescue remains v5. Russia and Asia
Hybrid queries remain the P3 representative queries. P4 only determines whether
an existing regional slot is warranted after deterministic viability filtering.

### Coverage

Coverage remains unchanged. No general Russia/China breadth directions are added.
The existing `security_russia`, `security_asia`, global legal/copyright, curiosity
and `general_coverage_gaps` directions remain the only Coverage surfaces.
Regional health metadata therefore improves Hybrid recovery rather than silently
turning Coverage into a new regional quota/search layer.

### Recovery / at-most-once

P4 performs no paid operation itself. The refresh is inside the fresh stable
Hybrid entrypoint and runs before Hybrid search. Same-day recovery still does not
repeat completed Hybrid retrieval. The agency recovery bridge remains on rescue
v5 and is not changed by P4. P4 therefore does not weaken at-most-once paid-stage
semantics.

### Failure mode

Missing/malformed Primary provenance or ambiguous candidate identity is fail-
neutral for spend: the previous health flag is preserved and P4 records
`not_available` / `identity_incomplete_preserved`. It does not open a search based
solely on an uncertain match.

## Cost / latency effect

Maximum cost and latency do not increase. Actual use of the existing fifth Hybrid
slot can become more frequent in the specific case where one region was already
a gap and the other region re-opens after viability filtering. That is the
intended P4 recall correction and remains inside the previously approved 25-search
conditional ceiling.

## Conclusion

The retrieval architecture is not made narrower or less robust by P4. P1–P4 now
cover complementary failure classes:

- P1 rejects reliably proven old events despite fresh pages;
- P2 prevents fresh Yandex first-party events from being lost to date parsing;
- P3 improves provider/query routing without adding search slots;
- P4 prevents early regional candidate counts from suppressing existing Hybrid
  recovery after those candidates fail deterministic/editorial viability.

The remaining empirical uncertainty is provider ranking itself. P4 does not claim
to prove that Tencent Hy4 will rank on every live run; it ensures that the
regional recovery route is no longer skipped merely because invalid earlier
candidates once existed.
