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
