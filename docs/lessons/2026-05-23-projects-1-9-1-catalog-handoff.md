# Projects 1.9.1 Catalog Handoff

## Context

`bluetape4k-projects` 1.9.1 was released to publish `truncateUtf8` support and
the corresponding `bluetape4k-bom` update. Downstream repositories consume the
core module line through `bluetape4k-dependencies`, so the central BOM/catalog
must move after Maven Central visibility is confirmed.

## Decision

Publish `bluetape4k-dependencies` 1.1.2 with only the projects BOM promotion:
`bluetape4k-bom` moves from 1.9.0 to 1.9.1. Other upstream BOM refs remain on
the already published release train.

## Outcome

The catalog and BOM version were bumped to 1.1.2, and the README/CHANGELOG now
show projects 1.9.1 as the managed core line.

## Verification

- Maven Central HTTP 200 checks passed for all imported upstream BOMs, including
  `io.github.bluetape4k:bluetape4k-bom:1.9.1`.
- `bluetape4k-workshop` clean-cache verification passed
  `:redis-redisson-examples:test` against public projects 1.9.1 artifacts.

## Future Guidance

For patch releases that only move one upstream BOM, keep `bluetape4k-dependencies`
as a narrow patch release. Do not batch unrelated dependency upgrades into the
handoff PR, because downstream consumers need a small, reviewable catalog delta.
