# Dependencies 1.0.1 Release Prep

## Context

The upstream bluetape4k ecosystem release train has new published artifacts for
projects, AWS, Exposed, image, Javers, text, and graph. The central BOM/catalog
still referenced several snapshots and older release lines.

## Decision

Prepare `bluetape4k-dependencies` 1.0.1 as the coordinated BOM/catalog release
for the current ecosystem train. Keep `bluetape4k-leader` on 0.1.0 because the
leader repository release is intentionally deferred.

## Outcome

Release metadata, version catalog, CHANGELOG, WIP, and release-prep lesson were
updated for the 1.0.1 release gate.

## Verification

Verified the Gradle release version, managed-catalog generation, shared-version
alignment, publication POM generation, stale/snapshot POM absence, build, and
local Maven publication before opening the release PR. The managed-catalog
generator excludes unreleased leader modules (`consul`, `etcd`, `k8s`) until
the deferred leader release publishes them.

## Future Notes

Do not promote the next governance or major dependency-upgrade lane until the
1.0.1 BOM and version catalog are visible in Maven Central.
