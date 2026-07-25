#!/usr/bin/env python3
"""Shared runtime correction for the editorial AI-agent wording policy.

The repository policy rejects the noun forms ``AI agent`` and ``AI-агент``.
The historical regular expression also rejected legitimate product-name
phrases such as ``Meta AI агентные функции`` because it treated the adjective
``агентные`` as a noun.  Production entry points import this module before
calling the shared editorial validator.
"""
from __future__ import annotations

import re
from typing import Any, Callable

AGENT_ERROR = "Используй «агент ИИ», а не AI agent или AI-агент."
Validator = Callable[..., tuple[list[str], list[str], dict[str, Any]]]


def actual_prohibited_agent_form(text: str) -> bool:
    """Return True only for the explicitly forbidden noun forms."""

    patterns = (
        r"\bAI\s+agents?\b",
        r"\bAI[- ]агент(?:а|у|ом|е|ы|ов|ам|ами|ах)?\b",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def wrap_validator(original: Validator) -> Validator:
    """Wrap one validator while preserving every unrelated policy error."""

    if getattr(original, "_ai_svodki_agent_policy_fixed", False):
        return original

    def corrected(
        article_html: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[list[str], list[str], dict[str, Any]]:
        errors, warnings, analysis = original(article_html, *args, **kwargs)
        if AGENT_ERROR not in errors:
            return errors, warnings, analysis

        try:
            import editorial_policy

            visible_text = editorial_policy.parse_article(article_html).visible_text
        except Exception:
            visible_text = article_html

        if actual_prohibited_agent_form(visible_text):
            return errors, warnings, analysis

        filtered = [error for error in errors if error != AGENT_ERROR]
        updated_warnings = list(warnings)
        updated_warnings.append(
            "Игнорировано ложное совпадение AI + прилагательное «агентный»: "
            "название продукта с AI не является формой AI-агент."
        )
        return filtered, updated_warnings, analysis

    setattr(corrected, "_ai_svodki_agent_policy_fixed", True)
    setattr(corrected, "__wrapped__", original)
    return corrected


def patch_editorial_policy(*consumer_modules: Any) -> Validator:
    """Patch the shared module and any direct-import consumer bindings."""

    import editorial_policy

    corrected = wrap_validator(editorial_policy.validate_article_policy)
    editorial_policy.validate_article_policy = corrected
    for module in consumer_modules:
        if hasattr(module, "validate_article_policy"):
            module.validate_article_policy = corrected
    return corrected
