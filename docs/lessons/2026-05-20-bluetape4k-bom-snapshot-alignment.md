# bluetape4k BOM Snapshot Alignment

## Context

The Fory 0.17 upgrade required `bluetape4k-projects` artifacts rebuilt against
the new Fory API. Downstream repositories still resolved `bluetape4k-bom:1.8.0`
from `bluetape4k-dependencies`, so they mixed Fory 0.17 with older
`bluetape4k-io` binaries and failed with `NoSuchMethodError`.

## Decision

Move the central `bluetape4k-bom` catalog entry to `1.8.1-SNAPSHOT`, matching
the published `bluetape4k-projects` snapshot line.

## Outcome

Downstream repositories should receive the rebuilt 1.8.1 artifacts through the
central BOM instead of repo-local overrides.

## Verification

Checked Maven snapshot metadata for `bluetape4k-io:1.8.1-SNAPSHOT` and
`bluetape4k-assertions:1.8.1-SNAPSHOT`; both exist after the projects snapshot
publish.

## Future Guidance

When upgrading shared runtime libraries in `bluetape4k-dependencies`, align the
core bluetape4k BOM version with the published snapshot line before syncing
downstream repositories.
