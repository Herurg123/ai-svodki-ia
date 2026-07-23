# Production orchestrator: dry-run contract

## Current status

The production orchestrator is simulation-only. It cannot publish, commit, push,
use FTP, access repository secrets, or modify the live `posts/` directory.

Machine-readable configuration:

`automation/config/orchestrator.json`

Plan and rollback report files may be written only under the explicitly
allowlisted preview roots:

- `automation/preview/production-orchestrator`
- `automation/preview/rollback-drill`

Any other preview root, absolute path, or path containing `..` must be rejected.

The following values must remain false while production is frozen:

- `publication_enabled`
- `rollback_execution_enabled`
- `allow_schedule`
- `allow_repository_write`
- `allow_ftp`
- `allow_external_network`

## Dry-run sequence

1. Build and validate an artifact-only release candidate.
2. Run the production gate and require `status: blocked`.
3. Compare the candidate site with the repository `posts/` tree.
4. Create `publication-plan.json` containing deterministic add, update, and
   delete operations.
5. Copy the current `posts/` tree into an artifact-only rollback snapshot.
6. Create `rollback-plan.json` describing the inverse transition.
7. Apply both plans only to a temporary copy under `automation/preview/`.
8. Verify that promotion reproduces the candidate tree exactly.
9. Verify that rollback reproduces the original `posts/` tree exactly.
10. Verify that the real `posts/` tree never changed.

A green workflow means the blocked plan and rollback simulation are valid. It
does not mean production publication is enabled.

## Golden fixture

The accepted release from 2026-07-11 remains a `golden_fixture` with
`production_eligible: false`. It may be used to test the mechanics in an
isolated directory. It must never become a production release.

## Future activation

Production activation requires a separate reviewed change that:

- creates a fresh production-eligible release candidate;
- changes the production configuration explicitly;
- runs only from `main` through a manual approval gate;
- keeps release creation, repository mutation, and FTP deployment as separate
  auditable jobs;
- preserves a validated rollback snapshot before any mutation;
- never reuses the 2026-07-11 golden fixture.
