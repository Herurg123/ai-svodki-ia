# Sol 6.1 Editorial: preservation of original evidence

This directory is intended to hold the **original, byte-for-byte GitHub Actions ZIP evidence** for the closed Sol 6.1 Editorial experiment (29 October–1 November 2026).

## Canonical preservation bundle

`sol61-editorial-evidence-2026-10-29_2026-11-01.zip`

Expected ZIP SHA-256:

`5a6fb1ce1dd0c01c747c3c851e7cf4384c19dd9a5f3ddfc9a076c1bc60c19c84`

Expected size: **645940 bytes**.

The bundle contains four unchanged original GitHub Actions artifact ZIPs under `original-artifacts/`, plus `README.md`, `preservation-manifest.json`, and `SHA256SUMS.txt`. Original ZIPs were downloaded from GitHub Actions and verified against their GitHub SHA-256. Their 42 internal manifest entries were also checked against the actual files.

| Date | GitHub run | Artifact ID | Version |
| --- | --- | --- | --- |
| 2026-10-29 | [40804252969](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40804252969) | 12868162007 | V1 |
| 2026-10-30 | [40989608475](https://github.com/Herurg123/ai-svodki-ia/actions/runs/40989608475) | 12948938021 | V1 |
| 2026-10-31 | [41159627400](https://github.com/Herurg123/ai-svodki-ia/actions/runs/41159627400) | 13027225563 | V1 |
| 2026-11-01 | [41263709199](https://github.com/Herurg123/ai-svodki-ia/actions/runs/41263709199) | 13066318415 | V2 |

The historical [evidence-index.json](../evidence-index.json) and [RESULTS_AND_RESTART.md](../RESULTS_AND_RESTART.md) are authoritative and already versioned in Git, so the bundle links to these files rather than reconstituting them from experimental output.

**Privacy:** This repository is public. The archive includes exact full Terra prompts and original model outputs. A byte-level heuristic scan found no apparent API secrets, passwords, private keys, or personal email addresses, and apparent key-like strings were publicly available article URL slugs. Automated scans do not guarantee absence of sensitive data.

**Important:** The ZIP itself is essential. An index or this README on its own is **not** permanent preservation of the original evidence. Do not merge a PR that lacks the exact ZIP. No new model runs or paid API calls are necessary.

## Verification

```bash
sha256sum sol61-editorial-evidence-2026-10-29_2026-11-01.zip
unzip -t sol61-editorial-evidence-2026-10-29_2026-11-01.zip
```

Expected SHA-256 values for each unchanged inner ZIP are in [SHA256SUMS.txt](SHA256SUMS.txt) and in the canonical historical evidence index. Keeping the archive in Git avoids GitHub Actions' finite artifact retention, provided the Git repository and its history are preserved.
