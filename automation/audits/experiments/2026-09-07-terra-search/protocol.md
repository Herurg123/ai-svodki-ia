# Prospective assistant-side Terra A/B protocol

Status: NOT EXECUTED. Stopped before either search call after independent
architecture review found a blocking event-identity counterexample. These are
prepared inputs, not search results or completed acceptance evidence.

Two isolated gpt-5.6-terra executors each receive only their own generated request.
Each must make exactly one web search with one exact query, no domain filter,
no navigation or supplementary searches, and retain raw tool evidence. No paid
production API call is authorized. Frozen editorial window and pre-run archive
come from the exact Sep-5 production artifacts/commit, identical across arms.
A uses unchanged v8 agency-target factory with the saved cand-003. B uses current
required-signals/cluster/resolution prompt from raw Primary and Source Freshness
records. No known alternative URL/HTML/RSS is passed to the search executor.

Expected admissible delta: B may discover/verify the lost same event through a
new authoritative source while A corroborates its already-existing target or
returns an empty set. B must not replace the event with a different company story,
accept an out-of-window source, fabricate an exact date, or add a search operation.
Returned candidate(s) will go through actual deterministic source and merge/cap/
dedupe gates. A newly successful baseline corroboration is a real priority tradeoff,
not a result to hide. Independent architecture acceptance remains required.

This is a current-index assistant-tool comparison of equal bounded search actions,
not reproduction of the historical search index or the production API transport.
One pair is evidence for this incident, not a statistical quality/spend guarantee.
