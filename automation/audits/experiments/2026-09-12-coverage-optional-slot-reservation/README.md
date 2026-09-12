# Coverage optional seventh-slot reservation audit — 2026-09-12

## Scope

This audit covers only the durability/recovery semantics of the already-existing
optional seventh Coverage Web Search operation. It is a prerequisite for P3b
exact authoritative binding, not an implementation of P3b.

Audited production baseline: `5b0f305c431aa4e55e07df245751cd84ed2718a0`.
Code-only treatment head that first passed the complete offline suite:
`031505ab1866558a1cba9d9b1097035ce2b30362`.

No user production API budget, paid Web Search, production workflow dispatch, or
live provider transport was used for this audit. Assistant-side Terra was not
needed because the treatment changes no query text, routing, candidate ranking,
or source selection; all acceptance claims are deterministic recovery/budget
properties exercised on saved/offline inputs.

## Why this prerequisite exists

The pre-treatment Coverage accounting derived optional capacity mainly from the
semantic attempt list / completed-call count. A crash or cleanup boundary could
therefore erase the semantic representation of an already admitted seventh
request and make the slot look available again. That is unsafe for any later
P3b consumer: a provider request whose outcome is unknown cannot be refunded
simply because its parsed result was not retained.

The repair separates provider-admission truth from semantic-resolution truth.
The optional slot has a durable journal outside rollback-prone semantic state and
moves monotonically through:

`reserved -> request_started -> response_saved -> processed`

The reservation is persisted before provider admission. `request_started` is
persisted before the wire call. The raw provider response is fsynced before the
journal becomes `response_saved`. Parsed/processed state is derived only after a
saved response exists.

## Invariants

1. Coverage remains six mandatory searches plus at most one optional seventh
   search. No eighth Coverage search is introduced.
2. The six mandatory Coverage requests retain their established transport/retry
   contract. Only the protected optional seventh request uses SDK
   `max_retries=0`.
3. Failure to persist `reserved` prevents provider transport.
4. Once `request_started` is durable, the optional capacity is consumed or
   ambiguous and cannot be automatically retried/refunded.
5. `request_started` without an authoritative saved response fails closed.
6. If the raw response was durably saved before a crash, restart reparses the
   same response offline. It never opens another provider request.
7. If the parsed result or complete processed Coverage snapshot was saved,
   restart replays it offline.
8. Semantic cleanup, migration, negative resolution, or attempt filtering cannot
   turn an admitted/spent optional operation back into `remaining_calls=1`.
9. Legacy artifacts containing an already-spent optional resolution attempt keep
   effective consumption at seven even if compatibility migration rewrites the
   semantic attempt list.
10. Recovery restores optional-slot state only from the same selected artifact
    bundle. Same-date state from another bundle is not eligible evidence.
11. Bundled journal/response integrity is verified before target mutation.
    Corrupt response hashes fail closed.
12. Existing divergent target journal/response state is never overwritten by
    recovery. Exact identical state is idempotent.
13. Candidate matching, signal priority, query construction, Freshness, archive
    dedupe, ranking, regional health and Agency health are unchanged by this PR.
14. P3a weak-source evidence remains `resolution_required=false`; this repair does
    not give it ownership of the seventh slot.
15. P3b exact authoritative binding remains deferred until this prerequisite and
    the separate P3a repair are merged.

## Whole-project dependency trace

### Primary Recall

No query, pass count, source routing, candidate cap, recommendation or sealed
research behavior changes. This repair consumes only Coverage state downstream.

### Source Pulse

No registry, parser, promotion, snapshot or recovery behavior changes. Pulse
cannot create or free Coverage optional capacity.

### Event Freshness / Source Freshness

No freshness rule changes. The slot journal cannot turn a stale/unknown candidate
into a fresh one and cannot bypass direct-page validation.

### First editorial

No prompt, ranking or selection rule changes. The reservation journal is service
state and is not injected into editorial research/context.

### Agency Rescue

No Reuters routing/query/search slot changes. Agency state is independent of the
Coverage optional slot.

### Hybrid

No Hybrid budget/routing changes. The existing Hybrid ceilings and regional-gap
semantics remain independent of Coverage accounting.

### Coverage

This is the only semantic runtime boundary. Six mandatory passes are unchanged.
The existing optional seventh operation now has durable admission accounting.
`completed_calls` continues to describe completed search operations; the added
`reserved_or_spent_calls` / `effective_consumed_calls` fields represent capacity
that cannot safely be refunded after provider admission.

