# Dependencies Consumer Version Line

## Context

`publish-snapshot.yml` publishes the next development line by passing
`-PsnapshotVersion=-SNAPSHOT` at Gradle runtime, while CI catalog sync reads only
the checked-in `gradle/libs.versions.toml` values.

## Decision

Keep `gradle.properties` as the publication line and keep the
`bluetape4k-dependencies` version catalog alias as the latest released
downstream consumer line.

## Outcome

The snapshot train can publish `1.1.4-SNAPSHOT` without forcing downstream
repositories to consume unreleased `io.github.bluetape4k:bluetape4k-dependencies:1.1.4`.

Existing immutable catalog refs still expose their original content. If
`catalog/2026-05-25-00` points at a bad catalog, do not move it; commit this
fix, create the next ref such as `catalog/2026-05-25-01`, and update downstream
default `bluetape4kDependenciesCatalogRef` values to that new ref.

## Verification

`python3 -m unittest tests/test_sync_shared_versions.py`
