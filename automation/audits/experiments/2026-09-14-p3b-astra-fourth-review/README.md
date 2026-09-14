# P3b Astra fourth-review semantic/matrix remediation

Date: 2026-09-14

PR: #175 `Add P3b exact authoritative weak-source binding`

Baseline independently reviewed head: `926e2f66e9d8955f7c1fc717fd4998825ec617b0`.

Independent verdict on that exact head: `REQUEST CHANGES`.

This remediation is intentionally narrow. It does not change retrieval queries, provider/domain routing, Primary, Source Pulse, Agency Rescue, Hybrid allocation, editorial ranking, Event/Source Freshness policy, publication validation or search capacity. Coverage remains six mandatory searches plus at most the existing optional seventh; whole-pipeline ceilings remain 24 normally and 25 only on the existing double-regional-gap Hybrid path. No user production API or paid Web Search is used. Terra is not applicable because the defect and repair are deterministic exact-binding semantics rather than retrieval/query architecture.

## Independent findings

The fourth exact-head review identified three merge blockers on `926e2f66...`:

1. Active binder v4 did not fail closed for several lifecycle uncertainty/state forms when the qualifier followed the action or appeared as an evidential adverb. Examples included `reportedly launched`, `launch expected`, `launch may|might|could happen`, `launch denied`, and GA `planned|cancelled|may happen`.
2. GA/preview contradiction handling was claim-local in a way that permitted an early clean GA claim to return positive before a later exact claim for the same organization/model asserted active preview.
3. The canonical executable 20-case matrix imported historical `weak_source_exact_binding_v2` for direct semantic cases instead of the documented active binder v4. Supplemental active tests existed, but the canonical matrix itself therefore did not prove the active semantic implementation.

## Regression-first reproduction

Commit `d272835e42387aa5006befe103f404a6ecc89ea1` added only `automation/tests/test_p3b_astra_fourth_review.py` with deterministic counterexamples and positive controls; production code was unchanged.

PR Gate #397, run `34876840067`, failed exactly as intended. The new controls produced 14 failures for the reported counterexamples while the pre-existing P3b recovery/Freshness/slot controls remained green. This records an independent red-stage reproduction before implementation changes.

The regression set covers:

- `DeepSeek reportedly launched V4.1 Flash`;
- launch suffix `expected`, `may happen`, `might happen`, `could happen`, `denied`;
- GA suffix `planned`, `cancelled`, `may happen`;
- positive current launch and GA controls;
- `DeepSeek V4.1 Flash general availability. DeepSeek V4.1 Flash remains in preview.`;
- direct active-binder identity checks;
- migration of a positive processed snapshot carrying the prior semantic evidence marker.

## Semantic repair

Active `weak_source_exact_binding_v4.py` is hardened without changing durable request identity or historical v2/v3 modules.

The repair:

- keeps durable `VERSION=2` and the existing P3b mode;
- raises semantic `EVIDENCE_VERSION` from 1 to 2 so a previously positive processed snapshot produced before this hardening cannot be reused as current proof;
- treats evidential uncertainty words such as `reportedly` fail-closed anywhere in an exact candidate claim rather than only before an action token;
- applies post-action state/modal checks across retained lifecycle families rather than only a launch/update-oriented regex subset, covering planned/scheduled/expected/cancelled/denied and modal `may|might|could|would|should` forms;
- delays positive return until all exact local claims have been checked for contradictory active/noncurrent lifecycle evidence;
- keeps GA and preview distinct across multiple local claims, not only inside one sentence/claim;
- prevents one clean same-event claim from overriding a neighboring exact `negated` or `noncurrent` claim such as current GA + GA planned or current launch + launch cancelled;
- deliberately does **not** let historical/background exact claims veto a separately proven current claim; a permanent positive control covers current launch plus a 2025 historical mention;
- preserves strict unknown lexical/numeric/punctuation version-suffix rejection while locally allowing a bounded set of ordinary predicate/linking words such as `remain/remains/stay/stays` after an exact anchor. Historical v2/v3 compatibility vocabulary is not mutated.

