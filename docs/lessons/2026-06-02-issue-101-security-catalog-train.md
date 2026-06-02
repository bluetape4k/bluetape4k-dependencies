# Issue 101: Security Catalog Train

## Context

`bluetape4k-projects` Dependabot alerts surfaced shared Maven dependency
families that are governed by the `bluetape4k-dependencies` catalog.

## Decision

Update shared catalog versions in `bluetape4k-dependencies` first. Use the
latest stable Maven metadata version, not only the minimum patched version, for
alerted shared lines.

## Outcome

Jackson 2, Jackson 3, and AWS SDK v2 were advanced beyond the already-merged
Dependabot PR baseline. Existing Spring Boot, Tomcat, Netty, Bouncy Castle, and
ClassGraph lines were verified against current stable metadata.

## Verification

- Maven metadata lookup for affected shared dependency families.
- `scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k --check --summary`
- `scripts/sync-shared-versions.py --workspace /Users/debop/work/bluetape4k --check --summary` reported downstream drift that must be handled in the follow-up catalog/downstream sync step.

## Future Guidance

For security catalog trains, update `bluetape4k-dependencies` source-of-truth
first, merge that PR, then cut the catalog tag and update downstream consumers.
