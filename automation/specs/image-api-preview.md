# Image API preview: artifact-only contract

## Purpose

Generate one real cover for an already validated editorial artifact without
rerunning research or editorial text generation.

## Safety boundary

- branch: `automation-prep` only;
- trigger: a commit that changes exactly
  `automation/requests/image-preview.json`;
- source: hash-locked editorial artifact under
  `automation/fixtures/editorial/`;
- endpoint: `POST /v1/images/generations`;
- model: repository variable `OPENAI_IMAGE_MODEL`, which must match
  `automation/config/image.json`;
- number of images: one;
- automatic retries: zero;
- output: `automation/preview/image-api/` artifact only;
- no writes to `posts/`, no FTP, no commit, no production RSS changes.

## Request schema

```json
{
  "enabled": true,
  "mode": "image_api_preview",
  "source": "automation/fixtures/editorial/2026-07-11",
  "publication_date": "2026-07-11",
  "request_id": "image-preview-001"
}
```

The request file is deliberately absent from the infrastructure commit. It is
added later as a separate paid commit after all offline checks are green.

## API parameters

- model: `gpt-image-2`;
- size: `1536x864`;
- quality: `high`;
- output format: `png`;
- background: `opaque`;
- n: `1`.

The response image is returned as base64 and decoded directly to `cover.png`.
The base64 payload is never written to logs or JSON artifacts.

## Validation

The workflow validates:

1. request-only Git diff and unique request ID;
2. hashes and provenance of the editorial source;
3. editorial artifact contract before the API call;
4. PNG dimensions, chunks, CRC and metadata after the API call;
5. isolated HTML, site index and RSS with the real cover;
6. unchanged `posts/` and request files after the run.

Visual semantics and rendered title correctness remain false in machine reports
until a human reviews the generated PNG.
