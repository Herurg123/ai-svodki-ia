# Preserved independent review — FAIL

The original Terra report and controls are preserved verbatim. The original
runner uses the scratch repository path recorded in FINDINGS.md. To replay on
another clone, change only its REPO path, then run it offline. The three reviewed
implementation hashes match checkpoint 1cdbb4bafa834d214edaa4a770d9a838242538cc.

These four controls describe synthetic damaged/ambiguous inputs, not observed
production failures. Identical duplicates being collapsed to one is an explicit
policy/diagnostic ambiguity; it does not establish lost distinct events.

Implementation stopped on FAIL. source_value_period.py is an untested draft;
its planned observation IDs are not emitted by the producer yet. Next work must
repair evidence validation, define duplicate semantics, bind each headline to
its own source block, then repeat independent acceptance and complete aggregation.

A new owner-requested production incident on 2026-09-09 interrupted DOCX report
finalization. Point 5 remains unaccepted; no PR, merge, or production invocation.
