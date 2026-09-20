# Sep11 technical follow-up — inert evidence

Start with [HANDOFF_TO_SOL_HIGH.md](HANDOFF_TO_SOL_HIGH.md). Runtime is unchanged.

- `saved-coverage-paid.json`, `saved-coverage-final.json`: complete original Coverage reports.
- `manifest.json`: Actions/artifact identities, original ZIP and release-file hashes.
- `probe_baseline.py`: local baseline mechanism probes; no model/network calls.
- `baseline-results.json`: observed baseline defects, not repaired-runtime acceptance.
- `terra-reference.md`: limited assistant-side reference checks, not production API A/B.

The probe reads immutable Sep11 inputs with `git show` from baseline
`5d15b0f0a220f55a6753412b6e712fd2cd96b06a` and imports the checkout runtime.
Use a baseline checkout for reproduction; use a separate treatment checkout for A/B.
No workflow imports or discovers this directory. Do not import this probe in runtime.
Original artifacts may expire; these committed reports and baseline content preserve
the inputs used by the reproducible counterexamples. Raw historical RSS/newsroom HTML
was not present in those artifacts and must not be reconstructed as authentic proof.
