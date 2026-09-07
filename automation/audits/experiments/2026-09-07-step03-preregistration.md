# Step 3: publication evidence continuity

Baseline: `4fc0c164dd5159522047b7b457add1bac0a91f0c`.
Before independent final acceptance, freeze these expectations:

1. The saved Sep 4 Yandex page and Sep 3 Claude Code release evidence repair two
   date-proof losses in the real freshness gate. Candidate eligibility is
   reconstructed at its pre-gate state, not by reviving arbitrary excluded rows.
2. Generic publication metadata takes priority. A stale event must still reject
   before fetching. Date-only partial boundaries, future releases, draft/wrong
   repository/tag, redirects, invalid publication timestamps and source errors
   must remain fail-closed. `created_at` is never a publication substitute.
3. Replay current baseline and proposed version on the same inputs. Exact unchanged
   generic/nonmatching behavior is required. Matrix combinations cover sparse/dense
   pools, regional data, shared URL identities, include/consider/exclude, old/fresh
   event and source dates, boundaries and repeated saved-input verification.
4. Search query, cap, regional/agency health, paid budget, publication, archive
   dedupe and recovery planners remain unchanged. Full regressions and canonical
   validators must pass. No OpenAI client or paid API is used by the experiment.
5. Yandex makes no extra request. GitHub may make one additional logical public
   Releases API fetch per matching source lacking HTML date, through the existing
   bounded safe fetcher (its existing retry policy applies). No API key required.
   HTTP 403 before successful page retrieval is deliberately not rescued here.

Architecture review: v2 supplies a per-call optional evidence resolver to the
preserved v1 gate. Its default is None, so historical entrypoints and test hooks
retain their behavior. There is no global monkeypatch. Yandex calls the existing
Pulse parser only for identical HTTPS article identity. GitHub evidence must
match both the API endpoint and the exact cited HTML repository/tag URL.
Raw candidate date claims and saved model assertions never become proof.

Evidence locators/dates flow through the existing source report and v2 candidate
diagnostics. Event gate, source promotion and exact-window arithmetic are reused.
The correction establishes eligibility, not significance or automatic selection.
All fixtures are inert; reduced HTML is labelled and full saved HTML is tested
separately when available. This is a deterministic evidence experiment, not a
Terra query experiment: no search prompt or ranking changes.

Any failed final independent acceptance stops the sequence for a DOCX report.
