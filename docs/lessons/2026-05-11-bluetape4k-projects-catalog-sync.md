# Managed catalog sync

## Context

`gradle/libs.versions.toml` listed only a subset of managed modules. Manual
updates are easy to miss because several bluetape4k repositories derive project
names dynamically from `settings.gradle.kts` and module directories.

## Decision

Maintain managed catalog aliases and BOM constraints through
`scripts/sync-managed-catalog.py`.

## Outcome

The script discovers modules from sibling managed repositories, rewrites
generated blocks in `gradle/libs.versions.toml` and `build.gradle.kts`, and
fails `--check` when generated content drifts.

## Verification

- `scripts/sync-managed-catalog.py --write --check --summary`
- `python3 -m unittest tests/test_sync_managed_catalog.py`
- `./gradlew build`

## Future Guard

When a managed module is added, removed, or renamed, run the sync script instead
of editing generated blocks manually.
