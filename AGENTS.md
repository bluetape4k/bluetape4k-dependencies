# AGENTS.md - bluetape4k-dependencies

This repository is the centralized dependency-governance project for the
bluetape4k ecosystem. It publishes a Gradle `java-platform` BOM plus a Gradle
version catalog from the same managed version source. It contains no production
source code.

- Group: `io.github.bluetape4k`
- BOM artifact: `bluetape4k-dependencies`
- Gradle version catalog artifact: `bluetape4k-version-catalog`
- Published to Maven Central through Sonatype NMCP

## Managed Repositories

| Repository | Version key | Group ID |
|---|---|---|
| `bluetape4k-projects` | `bluetape4k-core` | `io.github.bluetape4k` |
| `bluetape4k-aws` | `bluetape4k-aws` | `io.github.bluetape4k.aws` |
| `bluetape4k-image` | `bluetape4k-image` | `io.github.bluetape4k.image` |
| `bluetape4k-text` | `bluetape4k-text` | `io.github.bluetape4k.text` |
| `bluetape4k-graph` | `bluetape4k-graph` | `io.github.bluetape4k.graph` |
| `bluetape4k-leader` | `bluetape4k-leader` | `io.github.bluetape4k.leader` |
| `bluetape4k-exposed` | `bluetape4k-exposed` | `io.github.bluetape4k.exposed` |
| `bluetape4k-javers` | `bluetape4k-javers` | `io.github.bluetape4k.javers` |

## How It Works

`gradle/libs.versions.toml` owns version refs, library aliases, and plugin
aliases. `build.gradle.kts` publishes that file as `bluetape4k-version-catalog`
and also declares `dependencies { constraints { ... } }` for the
`bluetape4k-dependencies` BOM.

Use the BOM for dependency resolution contracts. Use the published version
catalog for Gradle build aliases and plugin/tooling versions.

## Updating Versions

1. Update the relevant version ref in `gradle/libs.versions.toml`.
2. For managed repository module additions/removals, run
   `scripts/sync-managed-catalog.py --write --check`; do not edit
   generated catalog/constraint blocks by hand.
3. Verify existing constraints pick up the version through the catalog alias.
4. When adding a new published artifact outside generated blocks, add both a `[libraries]` alias and a
   matching `api(libs.<alias>)` constraint.
5. Run `./gradlew build`.

## Commands

```bash
scripts/sync-managed-catalog.py --check --summary
scripts/sync-managed-catalog.py --write --check --summary
python3 -m unittest tests/test_sync_managed_catalog.py
./gradlew build
./gradlew publishBluetapeDependenciesPublicationToCentralPortal
./gradlew publishBluetapeVersionCatalogPublicationToCentralPortal
./gradlew publishToMavenLocal
```

Publishing credentials come from `resolveCentralPublishingConfig()`. Use
`CENTRAL_USERNAME` and `CENTRAL_PASSWORD` env vars or Gradle properties.

## Rules

- Keep all per-repo versions and shared Gradle plugin/tooling versions in
  `gradle/libs.versions.toml`; do not hard-code module versions elsewhere.
- The BOM version is bumped when a coordinated upstream version set is promoted.
- `allowDependencies()` is enabled so constraints can reference external BOMs.
- The version catalog is a Gradle build contract, not a substitute for the BOM.
  Consumers should still import `bluetape4k-dependencies` as a platform when
  they need dependency resolution alignment.
- CI runs `./gradlew build` for pushes/PRs against `develop` and `main`.
