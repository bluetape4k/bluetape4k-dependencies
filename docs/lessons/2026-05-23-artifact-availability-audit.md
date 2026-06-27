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

The release was published and then consumed by downstream synchronization PRs:

- `bluetape4k-dependencies` PR #63 published tag `1.1.1`.
- `bluetape4k-experimental` PR #57 consumed `1.1.1`.
- `bluetape4k-graph` PR #208 consumed `1.1.1`.
- `clinic-appointment` PR #130 consumed `1.1.1`.
- `exposed-r2dbc-workshop` PR #85 consumed `1.1.1`.
- `exposed-workshop` PR #96 consumed `1.1.1`.

## Verification

- `scripts/sync-managed-catalog.py --write --check --summary`
- `scripts/verify-managed-artifacts.py --include-self --summary` checked 153
  managed bluetape4k artifacts.
- GitHub Actions release run 26323169412 completed successfully.
- Maven Central `repo1.maven.org` returned 200 for
  `bluetape4k-dependencies/1.1.1`.
- The shared version catalog source was available from the corresponding git
  ref for downstream sync.
- Downstream sync PRs #57, #208, #130, #85, and #96 were merged after CI passed.
- `scripts/sync-shared-versions.py --workspace .. --check --summary`

## Future Guidance

Before publishing `bluetape4k-dependencies`, run both the generated catalog sync
check and the Central artifact availability audit. Treat modules with disabled
publishing as implementation fixtures, not catalog-managed libraries. Downstream
repositories should wait for Maven Central `repo1` visibility before rerunning
their CI, because Central Portal success does not guarantee immediate repository
availability.
