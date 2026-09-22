# 2026-09-22 legacy editorial request identity incident

Status: controlled zero-paid production recovery remediation.

## Failing production recovery

- run: `35687487645`
- exact run head: `0f0eafdac92c27555ed9add4ae41e52828b64f52`
- recovery input: run `35686440718`
- failure stage: Coverage editorial completion
- exact error: `EditorialRepairError: editorial repair request contract changed`
- recovery itself succeeded;
- full Research was skipped;
- completed Coverage evidence was reused;
- no new Web Search, editorial provider transport or Image API call occurred.

The restored durable v1 repair journal is in `response_saved` state and binds:

- request SHA-256:
  `73cd6015a0bfa345f49a00c0028b2d736c9e77cc657bb676fcb15464025c1885`
- archive SHA-256:
  `aab2217b89a785b74e0cebcbe7cde95ee16a06964ce4882728bf14dc4df9e810`

## Production evidence

The input artifact from run `35686440718` still contains the exact original
`2026-09-22/editorial-prompt-input.txt`. Its archive context has
`generated_at=2026-09-22T01:36:38+00:00`, and the full canonical archive hash is
exactly the journal `archive_sha256`.

The failed recovery artifact from run `35687487645` contains the same durable
journal/response, but its mutable dated prompt was overwritten before provider
admission. Its archive context has
`generated_at=2026-09-22T04:36:27+00:00`.

After removing only top-level `generated_at`, both archive contexts have the same
semantic SHA-256:

`9d6633c63e1f802d441b9ef336e3a2285b515529b39e7fe2f07b9f48567a82ba`

This proves the archive corpus did not change. PR #194 correctly fixed archive
identity, but the actual editorial request still embedded the volatile timestamp,
so the whole-request SHA changed. In addition, the runtime rewrote the dated
prompt before the request guard ran, destroying the only legacy request proof in
the newly uploaded artifact.

Therefore run `35687487645` must not be used as the next legacy recovery source.
Run `35686440718` remains the safe same-day source because it still contains the
original exact prompt proof.

## Mandatory red-first regression

The incident-to-entrypoint rule in `AGENTS.md` was applied before changing
runtime code.

Two preliminary attempts were rejected as invalid reproductions:

- PR Gate #653 / run `35687850442`: fixture was not a usable recovery artifact
  and failed before the production seam;
- PR Gate #654 / run `35687961283`: fixture timestamp did not match its
  publication date and freshness failed first.

The corrected production-shaped regression then ran on the pre-fix runtime:

- PR Gate #655 / run `35688045106`
- exact head: `5e29a60a6ccb251a0cb0e0f510727f3e73f29965`
- public path: `recover_digest_artifact.recover()` followed by
  `run_editorial_repair.main()`
- recovery succeeds;
- mutable dated prompt is rewritten before transport;
- test fails with the exact production error:
  `EditorialRepairError: editorial repair request contract changed`.

Only after this exact red reproduction was runtime remediation added.

## Bounded remediation

1. Recovery copies an exact legacy prompt proof from the selected same-bundle
   artifact into `production-daily/editorial-repair-<date>.prompt.txt` before
   runtime can rewrite the dated prompt.
2. The legacy proof archive must still hash exactly to the v1 journal
   `archive_sha256`.
3. When a durable v1 response exists and the current request hash differs, the
   guard compares the saved/current prompts. Their bytes outside
   `ARCHIVE_CONTEXT` must match exactly, and the archives may differ only by
   top-level `generated_at`.
4. The guard reconstructs the old request by substituting only the saved prompt
   into the current request structure. Replay is admitted only if that complete
   reconstructed request, including model, schema, reasoning/limits and Terra
   cache metadata, hashes exactly to the journal `request_sha256`.
5. New editorial prompts omit only archive `generated_at`, aligning actual
   request bytes with journal-v2 semantic archive identity.

This path cannot authorize a new provider request. Missing proof, changed prompt
policy/candidates, schema/model drift, semantic archive drift or a reconstructed
request hash mismatch remains fail-closed.

## Regression controls

The post-fix suite requires:

- the exact public recovery-to-editorial legacy replay to complete offline;
- provider callback count to remain zero;
- durable prompt proof to retain the original timestamp after the mutable dated
  prompt is overwritten;
- Terra structured input/cache-breakpoint request reconstruction;
- non-archive prompt drift to fail closed;
- JSON schema drift to fail closed;
- v2 editorial archive context to remove only `generated_at`;
- existing archive semantic-drift, request-started, response-saved, same-bundle,
  publisher-override and search-budget regressions to remain green.

No production API, Terra, Web Search, page refetch or image call is used for
remediation validation.
