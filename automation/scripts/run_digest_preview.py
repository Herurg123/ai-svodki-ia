#!/usr/bin/env python3
"""Run generate_digest_preview with resilient editorial handling.

The underlying generator writes research and parsed editorial artifacts before
its final editorial-policy validation. This wrapper fixes one known false
positive in the policy validator and can let an initial run continue to the
coverage stage when paid research completed but the provisional editorial did
not yet pass all final checks.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PREVIEW_ROOT = REPOSITORY_ROOT / "automation" / "preview"
AGENT_ERROR = "Используй «агент ИИ», а не AI agent или AI-агент."


def actual_prohibited_agent_form(text: str) -> bool:
    """Return True only for actual forbidden noun forms, not product names.

    In particular, ``Meta AI агентные функции`` is valid: ``Meta AI`` is the
    product name and ``агентные`` is an adjective. The former validator used
    ``AI[- ]агент...`` and incorrectly rejected that phrase.
    """

    patterns = (
        r"\bAI\s+agents?\b",
        r"\bAI[- ]агент(?:а|у|ом|е|ы|ов|ам|ами|ах)?\b",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def patch_editorial_policy() -> None:
    import editorial_policy
    import generate_digest_preview

    original: Callable[..., tuple[list[str], list[str], dict[str, Any]]] = (
        editorial_policy.validate_article_policy
    )

    def corrected_validate_article_policy(
        article_html: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[list[str], list[str], dict[str, Any]]:
        errors, warnings, analysis = original(article_html, *args, **kwargs)
        if AGENT_ERROR in errors:
            try:
                visible_text = editorial_policy.parse_article(article_html).visible_text
            except Exception:
                visible_text = article_html
            if not actual_prohibited_agent_form(visible_text):
                errors = [error for error in errors if error != AGENT_ERROR]
                warnings = list(warnings) + [
                    "Исправлен ложный policy match: название продукта Meta AI "
                    "перед прилагательным «агентные» не является формой AI-агент."
                ]
        return errors, warnings, analysis

    editorial_policy.validate_article_policy = corrected_validate_article_policy
    # generate_digest_preview imported the function directly, so patch its
    # local binding as well.
    generate_digest_preview.validate_article_policy = corrected_validate_article_policy


def publication_date_from_argv(argv: list[str]) -> str | None:
    try:
        index = argv.index("--publication-date")
    except ValueError:
        return None
    if index + 1 >= len(argv):
        return None
    value = argv[index + 1].strip()
    return value or None


def provisional_artifact_is_reusable(output_dir: Path) -> bool:
    required = (
        output_dir / "run-info.json",
        output_dir / "candidates.json",
        output_dir / "research-output-raw.json",
    )
    if not all(path.is_file() for path in required):
        return False
    try:
        run_info = json.loads((output_dir / "run-info.json").read_text(encoding="utf-8"))
        candidates = json.loads((output_dir / "candidates.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(run_info, dict) or not isinstance(candidates, dict):
        return False
    research = run_info.get("research")
    if not isinstance(research, dict) or research.get("status") != "ok":
        return False
    if not isinstance(candidates.get("candidates"), list):
        return False
    # A parsed editorial response is useful but not mandatory. Research-only
    # recovery must remain possible after an editorial transport failure.
    return True


def main() -> int:
    allow_provisional = False
    forwarded: list[str] = [sys.argv[0]]
    for arg in sys.argv[1:]:
        if arg == "--allow-provisional-editorial":
            allow_provisional = True
        else:
            forwarded.append(arg)
    sys.argv = forwarded

    patch_editorial_policy()
    import generate_digest_preview

    result = int(generate_digest_preview.main())
    if result == 0 or not allow_provisional:
        return result

    publication_date = publication_date_from_argv(forwarded)
    if not publication_date:
        return result
    output_dir = PREVIEW_ROOT / publication_date
    if not provisional_artifact_is_reusable(output_dir):
        return result

    print(
        "Initial editorial is provisional, but paid research is reusable; "
        "continuing to the 5+2 coverage and editorial-repair stage."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
