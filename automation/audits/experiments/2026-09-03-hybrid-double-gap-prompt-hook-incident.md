# Hybrid v3 clean-process prompt-hook incident — 2026-09-03

## Production incident

Failing scheduled run: `33702310841`, head `cf2e9c2bcf3be2c311a12f05b536b6bb1c24d570`.

The paid Primary stage completed all 12 mandatory searches and produced 14 final
candidates. Source Freshness reduced the eligible set from 14 to 12. The first
editorial pass was provisional because it selected three stories whose primary
publisher was HuggingNews without a required diversity override.

The saved Primary report simultaneously had both Search-derived regional gaps
open:

- China/Asia: `accepted_candidates=0`, `health_check_needed=true`;
- Russia: `accepted_candidates=0`, `health_check_needed=true`.

That state activates the exceptional Hybrid v3 path with an approved maximum of
five Hybrid searches. Before the first Hybrid search was made, production emitted:

`AttributeError: module 'hybrid_search_completeness_v1' has no attribute 'build_prompt_original'`

No Hybrid report was written and the coverage/editorial completion path later
failed again on the same HuggingNews diversity violation.

## Root cause

Hybrid v2 introduced a compatibility hook in the Aug-28 conditional-fifth-Hybrid
work. `v2.build_prompt()` reads `legacy._base.build_prompt_original`, while
`v2._ensure_original_prompt_hook()` creates that attribute from the preserved v1
base prompt.

Normal v2 execution calls the initializer before temporarily monkeypatching the
base prompt. The stable public wrapper's own `build_prompt()` also calls the
initializer.

The exceptional v3 double-gap implementation, however, directly calls
`v2.build_prompt()` for its three broad passes. In a clean production process no
normal v2 path had necessarily run first, so `build_prompt_original` could still
be absent. The conditional fifth-search branch therefore depended on incidental
module state/test order.

This is a latent defect from the Aug-28 Hybrid v3 implementation, not a regression
introduced by Sep-2 PRs #140 or #141. Comparing the Sep-2 publication commit
`19e329c55d55b013586e331c36dc9afa4cb5137b` with the post-#141 main commit
`4c4b5da7b4a1cf36d85f8ea6c4a859cefa5d25a3` shows no Hybrid, editorial, query,
routing, freshness or candidate-selection source files changed by those two PRs.
They added Discovery Health / Primary outcome diagnostics and status reporting.

## Fix

The stable public Hybrid wrapper now initializes v2's preserved original-prompt
hook inside `_sync_compatibility_hooks()` before delegating any execution to v3.
This preserves all existing versioned modules and monkeypatch/recovery surfaces.
No query text, ranking, candidate validation, freshness, regional-gap trigger,
search allocation or publication semantics change.

A clean-state regression deliberately removes `build_prompt_original`, installs a
sentinel preserved base prompt, runs the public compatibility sync, and then calls
`v2.build_prompt()`. The test verifies that the original prompt is restored before
the v3 path can use it and that the Hybrid/pipeline ceilings remain 4/5 and 24/25.

## Separate editorial failure

The HuggingNews diversity failure is independent of the Hybrid exception. The
saved Sep-3 candidate artifact contains 13 candidates, five with primary publisher
`HuggingNews`. The model selected seven stories, including three HuggingNews rows,
with an empty `diversity_overrides` list. The existing editorial validator correctly
rejected that output.

This incident fix does not weaken the diversity guard and does not change Primary
source routing. A same-day recovery should reuse the already-paid artifact after
the code fix rather than repeat Primary research.

## Cost and invariants

- production API spend used for this regression work: `0`;
- new OpenAI calls: `0`;
- new Web Search operations: `0`;
- Primary remains exactly 12 searches;
- Agency Rescue remains max 1;
- Hybrid remains max 4 normally and max 5 only for simultaneous Asia+Russia gaps;
- Coverage remains max 7;
- whole-pipeline ceiling remains 24 normally / 25 on the approved double-gap path;
- Source Freshness, Event Freshness, archive dedupe and recovery at-most-once rules are unchanged.
