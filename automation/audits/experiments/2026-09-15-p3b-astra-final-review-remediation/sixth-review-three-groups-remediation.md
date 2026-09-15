# Astra sixth-review remediation: three material defect groups

## Independent review boundary

Fresh independent Astra final review inspected exact PR #183 head:

`e332e8b60a0adcb748af1b14c07cbae0a2712048`

and returned `REQUEST CHANGES`. The review was read-only: Astra did not change code, commits, PR metadata, or merge state. PR body and this audit are remediation records only and are not correctness proof.

The review independently confirmed that the three fifth-review counterexamples were fixed, the then-current 835-test suite and PR Gate #467 were green, P3a remained preserved, the canonical P3b matrix remained exactly 20 cases, and search ceilings remained 12 / 1 / 4–5 / 7 / 24–25. It then found three new material groups in `automation/scripts/weak_source_exact_binding_v4.py`.

## Finding 1: unrelated historical context hid a current negative lifecycle claim

Reproducer:

```text
DeepSeek launches V4.1 Flash |
Today, DeepSeek did not launch V4.1 Flash, with a dispute dating to September 1, 2025 still unresolved
```

Expected: the current negation blocks admission.

Observed on reviewed head: `bound_candidate`; one candidate survived and a positive processed snapshot was stored.

Root cause: broad old-date classification could attach a background date to the lifecycle relation before current negation / attribution semantics were resolved. Similar shapes could affect foreign attribution and mixed current/historical relations in one local claim.

Remediation: history is now relation-local. Current negation/state/foreign attribution is evaluated against the lifecycle relation, while an old date/year counts as history only when the bridge to that relation is clean. Background/causal bridges such as `with`, `while`, `due to`, `dispute`, `agreement`, `dating to`, and a current post-action state prevent an unrelated date from laundering a current veto into historical context.

## Finding 2: historical cancellation vetoed a separate current exact launch

Reproducer:

```text
DeepSeek launches V4.1 Flash |
DeepSeek V4.1 Flash launch cancelled on September 1, 2025
```

Expected: the separate current exact launch remains admissible; the cancellation is an old relation and must remain non-positive background.

Observed on reviewed head: `lifecycle_noncurrent`; zero candidates.

Root cause: cancellation/state was treated as an active lifecycle veto before its own temporal relation was classified.

Remediation: post-action state gets its own span and temporal binding. A cancellation explicitly bound to an old date is historical background and does not veto a separate current positive claim. A current cancellation such as `launch cancelled today due to a 2025 incident` remains current non-positive. Historical-only cancellation remains non-positive and cannot become current proof.

During remediation, PR Gate #470 exposed two collateral historical controls:

```text
In 2025, DeepSeek launched V4.1 Flash
DeepSeek launched V4.1 Flash in 2025 and now discusses it
```

The first relation-local implementation incorrectly allowed them. The follow-up repair restores direct prefix/suffix old-year binding while preventing a later unrelated current predicate from retroactively turning the old lifecycle event into current proof.

## Finding 3: Unicode wrappers hid a foreign trailing replacement agent

Reproducers:

```text
DeepSeek says V4 Pro was replaced by V4.1 Flash «by OpenAI»
DeepSeek says V4 Pro was replaced by V4.1 Flash ‹by OpenAI›
DeepSeek says V4 Pro was replaced by V4.1 Flash （by OpenAI）
```

Expected: `organization_event_attribution_mismatch` and no candidate.

Observed on reviewed head: the attribution was not captured; the candidate could bind.

Remediation: trailing replacement attribution now recognizes Unicode guillemets/single guillemets/fullwidth opening wrappers in the same bounded wrapper grammar as ASCII/curly forms. Agent normalization strips the matching closing wrappers before exact normalized organization comparison. Positive same-agent controls remain required.

## Regression-first evidence

Permanent regressions were added first in:

`automation/tests/test_p3b_astra_sixth_review.py`

Test-only SHA:

`97b1b6034fc3031c282aa4d5b1ae7dfa9faa9e20`

PR Gate #468 / workflow run `34982285665` failed as expected against the old runtime. The suite contained 839 tests and produced seven failures owned by the new sixth-review assertions/version marker; existing fifth-review controls remained green. This establishes that the new tests reproduced the defects rather than merely documenting already-fixed behavior.

## Runtime remediation and collateral gate

Initial runtime remediation commit:

`0579c7a5c8d6e23ea1605378ec12a3e1dee6bb99`

The active binder kept durable `VERSION=2` and advanced semantic proof to `EVIDENCE_VERSION=6`. Intermediate PR Gate #469 was superseded by a newer head and is not used as final evidence.

Candidate head `b14059c9c8aeed2672f9fa29f2e738e95c46cf73` ran PR Gate #470 / workflow run `34983375109`. All sixth-review regressions passed, as did the fifth-review regressions. Gate #470 nevertheless failed four tests: two stale literal evidence-v5 expectations and the two collateral historical controls listed above. Those failures were treated as real remediation feedback, not waived.

The follow-up runtime repair makes old-year prefix/suffix markers relation-bound through a clean bridge, restores the old historical controls, and keeps the new background-date defenses. Existing version assertions/recovery tests are advanced to current evidence-v6 semantics, with positive evidence-v1 through evidence-v5 stale.

## Version / recovery contract

Active public Coverage runtime remains P3b v6.

Semantic binder remains `automation/scripts/weak_source_exact_binding_v4.py`; the filename is a compatibility/import surface, not the evidence version.

Durable request identity remains:

`VERSION=2`

Current semantic positive proof becomes:

`EVIDENCE_VERSION=6`

Positive processed evidence-v1, evidence-v2, evidence-v3, evidence-v4, and evidence-v5 are stale relative to current v6 proof. They cannot be reused as current positive proof. Existing stale-candidate revocation remains a v6 postcondition and must not create a new provider search or mutable-page refetch. `request_started` remains consumed/ambiguous and is never automatically retried.

## Preserved invariants

- P3a production blob SHA remains `14f0e38f57b9285a949ec5083136999c12c81bc0`.
- Canonical P3b validation matrix remains exactly 20 cases; sixth-review counterexamples are supplemental permanent regressions.
- Primary maximum remains 12.
- Agency Rescue maximum remains 1.
- Hybrid maximum remains 4 normally / 5 only on the approved double-regional-gap path.
- Coverage maximum remains 7: six mandatory plus the existing optional seventh.
- No eighth Coverage search is authorized.
- Whole-pipeline ceiling remains 24 normally / 25 conditional.
- No query/provider/domain routing/ranking/publication-policy expansion is part of this remediation.
- Durable optional-slot ownership, atomic P3b→legacy transfer, and recovery semantics remain unchanged.

## Spend / external calls

Remediation and validation use deterministic/offline tests plus GitHub CI:

- production API calls: 0;
- paid Web Search calls: 0;
- Terra calls: 0.

## Final-review requirement

Do not treat this remediation audit, PR metadata, or regression names as independent proof. After the exact final head receives a green PR Gate, a fresh independent Astra review must inspect that exact SHA, independently reproduce the sixth-review counterexamples and neighboring adversarial variants, re-check prior fifth/fourth-review controls, verify evidence-v6 recovery semantics and unchanged ceilings, and return either `APPROVE` or `REQUEST CHANGES`.

The exact final SHA and green Gate/run belong in PR metadata after CI completes. They are intentionally not committed back into this tracked audit because doing so would create a new SHA and invalidate the claimed exact-head evidence.