# Artifact Availability Audit Before BOM Release

## Context

`bluetape4k-dependencies` 1.1.0 was published with generated aliases for
`bluetape4k-mock-web-server` and `bluetape4k-mock-webflux-server`.
Those modules are application/image test fixtures in `bluetape4k-projects`, and
their Gradle builds explicitly disable Maven publication.

## Decision

Exclude non-published mock web application modules from the generated managed
catalog and BOM. Public consumption should go through published testing APIs
such as `bluetape4k-testcontainers` instead of direct Maven coordinates for
those app modules.

Add a release-prep audit that checks managed `io.github.bluetape4k*` GAVs
against Maven Central before publishing a final BOM.

## Outcome

The 1.1.1 patch release supersedes 1.1.0 for downstream sync by removing the two
missing aliases and adding `scripts/verify-managed-artifacts.py`.

## Verification

- `scripts/sync-managed-catalog.py --write --check --summary`
- Pending full validation before PR creation.

## Future Guidance

Before publishing `bluetape4k-dependencies`, run both the generated catalog sync
check and the Central artifact availability audit. Treat modules with disabled
publishing as implementation fixtures, not catalog-managed libraries.
