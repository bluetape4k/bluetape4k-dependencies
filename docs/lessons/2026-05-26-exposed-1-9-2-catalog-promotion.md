# Exposed 1.9.2 Catalog Promotion

## Context

`bluetape4k-exposed` 1.9.2 and `bluetape4k-projects` 1.9.2 are both visible
from Maven Central, but the dependencies catalog still referenced their
`1.9.2-SNAPSHOT` BOMs.

## Decision

Promote the managed `bluetape4k-bom` and `bluetape4k-exposed-bom` references to
the published `1.9.2` versions before downstream consumers move off snapshots.

## Outcome

The 1.1.4 dependencies line can serve as the stable downstream BOM/catalog line
for consumers that need Exposed 1.9.2.

## Verification

- Maven Central HTTP 200 for `bluetape4k-bom:1.9.2`
- Maven Central HTTP 200 for `bluetape4k-exposed-bom:1.9.2`

## Future Notes

Do not update downstream workshop/example repositories to a new
`bluetape4k-dependencies` version until this repository has published that BOM
version or the downstream build uses a checked-out catalog ref.
