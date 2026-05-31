# Projects 1.10.0 BOM handoff

## Context

`bluetape4k-projects` 1.10.0 was released and `bluetape4k-bom:1.10.0` is visible
from Maven Central.

## Decision

Promote the centrally managed `bluetape4k-bom` version from 1.9.2 to 1.10.0
while leaving independent repository BOM versions unchanged.

## Outcome

The shared catalog now resolves `io.github.bluetape4k:bluetape4k-bom` from the
stable 1.10.0 release.

## Verification

- Maven Central HTTP 200 for `bluetape4k-bom:1.10.0`.

