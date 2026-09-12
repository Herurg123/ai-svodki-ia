#!/usr/bin/env python3
"""Compatibility import surface for active Agency Discovery Rescue v6.

The exact former v5 implementation is preserved in
``agency_discovery_rescue_v5_base.py`` for replay/rollback and source-inspection
contracts. Existing consumers keep importing this stable module path and receive
the additive v6 observability layer without changing search/query semantics.

Removal condition: this shim may be collapsed only after all active Hybrid,
recovery and monkeypatch/test consumers move to the canonical v6 entrypoint and
saved-artifact compatibility has been re-audited. Review no earlier than
2026-10-12.
"""
import agency_discovery_rescue_v6 as _active
from agency_discovery_rescue_v6 import *  # noqa: F401,F403

# Same-day recovery still calls this private compatibility hook directly.
_persist_report = _active._persist_report


def __getattr__(name):
    if hasattr(_active, name):
        return getattr(_active, name)
    return getattr(_active.v5, name)
