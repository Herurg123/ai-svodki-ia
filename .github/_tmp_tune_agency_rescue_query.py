from pathlib import Path

QUERY_OLD = "latest major artificial intelligence news"
QUERY_NEW = "latest artificial intelligence funding acquisition models chips data centers cybersecurity"


def replace_required(path: str, old: str, new: str, expected_min: int = 1) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count < expected_min:
        raise SystemExit(f"expected at least {expected_min} occurrences in {path}, found {count}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# The first live rescue proved that the generic query can complete with zero
# sources even when fresh Reuters material exists. Keep one date-free search,
# but expose the main event axes that current-news ranking should cover.
p = Path("automation/scripts/ensure_story_coverage.py")
text = p.read_text(encoding="utf-8")
if text.count(f'required_query = "{QUERY_OLD}"') < 2:
    raise SystemExit("expected sentinel + agency rescue query assignments")
# Keep the zero-pool sentinel unchanged. Only tune the second occurrence, which
# belongs to build_agency_rescue_prompt().
needle = f'required_query = "{QUERY_OLD}"'
first = text.index(needle)
second = text.index(needle, first + len(needle))
text = text[:second] + text[second:].replace(needle, f'required_query = "{QUERY_NEW}"', 1)
text = text.replace('AGENCY_RESCUE_VERSION = 1', 'AGENCY_RESCUE_VERSION = 2', 1)
text = text.replace('"label": "Fresh Reuters/AP source-health rescue v1"', '"label": "Fresh Reuters/AP source-health rescue v2"', 1)
p.write_text(text, encoding="utf-8")

# Version the source-health recovery boundary with the changed rescue semantics,
# so a saved v1 zero-result rescue cannot be reused after this fix.
p = Path("automation/scripts/ensure_story_coverage_policy.py")
text = p.read_text(encoding="utf-8")
if 'SOURCE_HEALTH_CONTRACT_VERSION = 1' not in text:
    raise SystemExit("source health contract v1 marker missing")
text = text.replace('SOURCE_HEALTH_CONTRACT_VERSION = 1', 'SOURCE_HEALTH_CONTRACT_VERSION = 2', 1)
p.write_text(text, encoding="utf-8")

# Focused unit expectations follow the production query. The zero-pool sentinel
# test remains on its intentionally generic query.
p = Path("automation/tests/test_agency_rescue.py")
text = p.read_text(encoding="utf-8")
text = text.replace(
    'metadata("latest major artificial intelligence news")',
    f'metadata("{QUERY_NEW}")',
    1,
)
text = text.replace(
    'self.assertIn("latest major artificial intelligence news", call["prompt"])',
    f'self.assertIn("{QUERY_NEW}", call["prompt"])',
    1,
)
p.write_text(text, encoding="utf-8")

# Docs state the exact bounded rescue query. Preserve sentinel wording where it
# intentionally refers to its own generic query; replace only rescue passages.
for path in ("README.md", "automation/README.md", "AGENTS.md"):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    rescue_anchor = (
        "используется как bounded `fresh_agency_rescue`: один date-free запрос\n"
        f"`{QUERY_OLD}` с API domain filter только на\nReuters + AP."
    )
    rescue_new = (
        "используется как bounded `fresh_agency_rescue`: один date-free запрос\n"
        f"`{QUERY_NEW}` с API domain filter только на\nReuters + AP."
    )
    if rescue_anchor in text:
        text = text.replace(rescue_anchor, rescue_new, 1)
    elif QUERY_NEW not in text:
        raise SystemExit(f"rescue query doc anchor missing in {path}")
    p.write_text(text, encoding="utf-8")

Path(".github/_tmp_tune_agency_rescue_query.py").unlink()
