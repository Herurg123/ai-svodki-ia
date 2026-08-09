# Repository instructions

`README.md` and `automation/README.md` are part of the project's maintained
contract. They must describe the current project, not a previous version of it.

Any pull request that materially changes project behavior or structure must
update every affected README in the same pull request. This includes changes to
architecture, workflows and schedules, configuration and defaults, models and
budgets, editorial rules, publication and deployment, recovery, cleanup, and
operator-facing commands.

Before declaring such a change complete:

1. Compare the affected README sections with the implemented code, workflows,
   configuration, and canonical specifications.
2. Update the README text and any documentation-contract tests in the same
   change.
3. Run the relevant offline checks.

Do not merge a material project update while an affected README still describes
the old behavior. If a change truly has no documentation impact, state that
explicitly in the pull request description.

## GitHub change workflow

Do not commit project changes directly to `main`. Use a dedicated branch and a
pull request, run CI, and inspect the resulting diff before merge.

A pull request must not be merged merely because its checks are green or because
a previous message asked to continue the work. Merge only after the project
owner gives a separate explicit merge command for that prepared pull request.
Production recovery or publication that depends on the change must wait for that
merge command; preparation, diagnostics, CI and diff review may proceed before
it.

## Repository hygiene operational boundary

The scheduled repository hygiene workflow may mutate only explicitly classified
ephemeral GitHub objects: old merged branch refs, safe Actions artifacts, and
the enabled state of orphaned Actions workflows. It must not edit tracked
project files, `main`, releases, tags, or published/editorial content.

Source-code, test, prompt, configuration, fixture, and specification orphan
detection is report-only. Any tracked-file cleanup still follows the normal
branch → pull request → CI → diff review → separate explicit merge command.

The existing 32-day repository/public-content cleanup remains a separate,
documented operational workflow. The repository hygiene exception does not
broaden its scope or weaken its retention and validation rules.

## Permanent digest footer asset

`posts/_footer-scr.png` is a permanent production asset, not dated release
content. Every newly rendered digest page and the RSS article content for a new
release must end with a linked footer image pointing to `https://dzen.ru/rybv`;
the image source is `https://rybalka.one/posts/_footer-scr.png` and its displayed
width must not exceed 50%.

Every FTP deployment must verify the actual remote presence of
`_footer-scr.png` after normal synchronization and restore it if it is missing.
The scheduled 32-day content cleanup must never classify or delete this file.

## Temporal contract for nightly research

For nightly production, the exact `search_window.end_at` timestamp is the
authoritative current time for research, every coverage pass, and the recall
sentinel. Do not let model/system calendar dates override that timestamp.
Legacy recovery data from a cross-midnight local/UTC window must not be reused
as final research or a terminal zero-pool stop unless it carries the current
temporal-anchor contract version.

## Editorial zero-pool stop

A completed zero-pool result is a normal successful `no-publish`, not a
production failure, but only after the current temporal-anchor contract, all
six mandatory coverage directions, and the current recall sentinel have
completed successfully with no publishable candidate. In that state Image API,
commit, and deploy must remain skipped. Technical partial/error audits remain
fail-closed and red. Recovery must reuse a proven completed editorial stop
without repeating paid research or coverage.
