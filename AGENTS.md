# AGENTS.md - bluetape4k-dependencies

This repository is the centralized BOM for the bluetape4k ecosystem. It is a
pure Gradle `java-platform` project: no production source code, constraints
only.

- Group: `io.github.bluetape4k`
- Artifact: `bluetape4k-dependencies`
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

## How It Works

`gradle/libs.versions.toml` owns version refs. `build.gradle.kts` declares
`dependencies { constraints { ... } }` and references catalog aliases. Consumers
import the BOM with `platform(...)` and omit individual bluetape4k versions.

## Updating Versions

1. Update the relevant version ref in `gradle/libs.versions.toml`.
2. Verify existing constraints pick up the version through the catalog alias.
3. When adding a new published artifact, add both a `[libraries]` alias and a
   matching `api(libs.<alias>)` constraint.
4. Run `./gradlew build`.

## Commands

```bash
./gradlew build
./gradlew publishBluetapeDependenciesPublicationToCentralPortal
./gradlew publishToMavenLocal
```

Publishing credentials come from `resolveCentralPublishingConfig()`. Use
`CENTRAL_USERNAME` and `CENTRAL_PASSWORD` env vars or Gradle properties.

## Rules

- Keep all per-repo versions in `gradle/libs.versions.toml`; do not hard-code
  module versions elsewhere.
- The BOM version is bumped when a coordinated upstream version set is promoted.
- `allowDependencies()` is enabled so constraints can reference external BOMs.
- CI runs `./gradlew build` for pushes/PRs against `develop` and `main`.
