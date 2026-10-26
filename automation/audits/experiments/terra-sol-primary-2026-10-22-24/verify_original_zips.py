#!/usr/bin/env python3
"""Проверить неизменённые оригинальные Terra/Sol ZIP в публичном Git-архиве."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    data = json.loads((root / "ORIGINAL_ZIP_MANIFEST.json").read_text(encoding="utf-8"))
    entries = data["originals"]
    if len(entries) != 8:
        raise ValueError(f"Expected 8 original ZIPs, got {len(entries)}")
    filenames = []
    for record in entries:
        rel = Path(record["repo_path"])
        filename = rel.name
        if not filename.endswith(".zip") or filename in filenames:
            raise ValueError(f"Invalid or duplicate original filename: {filename}")
        filenames.append(filename)
        src = root / "originals" / filename
        if not src.is_file():
            raise FileNotFoundError(src)
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        expected = record["sha256"].lower()
        if digest != expected:
            raise ValueError(f"SHA-256 mismatch: {filename}: {digest} != {expected}")
        with zipfile.ZipFile(src) as z:
            if not z.namelist():
                raise ValueError(f"Empty original ZIP: {filename}")
            damaged = z.testzip()
            if damaged is not None:
                raise ValueError(f"Corrupted ZIP member {filename}: {damaged}")
        print(f"OK {digest}  {filename}")
    actual = {p.name for p in (root / "originals").glob("*.zip")}
    if actual != set(filenames):
        raise ValueError(f"Unexpected / missing archive ZIPs: {actual ^ set(filenames)}")
    print(f"PASS: {len(entries)} original immutable ZIPs; SHA-256 + CRC verified")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Archive verification failed: {exc}", file=sys.stderr)
        sys.exit(1)
