# Search baseline: pre-hybrid 2026-08-09

Canonical pre-hybrid repository state:

- branch: `archive/search-baseline-pre-hybrid-2026-08-09`;
- commit: `d926a3abf8b9443f58f303d984ef79fdc289fc3e`;
- meaning: the complete production repository immediately before the always-on
  hybrid completeness layer was introduced.

This baseline exists for retrospective analysis of releases created by the old
search mechanism, regression comparison, and emergency rollback/reference. The
commit SHA is the canonical immutable identity; the archive branch is a stable
human-readable pointer to it.

Do not move, rewrite, reuse, or delete this branch. Repository hygiene must
classify it as `protected` with reason `permanent_archive_branch`. Any future
replacement baseline must get a new branch and a new manifest rather than
mutating this one.
