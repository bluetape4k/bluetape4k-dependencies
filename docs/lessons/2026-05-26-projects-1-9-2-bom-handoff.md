# Projects 1.9.2 BOM handoff

## Context

`bluetape4k-projects` 1.9.2 was released and `bluetape4k-bom:1.9.2` is visible
from Maven Central.

## Decision

Promote the managed projects BOM reference from `1.9.2-SNAPSHOT` to the stable
1.9.2 release in the dependencies catalog.

## Outcome

The central dependency catalog now points at the released
`io.github.bluetape4k:bluetape4k-bom` 1.9.2 artifact. The final dependencies
BOM still needs its own release-train gate after downstream repository versions
are selected.

## Verification

- Maven Central HTTP 200 for `bluetape4k-bom:1.9.2`
- `./gradlew build`
