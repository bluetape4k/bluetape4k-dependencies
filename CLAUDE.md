# CLAUDE.md — bluetape4k-dependencies

## Project Overview

`bluetape4k-dependencies` is the **centralized BOM (Bill of Materials)** for the entire bluetape4k ecosystem.
It plays the same role as `spring-boot-dependencies`: consumers import a single platform dependency and get
consistent, pre-coordinated versions for every bluetape4k module — no per-dependency version declarations needed.

- **group**: `io.github.bluetape4k`
- **artifact**: `bluetape4k-dependencies`
- **plugin**: `java-platform` (Gradle built-in; no code, constraints only)
- **published to**: Maven Central (via Sonatype NMCP)

### Managed Repositories

| Repository | Version key in `libs.versions.toml` | Group ID |
|---|---|---|
| [bluetape4k-projects](https://github.com/bluetape4k/bluetape4k-projects) | `bluetape4k-core` | `io.github.bluetape4k` |
| [bluetape4k-aws](https://github.com/bluetape4k/bluetape4k-aws) | `bluetape4k-aws` | `io.github.bluetape4k.aws` |
| [bluetape4k-image](https://github.com/bluetape4k/bluetape4k-image) | `bluetape4k-image` | `io.github.bluetape4k.image` |
| [bluetape4k-text](https://github.com/bluetape4k/bluetape4k-text) | `bluetape4k-text` | `io.github.bluetape4k.text` |
| [bluetape4k-graph](https://github.com/bluetape4k/bluetape4k-graph) | `bluetape4k-graph` | `io.github.bluetape4k.graph` |
| [bluetape4k-leader](https://github.com/bluetape4k/bluetape4k-leader) | `bluetape4k-leader` | `io.github.bluetape4k.leader` |

---

## How It Works

`build.gradle.kts` declares a `java-platform` project.
All bluetape4k ecosystem sub-BOMs are imported as `api(platform(...))` so
all modules in each repo are version-managed for consumers automatically.
Generated module aliases stay in `libs.versions.toml` for Gradle build ergonomics;
they are not repeated as individual BOM constraints.

```
bluetape4k-bom          ──platform import──▶  ALL bluetape4k-projects versions
bluetape4k-graph-bom    ──platform import──▶  ALL graph module versions
bluetape4k-exposed-bom  ──platform import──▶  ALL exposed module versions
libs.versions.toml      ──version refs──────▶  Gradle aliases for downstream builds
```

Consumers use `platform(...)` to import the BOM:

```kotlin
dependencies {
    implementation(platform("io.github.bluetape4k:bluetape4k-dependencies:VERSION"))
    implementation("io.github.bluetape4k:bluetape4k-core")          // no version
    implementation("io.github.bluetape4k.image:bluetape4k-images")             // no version
}
```

---

## How to Update a Module Version

1. **Open `gradle/libs.versions.toml`** and change the relevant version ref:

   ```toml
   [versions]
   bluetape4k-core   = "1.8.0"          # was 1.7.0-SNAPSHOT
   bluetape4k-graph  = "0.4.0-SNAPSHOT"
   ```

2. **Verify the sub-BOM import** in `build.gradle.kts` — the imported BOM owns the
   artifact versions. No per-artifact `api(libs.bluetape4k.*)` constraint is needed.

3. **Add a new artifact** (when a repo publishes a new module):
   - Add a `[libraries]` entry in `libs.versions.toml` pointing to the correct module coordinate and version ref.
   - Do not add a corresponding `api(libs.<alias>)` constraint when an imported sub-BOM governs the artifact.

4. **Run `./gradlew build`** to validate the platform resolves correctly.

---

## Build & Publish Commands

```bash
# Validate the BOM compiles and resolves
./gradlew build

# Publish a SNAPSHOT to Maven Central Snapshots
./gradlew publishBluetapeDependenciesPublicationToCentralPortal

# Publish a RELEASE (strip -SNAPSHOT suffix first in gradle.properties / libs.versions.toml)
./gradlew publishBluetapeDependenciesPublicationToCentralPortal

# Publish to local Maven repository (for local integration testing)
./gradlew publishToMavenLocal
```

> **Note**: Publishing credentials are resolved via `resolveCentralPublishingConfig()` (defined in `buildSrc`).
> Set `CENTRAL_USERNAME` and `CENTRAL_PASSWORD` environment variables or Gradle properties before publishing.

---

## Versioning Policy

- Each upstream repository maintains its own independent version (`bluetape4k-core`, `bluetape4k-graph`, …).
- The BOM's own version (`baseVersion` in `gradle.properties`) is bumped whenever a new set of upstream
  versions is promoted and the BOM is re-published.
- The Gradle version catalog source (`gradle/libs.versions.toml`) is cut by tagging this repo with
  a date-stamped train ref such as `catalog/2026-05-23-00`. It is an internal build input, not a
  Maven Central publication.
- All per-repo versions live exclusively in `gradle/libs.versions.toml` — never hard-coded elsewhere.

---

## Important Notes

- **No source code lives here.** This is a pure `java-platform` BOM project.
- **`allowDependencies()`** is enabled to allow `api(platform(...))` declarations alongside `constraints {}`.
- `bluetape4k-bom` is imported via `api(platform(...))` — this propagates ALL `bluetape4k-projects` module versions to consumers. Do NOT put it back inside `constraints {}`.
- Individual bluetape4k artifact constraints are intentionally omitted when an imported sub-BOM governs the repo.
- The CI workflow (`ci.yml`) runs `./gradlew build` on every push/PR against `develop` and `main`.
