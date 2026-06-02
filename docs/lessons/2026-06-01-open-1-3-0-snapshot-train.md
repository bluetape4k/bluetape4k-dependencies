# 2026-06-01 Open 1.3.0 Snapshot Train

## Context

`bluetape4k-dependencies` `1.2.0` was published with stable upstream BOMs.
After release, publishable library repositories need to validate the next minor
development lines together.

## Decision

Keep the downstream consumer alias at the latest released
`bluetape4k-dependencies:1.2.0`, but move managed upstream BOM refs to their
next `-SNAPSHOT` lines for the `1.3.0` train.

## Outcome

Sibling library repositories can sync their version catalogs from
`bluetape4k-dependencies` and resolve the next internal snapshot line.

## Verification

- Source-of-truth upstream BOM refs use the next `-SNAPSHOT` versions.
- `scripts/sync-shared-versions.py --check --summary` passes against sibling
  library repositories after this change.
- `./gradlew help --no-daemon --console=plain` resolves the updated catalog.
