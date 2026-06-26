# Jackson annotations catalog alias

## Context

Downstream repositories (`bluetape4k-projects`, `bluetape4k-exposed`, and
`bluetape4k-graph`) still read the `jackson-annotations` version alias from the
central `bt4k` catalog when they add dependency-management entries.

## Decision

Keep the Jackson 2 BOM aliases on the BOM release line:

- `jackson = "2.22.0"`
- `jackson2 = "2.22.0"`

Restore the downstream compatibility alias with the artifact's published
version string:

- `jackson-annotations = "2.22"`

`com.fasterxml.jackson:jackson-bom` publishes `2.22.0`, but
`com.fasterxml.jackson.core:jackson-annotations` publishes `2.22`; using
`2.22.0` for annotations fails dependency resolution.

## Verification

- Maven metadata confirmed `jackson-bom:2.22.0` exists.
- Maven metadata confirmed `jackson-annotations:2.22` exists.
- `bluetape4k-exposed`, `bluetape4k-projects`, and `bluetape4k-graph`
  `compileTestKotlin --warning-mode all --rerun-tasks --no-configuration-cache`
  passed with this catalog file.
