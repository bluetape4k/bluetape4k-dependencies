# Dependency Open Issues

## Context

`bluetape4k-dependencies` issue #39 exposed that
`scripts/sync-dependabot-ignores.py` defaulted to the parent of the workspace
root when launched from this repository. Issues #34 and #35 also promoted two
shared dependencies that affect downstream repositories: MyBatis Dynamic SQL 2.x
and Timefold Solver 2.x. Open Dependabot PRs also proposed shared patch/minor
updates for AWS SDK Java, AWS SDK Kotlin, ClassGraph, and Apache Fory.

## Decision

Keep `gradle/libs.versions.toml` as the source of truth, fix the default
workspace resolver to stop at the `bluetape4k-dependencies` checkout, and
materialize the 2.x versions into downstream repositories through coordinated
PRs.

## Outcome

- MyBatis Dynamic SQL was promoted to `2.0.0`.
- Timefold Solver was promoted to `2.1.0`.
- AWS SDK Java was promoted to `2.44.9`.
- AWS SDK Kotlin was promoted to `1.6.77`.
- ClassGraph was promoted to `4.8.184`.
- Apache Fory core and Kotlin were promoted to `0.17.0`.
- Dependabot ignore sync now defaults to the bluetape4k workspace root.
- `--check` fails when no target Dependabot files are found, preventing silent
  false positives.

## Verification

- `python3 -m unittest tests/test_sync_dependabot_ignores.py tests/test_sync_shared_versions.py tests/test_sync_managed_catalog.py tests/test_triage_dependabot_alerts.py`
- `./gradlew build --no-daemon`
- `scripts/sync-shared-versions.py --workspace /Users/debop/work/bluetape4k --check --summary`
- `scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --check --summary`

The two sync checks reported expected drift because the downstream updates live
in feature worktrees and two previously created Dependabot-ignore PRs were not
merged into the base workspace yet.
