# Contributing

## Issue labels

Every actionable issue must have:

- one type: `type:bug`, `type:feature`, or `type:chore`;
- one priority: `priority:P0`, `priority:P1`, `priority:P2`, or `priority:P3`;
- at least one area: `area:api`, `area:ci`, `area:docs`, or `area:security`.

P0 means an active critical incident. P1 is urgent customer or financial risk.
P2 is planned product or reliability work. P3 is maintenance or improvement.

Review the open backlog weekly. Titles must describe an outcome in more than ten
characters. Close duplicates, archive obsolete work, and ensure every active
issue has current labels and acceptance criteria. Implementation may be tracked
in Linear, but a GitHub coordination issue should link to the Linear project
when repository-level visibility is needed.

## Pull requests

Use conventional commit subjects so Release Please can generate useful release
notes. Pull requests must link the tracked issue, provide exact validation
commands, assess security/privacy impact, and state rollout and rollback steps.
The owner listed in `CODEOWNERS` must review changes, and CI, Security, and
Droid Auto Review must pass. See [security.md](security.md) for the documented
branch-protection limitation and portable enforcement controls.
