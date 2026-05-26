# Leader Security Catalog Lines

## Context

`bluetape4k-leader` issue #389 surfaced Dependabot alerts for transitive
Netty, Protobuf, Fabric8, and Vert.x artifacts through the shared catalog/BOM
path.

## Decision

Manage Netty 4.1/4.2, Protobuf, Fabric8, and Vert.x 4/5 versions in
`bluetape4k-dependencies` instead of pinning security override versions in
`bluetape4k-leader`.

## Outcome

Downstream repositories can consume the same version aliases and BOM imports for
security-aligned resolution.

## Verification

- Added catalog aliases for Netty, Protobuf, Fabric8, and Vert.x compatibility
  lines; added BOM/platform constraints only for the single-line constraints
  that are safe for central consumers.
- Updated the central Dependabot ignore source for those package groups.
- `scripts/sync-managed-catalog.py --check --summary`,
  `scripts/sync-shared-versions.py --workspace .. --repo bluetape4k-leader --check --summary`,
  `scripts/sync-dependabot-ignores.py --workspace .. --repo bluetape4k-leader --check --summary`,
  and `./gradlew build` passed.

## Future Notes

When Dependabot reports a shared transitive dependency from a downstream repo,
triage ownership first. If the version is ecosystem-wide, add or update the
central catalog line before touching downstream builds.
