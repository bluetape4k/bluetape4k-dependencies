# Dependencies 1.1.4 and 1.2.0 BOM train split

## Context

The `bluetape4k-dependencies` 1.1.4 release prep needed to avoid mixing the
`bluetape4k-projects:1.10.0` train with repositories that were still aligned to
the older core BOM line.

## Decision

Use `bluetape4k-dependencies:1.1.4` as a patch train:
`bluetape4k-bom:1.9.2`, `bluetape4k-exposed-bom:1.9.2`, and
`bluetape4k-leader-bom:0.2.2`.

Keep the other managed repository BOMs at the published
`bluetape4k-dependencies:1.1.3` baseline: `bluetape4k-aws-bom:0.2.1`,
`bluetape4k-image-bom:0.1.2`, `bluetape4k-text-bom:0.1.2`,
`bluetape4k-graph-bom:0.4.1`, and `bluetape4k-javers-bom:0.1.2`.

Also keep the 1.1.4 alias/constraint surface aligned to what those BOMs publish.
Do not include `bluetape4k-ktor-*`, `javers-ddd`, `javers-exposed`, or
`bluetape4k-images-ktor` until the corresponding 1.2.0 train BOMs are selected.

Use `bluetape4k-dependencies:1.2.0` as the next minor train with the latest
published repository BOMs, including `bluetape4k-bom:1.10.0`,
`bluetape4k-graph-bom:0.4.2`, `bluetape4k-image-bom:0.2.0`, and
`bluetape4k-leader-bom:0.3.0` after Maven Central visibility is confirmed.

Keep `bluetape4k-dependencies` consumer alias at the latest released version
until 1.1.4 itself is published.

## Outcome

The 1.1.4 catalog avoids the `bluetape4k-bom:1.10.0` compatibility line and
keeps a narrow patch-train surface.

## Verification

- Maven Central HTTP 200 for every retained or promoted internal BOM.
- `scripts/verify-managed-artifacts.py --summary`.
