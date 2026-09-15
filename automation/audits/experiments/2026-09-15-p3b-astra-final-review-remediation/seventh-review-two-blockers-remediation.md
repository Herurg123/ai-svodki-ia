# Astra seventh-review two-blocker remediation

Date: 2026-09-15

## Scope

This remediation addresses only two independently reproduced semantic defects in
`automation/scripts/weak_source_exact_binding_v4.py`. It does not change search
queries, providers, routing, ranking, publication policy, Freshness policy, P3a,
Coverage capacity, or the 24/25 whole-pipeline search ceilings.

No production API, paid Web Search, or Terra call is required for this change.
Validation is deterministic/offline plus GitHub CI.

## Blocker 1: current negation laundered by an unrelated historical date

Reviewed-head reproduction:

```text
DeepSeek launches V4.1 Flash | Today, DeepSeek did not launch V4.1 Flash, citing reporting from September 1, 2025
```

The old relation-local history check considered only the bridge from the action to
the old full date. Because `citing reporting from` was not one of the enumerated
background bridge words, the old date could be attached to the negated lifecycle
relation. The current contradiction was then downgraded to historical context and
a separate clean-looking positive claim could win.

The remediation adds a relation-local current-prefix guard. An explicit current
marker immediately governing the lifecycle relation prevents a later unrelated old
date from making that relation historical. A reporting/attribution predicate or a
newer relation-bound historical marker between the current marker and action
prevents the guard from overreaching. This preserves historical controls such as:

```text
Today, DeepSeek said it launched V4.1 Flash on September 1, 2025
```

Permanent regressions cover `citing reporting from`, `according to ... records`,
and `per ... reporting` variants through both the direct binder and the active
candidate-processing path.

## Blocker 2: closing wrapper hid a foreign trailing replacement agent

Reviewed-head reproductions include:

```text
DeepSeek: «V4 Pro was replaced by V4.1 Flash» by OpenAI
DeepSeek: [V4 Pro was replaced by V4.1 Flash] by OpenAI
```

The trailing-agent regex allowed punctuation and opening wrappers before `by` but
not closing ASCII/Unicode/fullwidth wrappers. The matcher therefore stopped before
`by OpenAI`, so the foreign performer was never checked.

The remediation accepts both opening and closing wrapper characters in the bounded
pre-`by` separator sequence. Permanent regressions cover guillemets, ASCII square
and round brackets, fullwidth round brackets, nested mixed wrappers, and a
DeepSeek positive control.

## Versioning and recovery boundary

Durable request identity remains `VERSION=2` and semantic evidence remains
`EVIDENCE_VERSION=6`.

Evidence 6 is intentionally not bumped for this remediation because the evidence-6
implementation is still confined to this open, unmerged PR and has not become a
production durable-proof contract. Existing production positive evidence v1-v5
remains stale relative to the final evidence-v6 semantics. No stale-proof migration
or new I/O authorization changes are introduced.

## Documentation impact

`README.md`, `automation/README.md`, `AGENTS.md`, the canonical 20-case P3b matrix,
and `automation/ARCHITECTURE.md` already describe the intended fail-closed contract.
This remediation makes the implementation satisfy that existing contract; it does
not change the documented architecture or canonical matrix.

## Required final verification

Before merge, the exact final head must have a green PR Gate and receive a fresh
independent review. Green CI, this audit record, and regression names are evidence
pointers, not correctness proof.
