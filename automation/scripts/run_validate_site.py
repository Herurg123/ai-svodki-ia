#!/usr/bin/env python3
"""Run validate_site with the shared editorial-policy runtime correction."""
from __future__ import annotations

from editorial_policy_runtime import patch_editorial_policy


def main() -> int:
    import validate_site

    patch_editorial_policy(validate_site)
    return int(validate_site.main())


if __name__ == "__main__":
    raise SystemExit(main())