The preserved pre-guard public wrapper is stored as
`automation/scripts/ensure_story_coverage_p0.py`. The active wrapper restores
historical monkeypatch/public compatibility hooks and installs the optional-slot
hooks only during production-style orchestration so direct legacy callers retain
the established P0 behavior.

### Archive

No archive lookup/dedupe contract changes. A saved seventh response replay still
passes through the established Coverage merge/eligibility logic.

### Editorial repair journal

The P0 editorial repair journal is separate from the optional Coverage slot
journal. Neither journal substitutes for the other. Both are fail-closed around
unknown provider outcomes.

### Artifact recovery

The preserved P0 recovery wrapper is stored as
`automation/scripts/recover_digest_artifact_p0.py`. The active recovery layer
adds only same-bundle restoration of Coverage optional-slot journal/response
state after the normal source bundle has been selected. It does not perform a
global same-date merge.

### Publication validation

No publication eligibility rule is weakened. Pending/incomplete Coverage remains
subject to the existing fail-closed publication contracts.

## Interruption matrix

| Boundary | Durable state | Allowed restart behavior | New provider search? |
|---|---|---|---:|
| reservation write fails | no valid reservation | fail before transport | no |
| `reserved` saved, process stops before admission | `reserved` | same exact intent may continue | at most one |
| `request_started` saved, transport outcome unknown | `request_started` | fail closed / no automatic retry | no |
| provider response fsynced, crash before parse snapshot | `response_saved` + raw response | reparse saved raw offline | no |
| parse/result snapshot saved, crash before semantic apply | `response_saved` + snapshot | replay snapshot offline | no |
| final Coverage result persisted | `processed` | replay processed snapshot | no |
| same-date state exists only in another bundle | selected bundle has no state | ignore foreign bundle | no |
| selected response hash corrupt | invalid selected bundle state | fail closed before target mutation | no |
| target already has divergent journal | conflict | fail closed; overwrite forbidden | no |

## Offline evidence

The dedicated regressions are:

- `automation/tests/test_coverage_optional_slot_guard.py`
  - reservation persistence failure blocks transport;
  - protected transport uses no SDK retry;
  - `request_started` cannot be retried;
  - consumed capacity stays at seven;
  - saved response replays offline;
  - raw-response-only crash gap reparses offline;
  - legacy spent seventh attempt is not refunded.
- `automation/tests/test_coverage_optional_slot_recovery.py`
  - only selected-bundle state can be restored;
  - selected journal/response restore together;
  - corrupt selected response fails closed;
  - divergent existing target journal cannot be overwritten.

The complete repository offline suite passed on code-only head
`031505ab1866558a1cba9d9b1097035ce2b30362`: 723 tests, compileall and all
production validators; Required PR Gate succeeded.

## Search/change matrix result

Relevant matrix dimensions are Budget + Recovery + Degradation + Ordering.
Baseline and treatment were compared on deterministic saved/offline states.
Expected semantic delta is restricted to provider-admission accounting after the
optional slot is reserved/started. Candidate identity/order, query wording,
Freshness and archive behavior must remain identical.

Permanent matrix coverage is extended with the optional-slot interruption and
same-bundle recovery cases. In particular:

- occupied/ambiguous seventh slot + cleanup/recovery must not become free;
- `request_started` + missing response must not retry;
- durable raw response + missing parser snapshot must replay offline;
- same-date foreign bundle must not supply reservation state;
- divergent target state must not be silently replaced.

## Documentation / compatibility review

Root `README.md` was checked. Its high-level contract already states that Coverage
has six mandatory passes plus at most one optional seventh search, so no root
behavioral wording change is required by this prerequisite. `AGENTS.md` was also
checked; no engineering-policy change is introduced.

The durable journal is an internal recovery mechanism. This audit and the
canonical search-change matrix are the source of truth for its interruption and
same-bundle invariants; P3b must cite and reuse them rather than creating a new
budget model.

## P3b gate

This PR does **not** authorize P3b to claim the seventh slot merely because a
weak-source row exists. After this prerequisite is merged, P3b still needs a
separate deterministic owner-selection/exact-event-binding contract. A higher
priority existing required obligation wins the shared optional slot. If the slot
is already reserved, started, saved, processed or legacy-spent, weak-source
binding must remain deferred and must not create another search.
