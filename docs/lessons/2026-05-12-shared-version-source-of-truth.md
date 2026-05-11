# Shared Version Source Of Truth

## Context

Dependabot can raise compatible-looking upgrades in only one repository, which
creates delayed failures when another bluetape4k repository keeps an older
shared dependency or plugin line.

## Lessons

- Treat `bluetape4k-dependencies/gradle/libs.versions.toml` as the explicit
  source of truth for shared aliases, not `bluetape4k-projects`.
- Keep compatibility-line aliases separate. Examples: `kafka3`/`kafka4`,
  `jackson2`/`jackson3`, `spring-boot3`/`spring-boot4`, and
  `spring-kafka`/`spring-kafka4`.
- Verify sync scripts as reusable operations: compile them, run unit tests,
  run `--check` against the workspace, and prove `--write` resolves drift in
  a fixture.
- Merge downstream catalog alignment before enabling central CI checks that
  clone remote `develop`, otherwise the central PR can correctly fail against
  still-drifting downstream repositories.

## Follow-Up Rule

When a shared version changes, update the source block first, run
`scripts/sync-shared-versions.py --workspace .. --write --check --summary`, and
open downstream PRs as one coordinated batch.
