# WIP - bluetape4k-dependencies

Snapshot: 2026-05-23 KST
Scope: open GitHub issues assigned to `debop`, created on or after 2026-01-01.
Open count: 0 issues.

## Recently Completed

- The 1.1.0 release scope has zero open issues on GitHub.
- The ecosystem release train is promoted into the central BOM/catalog:
  - `bluetape4k-bom:1.9.0`
  - `bluetape4k-aws-bom:0.2.0`
  - `bluetape4k-exposed-bom:1.9.0`
  - `bluetape4k-graph-bom:0.4.0`
  - `bluetape4k-image-bom:0.1.1`
  - `bluetape4k-javers-bom:0.1.1`
  - `bluetape4k-leader-bom:0.2.0`
  - `bluetape4k-text-bom:0.1.1`
- `bluetape4k-leader-dynamodb` is included in the generated catalog and BOM.

## Current Direction

Prepare and publish `1.1.1`. The patch removes non-published mock web
application modules from the managed catalog and adds a Central artifact audit
gate.

Do not start the next governance or major dependency-upgrade lane until the
1.1.1 BOM and version catalog are visible in Maven Central. Treat 1.1.0 as
superseded for downstream sync because it exposed non-published mock web app
modules.

## Priority Queue

No assigned open issues remain for this release train.

## WIP Limits

| Lane | Limit | Current next |
|---|---:|---|
| Release | 1 | Finish 1.1.1 release before starting more dependency governance work. |
