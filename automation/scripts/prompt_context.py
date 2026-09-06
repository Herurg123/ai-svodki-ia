"""Lossless prompt JSON and explicit editorial prefix caching.

Saved artifacts keep their existing format and identity. Cache settings affect
only the supported Terra transport, never search slots or recovery decisions.
"""
from __future__ import annotations

import json
from typing import Any


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def editorial_input(prompt: str, model: str) -> dict[str, Any]:
    marker = "=== ARCHIVE_CONTEXT_END ==="
    if model != "gpt-5.6-terra" or prompt.count(marker) != 1:
        return {"input": prompt}
    boundary = prompt.index(marker) + len(marker)
    # One user message and the exact original text order are retained. Only the
    # shared archive boundary is explicit; implicit full-message caching remains
    # available for exact request repeats, including SDK retries.
    return {
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": prompt[:boundary],
             "prompt_cache_breakpoint": {"mode": "explicit"}},
            {"type": "input_text", "text": prompt[boundary:]},
        ]}],
        # extra_body works with the production-pinned SDK even if the newer
        # cache option is not yet exposed as a named Python argument.
        "extra_body": {"prompt_cache_options": {"mode": "implicit"}},
    }
