# Terra 5.6 / Terra 6.1, 28 October 2026: original evidence

**Draft archive staging.** This directory contains verifiable metadata. The exact bundle `terra28-original-evidence-bundle-2026-11-08.zip` must be added to this directory **before merging this PR**. Until the ZIP is present and verified, Git preservation is **not complete**.

## Bundle and provenance

- Package: `terra28-original-evidence-bundle-2026-11-08.zip` (8,605,287 bytes).
- Package SHA-256: `a55ea17c0cab6cb013e5c2409cfe3cfab9d6e06dd4ae7b68bf30518c501dcc95`.
- Contains four **unchanged** original GitHub Actions artifact ZIPs, `MANIFEST.json`, `SHA256SUMS.txt`, and a source README.
- `MANIFEST.json` in this directory records original ZIP SHA-256, IDs, dates and sizes. The nested bundle's manifest preserves the same underlying original artifact records.
- For exact source context, see [RESULT.md](../RESULT.md), [PLAN.md](../PLAN.md) and [EVENTS.md](../EVENTS.md).

## Missing original, no reconstruction

The **full original** Terra 5.6 `daily-production-2026-10-28` (artifact ID `12786364155`, 76,530,263 bytes, SHA-256 `33a9c898549a289163bbafd7528e0d4043afc4b2ff72389f59c7649513ef4bd5`) was **not available** from Actions on 2026-11-08, and the owner has no local copy. Do not claim to have recovered this original. The three separately downloaded original research / coverage / image checkpoints preserve useful *partial* primary evidence, but none is a replacement for the missing full ZIP.

## Public disclosure and independent verification

The original files include prompts, API outputs, request/response metadata, and source URLs. A known URL from `static2.finnhub.io` contains a query parameter named `Authorization`. The owner explicitly accepted publication of the unchanged evidence notwithstanding this third-party URL. Pattern scanning did not find common PEM/Bearer/GitHub/AWS/Google credentials, but no automated scan guarantees absence of all sensitive information. Public Git history is permanent.

Verification on the exact package:

```bash
sha256sum terra28-original-evidence-bundle-2026-11-08.zip
unzip -t terra28-original-evidence-bundle-2026-11-08.zip
python3 - <<'PY'
from zipfile import ZipFile
from hashlib import sha256
import json
p='terra28-original-evidence-bundle-2026-11-08.zip'
with ZipFile(p) as z:
    manifest=json.loads(z.read('MANIFEST.json'))
    for f in manifest['files']:
        b=z.read(f['filename'])
        assert sha256(b).hexdigest()==f['sha256'], f['filename']
print('All four original ZIPs match the manifest')
PY
```

No models, external search or paid API calls were used to regenerate archive data.