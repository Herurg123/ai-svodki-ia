# Experiment: Source Pulse v1.3 parser recursion replay

Date: `2026-09-01`

## Question

Why did ten different Source Pulse sources fail with the identical `RecursionError: maximum recursion depth exceeded` during the production release?

## Production evidence

Saved `source-pulse-2026-09-01.json` reports:

- Source Pulse status: `complete_with_gaps`
- fixed sources: 13
- accepted leads: 0
- paid API calls: 0
- Web Search operations: 0
- ten sources: `parse_error = RecursionError: maximum recursion depth exceeded`
- three sources: unavailable for source-specific transport reasons

The same Python recursion exception across ten unrelated HTML publishers strongly suggests a shared parser/wrapper defect rather than independent source breakage.

## Static code trace

Current production code in `automation/scripts/source_pulse_supplement_v13.py` has the following interaction:

1. `parse_html_index_v13(body, base_url)` starts by calling `v12.parse_html_index_v12(body, base_url)`.
2. `run_source_pulse_v13(...)` captures the old parser in `original_parser`.
3. The wrapper then temporarily assigns `v12.parse_html_index_v12 = parse_html_index_v13` before invoking the v1.2 collector.
4. The v1.2 collector calls its module-level `parse_html_index_v12` symbol, which now points to `parse_html_index_v13`.
5. `parse_html_index_v13` then calls `v12.parse_html_index_v12(...)` again. Because that symbol is still patched to `parse_html_index_v13`, the function calls itself recursively.
6. Recursion continues until Python raises `RecursionError`.
7. `original_parser` is restored only after the collector returns or raises; it is not the function used by the inner call from `parse_html_index_v13`.

The relevant failure is therefore the combination of mutable module monkey-patching and `parse_html_index_v13` looking up the old parser through the same mutable module symbol.

## Minimal offline replay

A minimal isolated replay was executed without network access, source fetching, production APIs, or user-paid resources. The replay mirrors the control-flow shape:

```python
class V12:
    pass

v12 = V12()

def parse_v12(body, base_url):
    return []

v12.parse_html_index_v12 = parse_v12


def parse_v13(body, base_url):
    original = v12.parse_html_index_v12(body, base_url)
    return original

original_parser = v12.parse_html_index_v12
v12.parse_html_index_v12 = parse_v13
try:
    v12.parse_html_index_v12("<html></html>", "https://example.test/")
finally:
    v12.parse_html_index_v12 = original_parser
```

Observed result:

```text
RecursionError: maximum recursion depth exceeded
```

This reproduces the production exception deterministically before any website-specific HTML behavior matters.

## Root cause

**Confirmed shared code regression in Source Pulse v1.3.**

The v1.3 parser intended to extend v1.2 behavior, but it retrieves the v1.2 parser through a symbol that the wrapper itself has already replaced with v1.3.

## Safe fix shape

A production fix should avoid looking up the parent parser through the mutable patched symbol. Suitable designs include:

- capture the original v1.2 parser once and pass it explicitly into the v1.3 parser/closure;
- define a stable module-level reference to the unpatched v1.2 implementation and have v1.3 call that stable reference;
- refactor v1.2 collection to accept a parser dependency explicitly instead of monkey-patching a module symbol.

The smallest patch is not automatically the best patch. The chosen approach should make accidental self-recursion structurally difficult.

## Required regression tests

At minimum:

1. run the exact wrapper path that performs the parser substitution;
2. parse a small HTML fixture containing a normal article link/date signal;
3. assert no `RecursionError` and that v1.2 baseline extraction still participates;
4. assert v1.3-specific parsing additions are present;
5. assert the original v1.2 parser is restored after both success and exception paths;
6. keep the test offline and deterministic.

A neighboring test should cover a non-HTML source or source-unavailable path so the fix does not accidentally change Source Pulse's existing fail-open/`complete_with_gaps` reporting semantics.

## Contract checks for the eventual fix

The production fix must preserve:

- zero paid API calls for Source Pulse;
- zero Web Search operations for Source Pulse;
- Source Pulse as an independent second discovery plane;
- Source Pulse inability to close Search-derived regional gaps by itself;
- deterministic candidate merge/dedupe behavior;
- source-health diagnostics and `complete_with_gaps` behavior for genuine source failures.

## Decision

**GO for a separate production-code fix with offline regression coverage.**

The cause is reproduced and deterministic. No further live-source experiment is necessary to establish the recursion defect itself.

This audit experiment does not modify runtime code.
