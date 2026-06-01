# WIP - bluetape4k-dependencies

Snapshot: 2026-06-01 KST
Scope: dependencies 1.2.0 release train.
Open count: 0 repository issues.

## Current Direction

Prepare and publish `1.2.0` as the next minor dependencies train.

The 1.2.0 BOM should include only Maven Central-visible stable upstream BOMs:

- `bluetape4k-bom:1.10.0`
- `bluetape4k-aws-bom:0.3.0`
- `bluetape4k-exposed-bom:1.10.0`
- `bluetape4k-graph-bom:0.5.0`
- `bluetape4k-image-bom:0.2.0`
- `bluetape4k-javers-bom:0.2.0`
- `bluetape4k-leader-bom:0.3.0`
- `bluetape4k-text-bom:0.2.0`

## Release Gate

- `bluetape4k-graph:0.5.0` was newly published for this train and is Maven
  Central-visible.
- `bluetape4k-exposed:1.10.0` was newly published for this train and is Maven
  Central-visible before downstream `aws`, `javers`, or `leader` release
  dispatch.
- Generated managed aliases and BOM constraints must be regenerated after the
  BOM version selection so newly published modules such as `bluetape4k-images-ktor`,
  `javers-ddd`, and `javers-exposed` are included only when their selected BOMs
  publish them.

## Verification Evidence

- Maven Central returned HTTP 200 for every retained or promoted upstream BOM in
  the 1.2.0 matrix.
- `bluetape4k-exposed-bom:1.10.0` returned HTTP 200 after release workflow
  `https://github.com/bluetape4k/bluetape4k-exposed/actions/runs/26736279613`.
- `bluetape4k-graph-bom:0.5.0` returned HTTP 200 after release workflow
  `https://github.com/bluetape4k/bluetape4k-graph/actions/runs/26734244764`.

## Priority Queue

No assigned open issues are required for this release train.

## WIP Limits

| Lane | Limit | Current next |
|---|---:|---|
| Release | 1 | Finish 1.2.0 before starting the next dependencies governance train. |
