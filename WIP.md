# WIP - bluetape4k-dependencies

Snapshot: 2026-06-26 KST
Scope: dependencies 1.3.0 development line.
Open count: 0 issues.

## Current Direction

`1.2.0` is published. It consumes the following stable upstream BOMs:

- `bluetape4k-bom:1.10.0`
- `bluetape4k-aws-bom:0.3.1`
- `bluetape4k-exposed-bom:1.10.0`
- `bluetape4k-graph-bom:0.5.0`
- `bluetape4k-image-bom:0.2.0`
- `bluetape4k-javers-bom:0.2.0`
- `bluetape4k-leader-bom:0.3.1`
- `bluetape4k-text-bom:0.2.0`

Keep `develop` open for snapshot validation, but do not treat the raw
`*-SNAPSHOT` refs as the final `1.3.0` stable inputs. The current snapshot
development refs are:

- `bluetape4k-bom:1.11.0-SNAPSHOT`
- `bluetape4k-aws-bom:0.4.0-SNAPSHOT`
- `bluetape4k-exposed-bom:1.11.0-SNAPSHOT`
- `bluetape4k-graph-bom:0.6.0-SNAPSHOT`
- `bluetape4k-image-bom:0.3.0-SNAPSHOT`
- `bluetape4k-javers-bom:0.3.0-SNAPSHOT`
- `bluetape4k-leader-bom:0.4.0-SNAPSHOT`
- `bluetape4k-text-bom:0.3.0-SNAPSHOT`

## 1.3.0 Stable Candidate Matrix

These are the intended stable BOM inputs to compare against
`bluetape4k-dependencies:1.2.0` before publishing `1.3.0`. A candidate must be
tagged, released, and Maven Central-visible before the dependencies catalog is
pinned to the stable version.

| Upstream BOM | `1.2.0` stable input | `1.3.0` stable candidate | Notes |
|---|---:|---:|---|
| `bluetape4k-bom` | `1.10.0` | `1.11.0` | Pending stable release. |
| `bluetape4k-aws-bom` | `0.3.1` | `0.4.0` | Pending stable release. |
| `bluetape4k-image-bom` | `0.2.0` | `0.3.0` | Pending stable release. |
| `bluetape4k-text-bom` | `0.2.0` | `0.2.1` | Patch train; do not substitute `0.3.0-SNAPSHOT`. |
| `bluetape4k-graph-bom` | `0.5.0` | `0.5.1` | Patch train; `0.6.0` is the next development line, not this stable input. |
| `bluetape4k-leader-bom` | `0.3.1` | `0.4.0` | Pending stable release. |
| `bluetape4k-exposed-bom` | `1.10.0` | `1.11.0` | Pending stable release. |
| `bluetape4k-javers-bom` | `0.2.0` | `0.2.1` | Patch train; `0.3.0` is the next development line, not this stable input. |

## Release Gate

- `bluetape4k-dependencies:1.2.0` is published and Maven Central-visible.
- The next train remains a snapshot validation line until each selected
  upstream repository publishes the matching stable artifact.
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
- `bluetape4k-aws-bom:0.3.1` returned HTTP 200 after release workflow
  `https://github.com/bluetape4k/bluetape4k-aws/actions/runs/26737796498`.
- `bluetape4k-leader-bom:0.3.1` returned HTTP 200 after release workflow
  `https://github.com/bluetape4k/bluetape4k-leader/actions/runs/26754212311`.
- Live release/tag checks on 2026-06-26 KST show the `1.3.0` stable candidates
  above are not yet tagged or published.

## Priority Queue

No assigned open issues are required for this release train.

## WIP Limits

| Lane | Limit | Current next |
|---|---:|---|
| Release | 1 | Triage the next dependencies governance train before selecting 1.3.0 inputs. |
