# Issue 78 Exposed Plugin Catalog Alias

## Context

Downstream repositories need JetBrains' Exposed Gradle plugin for migration
script generation. The plugin version must follow the shared Exposed
compatibility line instead of being pinned separately in each repository.

## Decision

Add `exposed-plugin` to the central catalog and point it at the existing
`exposed` version ref.

## Outcome

Downstream repositories can use `alias(bt4k.plugins.exposed.plugin)` after
adopting the catalog train that contains this change.

## Verification

- `scripts/sync-managed-catalog.py --workspace /Users/debop/work/bluetape4k --check --summary`
- `./gradlew build`
- `git diff --check`

## Future Guard

When the catalog source changes, cut a `catalog/YYYY-MM-DD-NN` tag and make
downstream repositories depend on that immutable ref instead of duplicating the
plugin version locally.
