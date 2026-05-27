# Lesson: leader 0.2.2 catalog promotion

**Date**: 2026-05-27

## Context

`bluetape4k-leader` 0.2.2 was published through its tag-driven release workflow
after the patch issues and README version guidance were merged. Maven Central
metadata and representative POMs returned HTTP 200 for `0.2.2`.

## Decision

Promote the managed `bluetape4k-leader-bom` catalog ref from
`0.2.2-SNAPSHOT` to the published `0.2.2` release in the open
`bluetape4k-dependencies` 1.1.4 train. The required managed-catalog CI check
also surfaced pre-existing Javers generated-section drift, so the same PR
regenerated the missing `javers-ddd` and `javers-exposed` aliases and BOM
constraints.

## Outcome

Downstream repositories consuming the checked-out dependencies catalog can align
with the stable leader 0.2.2 artifacts instead of the snapshot line. The
generated managed catalog is back in sync with the current sibling repository
module set.

## Verification

- Maven Central HEAD checks returned 200 for `bluetape4k-leader-bom`,
  `bluetape4k-leader-core`, `bluetape4k-leader-redis-redisson`, and
  `bluetape4k-leader-spring-boot` 0.2.2 POMs.
- `scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k --write --check --summary`.
- `./gradlew build --no-daemon`.

## Future Guidance

After each upstream stable publish, verify Maven Central visibility before
removing `-SNAPSHOT` from the corresponding `bluetape4k-dependencies` catalog
version ref.
