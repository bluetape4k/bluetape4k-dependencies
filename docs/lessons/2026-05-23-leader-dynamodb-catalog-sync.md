# Leader DynamoDB Catalog Sync

## Context

The `develop` CI failed after the 1.0.1 release because the managed-module
catalog check discovered `bluetape4k-leader-dynamodb` in `bluetape4k-leader`,
but `bluetape4k-dependencies` had not regenerated its version catalog and BOM
constraints.

## Decision

Regenerate the managed catalog from the workspace source of truth instead of
manually editing the generated sections.

## Outcome

`bluetape4k-leader-dynamodb` is now present in both `gradle/libs.versions.toml`
and `build.gradle.kts`.

## Verification

- `scripts/sync-managed-catalog.py --write --check --summary`
- `scripts/sync-managed-catalog.py --check --summary`

## Future Guidance

When a managed repository adds a publishable module, rerun the managed catalog
sync before rerunning `bluetape4k-dependencies` CI.
