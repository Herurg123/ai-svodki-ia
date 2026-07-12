# Rollback runbook

## Current implementation

Only an artifact-only rollback drill exists. It copies the current repository
`posts/` tree into a snapshot, simulates a release in a temporary directory,
and restores that temporary directory from the snapshot. The live `posts/`
tree is read-only throughout the drill.

The standalone drill writes plans and reports only under
`automation/preview/rollback-drill`. The shared plan builders accept that path
through the explicit `allowed_preview_roots` configuration; they must continue
to reject every unlisted preview path.

## Required data for a future production rollback

- release ID and production commit SHA;
- pre-release snapshot manifest;
- SHA-256 manifest of every file in the snapshot;
- previous site and RSS validation reports;
- incident reason and operator approval;
- the exact deployment run that introduced the faulty release.

## Future manual rollback procedure

1. Freeze all new publication and deployment jobs.
2. Identify the last known-good pre-release snapshot.
3. Verify every snapshot file and the full tree SHA-256.
4. Restore the snapshot into an isolated staging directory.
5. Run site validation and the Dzen RSS contract against staging.
6. Compare staging with the intended rollback manifest.
7. Obtain explicit production approval.
8. Restore `posts/` on `main` in a dedicated rollback commit.
9. Deploy through the separately guarded production deployment workflow.
10. Verify the public HTML, image URLs, RSS, and Dzen import state.
11. Preserve the rollback reports and open an incident record.

## Prohibited shortcuts

- rolling back directly from `automation-prep`;
- restoring an unverified ZIP manually over FTP;
- using the golden fixture as a production snapshot;
- deleting the failed release without preserving evidence;
- enabling a schedule before the rollback path has passed a production drill.