The final point matters because the cross-claim counterexample initially remained hidden after the first repair: v3-style fail-closed suffix detection treated `remains` after `V4.1 Flash` as a possible model suffix, so the contradictory preview claim was excluded before conflict analysis. The v4-only prose exception lets that exact claim participate without weakening the existing `v2`, `experimental`, numeric or punctuation variant controls.

A later neighboring self-audit also checked same-action contradictions, not only GA↔preview. Permanent regressions now reject clean-current + planned/cancelled exact claims for the same identity and `launch was reportedly cancelled`, while retaining a current+historical positive control. This closes the same early-positive mechanism without turning historical background into a blanket veto.

## Canonical matrix correction

`automation/tests/test_p3b_regression_matrix.py` now imports `weak_source_exact_binding_v4` for its direct semantic cases. Its active-version contract also verifies:

- public `ensure_story_coverage` owns binder v4;
- active implementation module owns the same binder object;
- durable exact-binding contract remains `VERSION=2`;
- public binder evidence version equals the current v4 evidence marker;
- protected durable optional-slot runner wiring remains intact.

The matrix still contains exactly 20 named canonical cases. Recovery cases 13–16 remain owned by the durable optional-slot suite; rewiring the semantic binder does not create search capacity or alter recovery ownership.

## Recovery evidence migration

Because the previous active binder could admit the fourth-review false positives, merely fixing live evaluation would be insufficient. A positive `processed` snapshot stamped with `binder_evidence_version=1` is now stale under active evidence v2. The permanent regression constructs such a processed journal and proves the active v6 migration check rejects it as current proof. This downgrade does not authorize another provider search or mutable-page refetch; occupied/spent optional-slot semantics remain fail closed.

## Non-regression boundary

The remediation changes only active exact-binding semantics, its canonical tests/specification and audit evidence. It does not change:

- P3a evidence-only behavior or the byte-preserved `ensure_story_coverage_p3a.py` implementation;
- six mandatory Coverage directions;
- optional-slot atomic transfer or request admission locking;
- required legacy `unverified` priority;
- `request_started` no-retry semantics;
- Event/Source Freshness implementation or policy;
- archive exact-URL proof or mutable ordered-detail identity;
- Primary 12, Agency Rescue ≤1, Hybrid 4/conditional 5, Coverage ≤7;
- whole-pipeline ceilings 24/25;
- production publication/deploy validation.

Root `README.md` and `automation/README.md` were rechecked after the repair. Their public descriptions are intentionally implementation-version-neutral at this detail level and already describe exact authoritative identity, Freshness/archive checks, the same optional seventh slot and unchanged 24/25 ceilings, so no wording change is required there. Canonical implementation details are synchronized in `automation/ARCHITECTURE.md` and the permanent P3b matrix.

## Validation state

Regression-only red evidence is fixed at commit `d272835e42387aa5006befe103f404a6ecc89ea1`, PR Gate #397 / run `34876840067`.

An intermediate repaired head reduced the full suite to only the cross-claim `remains in preview` pair, which exposed the exact-anchor prose-continuation issue described above. That issue was then fixed locally in v4 rather than by weakening historical binder semantics. A subsequent documentation-stage Gate completed the Python unit suite and all main validators successfully before being superseded by later documentation commits.

The final documentation-inclusive exact SHA is intentionally recorded in the PR handoff rather than self-referenced inside this committed file: editing this file to insert its own resulting commit SHA would create another SHA. The final PR Gate must run after this audit, architecture, matrix and contract-test synchronization, and the PR handoff must name that unchanged exact head and gate.

Merge remains prohibited until that final documentation-inclusive exact SHA passes `Required PR Gate` and receives a new independent review with explicit `APPROVE`.
