# 2026-09-30 Meta service-field recovery incident

Status: zero-paid incident replay against saved production artifacts.

## Production evidence

Exact failed production run:

- run: `36658174880`
- head: `532e9efa3dc8104d64e55771fa2cfda30e2a3b4e`
- final artifact: `daily-production-2026-09-30`, artifact id `11073935299`
- Coverage checkpoint: `daily-production-checkpoint-coverage-2026-09-30-attempt-1`,
  artifact id `11072519995`

The paid retrieval/editorial stages completed before deterministic artifact
validation failed. Saved usage evidence reports 26 observed text calls:

- Primary: 12 calls / 12 search operations;
- Agency Rescue: 1 / 1;
- Hybrid: 5 / 5;
- Coverage: 6 / 6;
- Editorial: 2 calls;
- Image: 0 calls.

The internal observed-cost estimate is `$3.8078772`; it is diagnostic only and
is not a provider invoice.

The final validation report contains exactly five errors, all with code
`meta_star_service_field`:

- `meta.json`;
- `selection.json`;
- `digest.json`;
- `editorial-output-raw.json`;
- `editorial-output.json`.

No unrelated validation code is present.

## Independent offline Meta replay

The extracted real final artifact was copied to a scratch directory. The proposed
exact-marker normalization was applied recursively to the same service JSON set
used by the production validator, while excluding `article_html`, `html` and
`image_prompt`.

Result:

- 7 exact service-field occurrences were normalized across the five failing files;
- the real `digest.article_html` bytes were unchanged;
- no `Meta*` remained in the validator's sanitized service-field view;
- no network/provider call was made.

The public-entrypoint regression additionally runs
`normalize_digest_artifact.py` as a subprocess and proves the public HTML marker
survives while service strings become canonical `Meta`.

## Independent checkpoint comparison

The real Coverage checkpoint and the later final artifact were compared
byte-for-byte for paid-stage state. The following SHA-256 inputs are identical in
both artifacts:

- dated `candidates.json`: `ef405cbcb41959b67c6a40317976f12e65df56834aa03f0e0f387d5b15a10d3b`;
- dated `run-info.json`: `be9d20a606cbcb7ae857cc903229913389aca6ae6962329d157b9952748ae0e2`;
- dated `editorial-output.json`: `d83bfb800ffb97a12dbfbbe093aa7064aa243700381a4fe2ec5643b723fbc3ce`;
- dated `editorial-output-raw.json`: `66ba966e49e2af1484c2fab957e6e33285001619ee722c7e1f2f0582a3d769cb`;
- `coverage-audit.json`: `5aacbc5b807f4edd8404891acd3489934951ecdfd368d4f5b824621888ba0ff8`;
- Primary report: `0aa59ddaf46c976215312f7f159aaefa2618683197a842c804582b53811d123a`;
- Hybrid report: `e29eca654702083831bc6afad31d29ef46a74291ef01605f3016e61ec73b98eb`.

The checkpoint has no failed `artifact-validation.json`; the later final snapshot
does. Coverage state is `completed_usable` / `complete_with_gaps`, with six
completed Coverage searches and 15 saved candidates.

GitHub job-step evidence for run `36658174880` shows Coverage succeeded and both
Image generation/revalidation steps were skipped. Therefore a same-run rank-2
Coverage fallback cannot discard an attempted Image call in this incident.

## Recovery behavior after the fix

1. Current recovery first permits the final artifact to be revalidated because
   `meta_star_service_field` is now a narrowly revalidatable deterministic class.
2. Current normalizer removes only the service-field display marker, then normal
   validation reruns.
3. If a future final snapshot at the same rank is genuinely unusable, automatic
   recovery may try the same-run same-rank checkpoint once.
4. Rank-1 fallback is allowed only when Coverage never started; rank-2 fallback is
   allowed only when Image never started; rank-3 is already the last paid stage.
5. The rejected bundle is deleted before checkpoint download. Same-bundle P0,
   `request_started`, `response_saved` and fail-closed spend rules remain in
   force.
6. If both final and safe checkpoint recovery fail, the workflow stops. It still
   does not authorize fresh paid Research.

## Architecture audit

No retrieval query, model, prompt, ranking, candidate selection, freshness rule or
search ceiling changed. Primary remains 12, Agency Rescue <=1, Hybrid 4/5,
Coverage <=7 and whole-pipeline 24/25. The change is deterministic
normalization/recovery admission only.

No OpenAI API, Terra or Web Search was used for this replay.
