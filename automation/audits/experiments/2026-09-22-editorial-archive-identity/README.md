# 2026-09-22 editorial repair archive identity incident

Status: controlled zero-paid production recovery remediation.

## Failing production recovery

- recovery run: `35686440718`
- exact run head: `86d0ecdc6508fd3b80737ea35d98509ae4bb06eb`
- input paid artifact run: `35676364066`
- failure stage: Coverage editorial completion
- exact error: `EditorialRepairError: editorial repair input changed: archive_sha256`
- recovery itself succeeded; full Research was skipped
- completed Coverage evidence was reused; no new Web Search or provider editorial
  transport occurred in the failing recovery run
- failing run artifact: `10676832395`

## Production evidence

The durable v1 journal restored from the exact selected bundle contains:

- state: `response_saved`
- archive SHA-256:
  `aab2217b89a785b74e0cebcbe7cde95ee16a06964ce4882728bf14dc4df9e810`
- created at: `2026-09-22T01:46:38.384835+00:00`

The same artifact contains the saved `editorial-prompt-input.txt`. Its exact
`ARCHIVE_CONTEXT` has:

- `generated_at = 2026-09-22T01:36:38+00:00`
- 66 archive items
- canonical full-object SHA-256 exactly equal to the journal
  `archive_sha256` above.

The tracked `automation/archive/index.json` blob is byte-identical at:

- original production head `fefb11c504a93b9ca1c964db9d46c5c293613fd6`
- first remediation main `9b775ed89dc902259c88dd26ab9f0f5d7d10c252`
- current failing recovery main `86d0ecdc6508fd3b80737ea35d98509ae4bb06eb`

All three use Git blob `8915ebafd38ed697ecc1be82809221946b4f5415`.

The production workflow nevertheless runs `bootstrap_archive.py` before
Coverage. That script writes top-level `generated_at = now()` on every rebuild.
V1 repair identity hashed the entire archive object, so a deterministic rebuild of
the same 66-item archive changed `archive_sha256` solely because of this
operational timestamp.

## Remediation

Editorial repair journal identity v2 hashes the archive after removing only the
top-level `generated_at`. Version, source, items, story records, source URLs and
all other archive content remain bound.

Legacy v1 journals are not broadly relaxed. A v1 archive mismatch is admitted
only when both conditions are proven:

1. the archive context extracted from the saved exact editorial prompt has a full
   canonical hash equal to the v1 journal `archive_sha256`;
2. that saved archive and the current archive are canonical-equal after removing
   only top-level `generated_at`.

Missing prompt evidence, a prompt/hash mismatch, item drift, story drift, source
drift or any other semantic difference remains fail-closed.

## Regression gate

The regression suite includes:

- a v2 journal whose current archive changes only `generated_at`: load succeeds;
- a v2 semantic archive mutation: load fails closed;
- a production-shaped legacy v1 `response_saved` journal with saved prompt proof,
  executed through the public `run_editorial_repair.main()` entrypoint: the
  saved response replays offline and provider callback is never called;
- a legacy saved prompt plus real archive-item drift: replay fails closed.

The public-entrypoint regression specifically covers the seam that failed in
run `35686440718`; it does not inject a replacement archive identity marker.

No production API, Terra, Web Search, page refetch or image call is used for this
remediation validation.
