# Org Dependency Governance

## Context

Independent Dependabot PRs can update the same shared dependency alias in one
repository without updating the rest of the bluetape4k organization. This can
also break compatibility-line aliases such as `spring-kafka4`.

## Decision

`bluetape4k-dependencies` must own the full shared version matrix and CI must
check the configured organization repositories using the same repository list as
the sync script.

## Outcome

The shared-version sync script now covers the active Gradle repositories and
validates compatibility-line alias major versions.

## Verification

- Added unit coverage for repository list printing and compatibility-line
  validation.
- CI cloning will use `scripts/sync-shared-versions.py --print-default-repositories`.

## Future Guard

Do not maintain separate hard-coded repo lists in workflow YAML. Generate the
list from the governance script so CI and local checks cover the same scope.
