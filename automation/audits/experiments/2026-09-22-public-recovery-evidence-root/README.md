# 2026-09-22 public recovery evidence-root incident

Status: controlled zero-paid recovery remediation.

## Production failure

- failed recovery run: `35684833342`
- exact run head: `9b775ed89dc902259c88dd26ab9f0f5d7d10c252`
- requested manual recovery artifact: run `35676364066`
- downloaded artifact: `daily-production-2026-09-22`
- failure stage: `Restore saved paid artifact`
- exact error: `Digest recovery failed: selected recovery evidence root was not recorded`
- full research/editorial and Coverage were not re-run in the failed recovery attempt;
  OpenAI SDK installation and all subsequent paid stages were skipped.

The source artifact itself is structurally same-bundle: its selected dated
directory is `2026-09-22/`, while the durable P0 journal
`production-daily/editorial-repair-2026-09-22.json` is its sibling under the
same extracted artifact root. The journal is in `response_saved` state.

## Root cause

The P0 recovery contract records the selected evidence root in an in-memory
module marker when its own `choose_source` hook runs. The current public recovery
entrypoint is layered through several compatibility wrappers. Unit tests covered
P0 journal restoration and the active wrapper helpers separately, and some tests
manually assigned the evidence-root marker. They did not exercise the complete
public `recover()` stack with a production-shaped same-bundle P0 journal.

In the real manual recovery the lower recovery engine successfully selected and
copied the exact dated source and recorded that path in its in-memory recovery
report, but the transient P0 marker was not propagated back through the wrapper
stack. P0 then saw a real journal in the artifact while its marker was `None` and
correctly failed closed.

## Bounded remediation

When the transient marker is absent, P0 may recover same-bundle identity only from
the exact `selected_source` already emitted by the lower recovery engine in the
same in-memory recovery report. The fallback:

1. requires a non-empty exact selected-source path;
2. requires that selected source still exists;
3. applies the existing containment check against the requested recovery root;
4. derives only `selected_source.parent` as the evidence root;
5. stores that exact root back into the P0 marker for later active-wrapper
   optional-slot/P3b restoration.

It never searches sibling bundles, never chooses by date, never opens provider
I/O, never repeats Web Search, and never changes retrieval/editorial selection.

## Verification plan

A new regression calls the public `recover_digest_artifact.recover()` entrypoint,
not an internal helper. It builds a production-shaped partial editorial artifact
with a valid durable P0 journal and asserts that the public stack restores the
journal from the selected same bundle, preserves `partial_editorial`, and
records the exact evidence root.

Neighbor invariants remain covered by existing tests: different-bundle state is
rejected, optional-slot and P3b state restore only from the selected bundle,
ambiguous started provider work is never retried, and paid search ceilings are
unchanged.

No production API, Terra, Web Search, page refetch or other paid provider call is
used for this remediation validation.
