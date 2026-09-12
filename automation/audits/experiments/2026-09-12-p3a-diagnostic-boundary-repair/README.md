# P3a diagnostic-boundary repair

## Scope

Independent follow-up to the Astra audit of merged P3a on main commit
`5b0f305c431aa4e55e07df245751cd84ed2718a0`.

This repair is intentionally narrower than P3b. It fixes two violations of the
already-documented P3a evidence-only boundary and changes no retrieval query,
provider route, search budget, candidate eligibility, Freshness, archive policy,
editorial ranking, recovery spend or publication gate.

No production workflow, production API, OpenAI call or paid Web Search was used.
Terra is not needed because the defects are deterministic local data-flow defects,
not search-quality hypotheses.

## Baseline counterexamples

### A. malformed weak provenance can abort completed Primary work

`urllib.parse.urlparse("https://[bad")` raises `ValueError: Invalid IPv6 URL`.
The Primary rejection schema permits a string URL without a URI-format constraint,
so a completed 12-pass Primary matrix can reach P3a annotation with such a row.
Before this repair `_weak_source_product_identity()` did not catch the exception.
The failure occurred after the paid matrix had returned and before the annotated
research/report could be saved.

Treatment: malformed weak-source provenance is non-qualifying diagnostic evidence.
The row is dropped from the P3a weak queue and completed Primary results continue.

### B. weak diagnostic evidence changed sealed editorial research

Merged P3a wrote the same new weak-source unresolved row into both the diagnostic
Primary report and the `research` object. The editorial transport serializes the
research object with `prompt_context.compact_json`, so candidate arrays could stay
identical while the actual editorial input and full-research hash changed.

Treatment: all qualified weak-source rows remain in the diagnostic Primary report,
but only the pre-existing non-weak unresolved signals are copied into research.
The old `unverified` research metadata therefore remains compatible while new weak
rows cannot perturb the editorial candidates context or paid-artifact identity.

## Regression acceptance

`automation/tests/test_p3a_diagnostic_boundary.py` protects both counterexamples:

1. a completed mocked Primary matrix containing `https://[bad` must return instead
   of raising and must not emit that malformed weak row;
2. adding a qualified weak-source rejection must change the diagnostic report but
   leave `compact_json(research)` exactly equal to the control containing only the
   pre-P3a `unverified` signal.

The existing P3a retention suite continues to prove that a qualified weak row is
retained in diagnostics with `resolution_required=false`,
`candidate_eligible=false` and zero additional search operations.

## Architecture-wide dependency check

Affected edge: Primary matrix output -> Retrieval Quality annotation -> saved
research/report -> Event/Source Freshness -> first editorial.

The treatment removes only the new weak row from research. Candidate arrays,
search-window fields, legacy unverified signals, regional health and existing
Primary annotations are unchanged. Coverage still obtains weak evidence from the
Primary diagnostic report and still ignores it because `resolution_required` is
false. No new recovery obligation or paid stage is introduced.

Source Pulse, Agency Rescue, Hybrid, Coverage runtime, P0 repair journal, archive,
publication validators and workflows are unchanged.

`README.md`, `automation/README.md` and `automation/ARCHITECTURE.md` were reviewed.
Their intended contract already says P3a is evidence-only and does not change
editorial eligibility/ranking/search spend. This PR restores implementation to
that contract rather than introducing a new system behavior, so no canonical-doc
rewrite is required. This audit note records the newly proven diagnostic placement
constraint explicitly.

## P3b boundary

This PR does not implement authoritative binding, change `_required_signals()`,
reserve the Coverage seventh slot or alter the old fuzzy unverified matcher. P3b
remains a separate correctness boundary after optional-slot reservation semantics
are repaired and tested.
