# P3b eleventh-review remediation: P3a lifecycle morphology alignment

Date: 2026-09-16

Reviewed head that produced the independent REQUEST CHANGES:

`bc3c76a4175cbebfa84beee55bdbd5dcd87ae494`

This record is evidence/history only. It is not correctness proof and does not replace a fresh independent review of the final remediation head.

## Independent finding

The blind review found a production-reachable HIGH false-negative class in active P3b exact binding. P3a canonicalizes inflected weak-source lifecycle wording into canonical anchors, but the inherited binder vocabulary did not expose matching morphology for every canonical action.

The directly observed blocker was canonical `release`: P3a turns `release`, `releases` and `released` into `lifecycle_action_anchors=["release"]`, while the inherited binder stored those forms only under the separate `launch` group. Therefore normal authoritative wording such as `DeepSeek released V4.1 Flash` could fail with `lifecycle_identity_mismatch` before deterministic Freshness.

Architecture-wide comparison showed the same root mismatch for the production-reachable canonical families `introduce`, `unveil`, `ship`, `rollout` and `retire`. The latter also owns `discontinue*` wording in P3a. Leaving only `release` fixed would preserve adjacent false negatives from the same canonicalization contract.

## Independent zero-paid experiment

Before changing the repository, baseline and proposed morphology maps were compared on the same controlled corpus derived from the exact P3a action regexes and active binder groups at the reviewed head.

- controlled authoritative morphology cases: 34;
- 32 cases use surfaces directly retained by P3a;
- 2 cases are adjacent authoritative-page controls (`launch` for a signal retained from `launched`, and `rolling out` for a signal retained from `rolled out`) and do not create new P3a semantics;
- baseline production-reachable false negatives repaired by the proposed overlay: 16;
- regressions on already-supported morphology: 0;
- OpenAI calls: 0;
- Web Search calls: 0;
- Terra calls: 0.

Terra was not used because this remediation changes no query text, provider/model routing, search order, ranking or paid-search admission. The experiment is entirely deterministic post-retrieval event binding.

The 16 repaired surfaces are the inflected forms that baseline could not bind to the P3a canonical anchor: `releases`, `released`, `introduces`, `introduced`, `unveils`, `unveiled`, `ships`, `shipped`, `roll out`, `rolls out`, `rolled out`, `retires`, `retired`, `discontinue`, `discontinues`, `discontinued`.

## Remediation boundary

`automation/scripts/weak_source_exact_binding_v4.py` now adds an active-v4-only lifecycle morphology overlay on the private v3/v2 compatibility instance. Historical `weak_source_exact_binding_v2.py` and `weak_source_exact_binding_v3.py` source semantics remain unchanged.

The overlay mirrors all P3a canonical lifecycle families that were previously missing:

- `release` -> `release | releases | released`;
- `introduce` -> `introduce | introduces | introduced`;
- `unveil` -> `unveil | unveils | unveiled`;
- `ship` -> `ship | ships | shipped`;
- `rollout` -> `rollout | roll out | rolls out | rolled out | rolling out`;
- `retire` -> `retire | retires | retired | discontinue | discontinues | discontinued`.

The existing `launch`, `update/upgrade`, `preview`, `ga/general_availability`, `replace` and benchmark contracts are preserved.

Because the newly recognized lifecycle verbs become active exact-binding predicates, v4 also extends its private lifecycle-word boundary used to prevent one relation from borrowing anchors across another lifecycle predicate. Passive attribution checks are extended to the newly aligned action families so `... was released/introduced/... by ForeignOrg` remains fail-closed rather than gaining eligibility as a side effect of morphology repair.

## Permanent regressions

`automation/tests/test_p3b_astra_eleventh_review.py` covers:

- real P3a signal extraction for every production-reachable canonical family, using direct P3a morphology plus the two explicitly labelled adjacent authoritative controls;
- direct v4 `exact_event_identity` acceptance for each matching canonical family;
- explicit `release` controls for `release`, `releases` and `released`;
- foreign passive performer rejection for release, introduce, unveil, ship, rollout and retire;
- same-organization passive positive control;
- real active Coverage processor + authoritative page + deterministic Source Freshness positive admission for `released -> release`;
- real Coverage-path rejection for a foreign passive release performer;
- unchanged historical v2 lifecycle groups;
- unchanged durable `VERSION=2` and semantic `EVIDENCE_VERSION=6`.

The first CI run of this remediation (Gate #495 / workflow run `35088622909`) was intentionally not accepted as a final gate: its runtime compiled and 867 of 868 unit tests passed, but the new regression harness incorrectly attempted to create a P3a signal from bare `launch`, which the production collector does not retain as an input surface. The test was corrected to create the canonical `launch` signal from real P3a-retained `launched` and use bare `launch` only as the adjacent authoritative-page control described above. No runtime remediation logic changed in that correction.

`automation/specs/search-change-validation-matrix.md` adds permanent case **O14** and a corresponding critical combination / incident record. The canonical 20-case P3b exact-authoritative-binding matrix remains unchanged.

## Version and recovery rationale

No durable request schema or search intent changes. Evidence-v6 is still confined to this open, unmerged PR, so the remediation hardens the same unreleased semantic proof contract rather than creating a new durable migration generation:

- durable request `VERSION` remains 2;
- semantic `EVIDENCE_VERSION` remains 6;
- positive evidence v1-v5 remains stale relative to v6;
- `request_started` remains consumed/ambiguous and is never automatically retried;
- `response_saved` replay remains offline;
- stale-evidence cleanup authorizes zero provider retry, zero page refetch and zero optional-slot refund.

## Search-budget and architecture audit

Unchanged:

- Primary maximum 12;
- Agency Rescue maximum 1;
- Hybrid maximum 4 normally / 5 only on the approved double-regional-gap path;
- Coverage maximum 7 = six mandatory + existing optional seventh;
- no eighth Coverage search;
- whole-pipeline ceiling 24 normally / 25 conditional;
- P3a remains evidence-only;
- P3a production blob expectation remains `14f0e38f57b9285a949ec5083136999c12c81bc0`;
- no query generation, provider choice, model routing, ranking, candidate caps, Freshness policy, archive policy, editorial policy or publication policy changes.

README and `automation/ARCHITECTURE.md` require no semantic update because they already state the intended contract: exact lifecycle/action binding between the retained P3a signal and authoritative event evidence. This remediation makes runtime conform to that existing documented boundary rather than changing the boundary.

## Fresh review requirement

The remediation author must not self-approve. After CI is green on the exact final head, a fresh independent review must reproduce the original `release` blocker plus adjacent canonical families, verify passive-attribution safety, run the active Coverage/Freshness path, re-check recovery/search-budget invariants and inspect the final diff before any merge.
