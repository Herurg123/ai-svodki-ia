#!/usr/bin/env python3
"""Validate Dzen RSS while preserving the canonical generated footer image.

The historical validator lives in validate_dzen_feed_core.py. This thin layer
allows exactly one generated trailing digest footer in content:encoded, then
hands the remaining article HTML to the unchanged strict validator. Arbitrary
inline images remain forbidden.
"""

from __future__ import annotations

import re
from typing import Any

import validate_dzen_feed_core as core

FOOTER_TARGET_URL = "https://dzen.ru/rybv"
FOOTER_FILENAME = "_footer-scr.png"
FOOTER_ALT = "Подписаться на канал"

RSS_FOOTER_PATTERN = re.compile(
    r"\s*<p\b(?=[^>]*\bclass\s*=\s*(['\"])digest-footer\1)[^>]*>\s*"
    r"<a\b(?=[^>]*\bhref\s*=\s*(['\"])https://dzen\.ru/rybv\2)[^>]*>\s*"
    r"(?P<img><img\b[^>]*>)\s*</a>\s*</p>\s*$",
    re.IGNORECASE | re.DOTALL,
)
ATTRIBUTE_PATTERN = re.compile(
    r"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(['\"])(.*?)\2",
    re.DOTALL,
)

_expected_footer_image_url = "https://rybalka.one/posts/_footer-scr.png"
_original_validate_article_html = core.validate_article_html
_original_validate_feed = core.validate_feed


def strip_and_validate_rss_footer(
    html: str,
    *,
    report: dict[str, Any],
    item_label: str,
) -> str:
    """Remove only the exact generated trailing footer before strict inspection.

    A missing footer remains backward-compatible for historical items. Any
    malformed, duplicated, non-trailing, or arbitrary inline <img> remains in
    the HTML and is rejected by the historical validator.
    """
    match = RSS_FOOTER_PATTERN.search(html)
    if match is None:
        return html

    attrs = {
        name.lower(): value.strip()
        for name, _quote, value in ATTRIBUTE_PATTERN.findall(match.group("img"))
    }
    src = attrs.get("src", "")
    alt = attrs.get("alt", "")

    if src != _expected_footer_image_url:
        core.add_issue(
            report,
            "errors",
            "rss_footer_src",
            f"Footer RSS должен использовать {_expected_footer_image_url}.",
            item_label,
        )
    if alt != FOOTER_ALT:
        core.add_issue(
            report,
            "errors",
            "rss_footer_alt",
            f"Footer RSS должен использовать alt «{FOOTER_ALT}».",
            item_label,
        )

    return html[: match.start()].rstrip()


def validate_article_html(
    html: str,
    *,
    report: dict[str, Any],
    item_label: str,
    strict_editorial: bool,
) -> None:
    cleaned = strip_and_validate_rss_footer(
        html,
        report=report,
        item_label=item_label,
    )
    _original_validate_article_html(
        cleaned,
        report=report,
        item_label=item_label,
        strict_editorial=strict_editorial,
    )


def validate_feed(
    rss_path,
    *,
    site_base_url: str,
    latest_only: bool,
    strict_editorial: bool,
):
    global _expected_footer_image_url
    _expected_footer_image_url = site_base_url.rstrip("/") + "/" + FOOTER_FILENAME
    return _original_validate_feed(
        rss_path,
        site_base_url=site_base_url,
        latest_only=latest_only,
        strict_editorial=strict_editorial,
    )


# The core validator resolves these names from its own module globals at runtime.
# Patch only the two extension points needed for the generated footer contract.
core.validate_article_html = validate_article_html
core.validate_feed = validate_feed

# Preserve the existing CLI and public helpers for callers/tests.
main = core.main
parse_args = core.parse_args

if __name__ == "__main__":
    raise SystemExit(main())
