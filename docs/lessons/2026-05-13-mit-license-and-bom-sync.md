# MIT License And BOM Sync

## Context

The workspace-wide MIT license refresh touched this repository's README files.
CI also checked generated BOM/catalog blocks against sibling repositories.

## Decision

Keep the license text update in the same PR and run
`scripts/sync-managed-catalog.py --write --summary` to repair generated graph
module aliases and constraints required by CI.

## Outcome

The README files now advertise MIT License, and the generated BOM/catalog blocks
include `graph-ktor` plus the versionless `graph-spring-boot` alias.

## Verification

- `scripts/sync-managed-catalog.py --write --summary`
- `scripts/sync-managed-catalog.py --check --summary`
- `scripts/sync-shared-versions.py --workspace .. --check --summary`
