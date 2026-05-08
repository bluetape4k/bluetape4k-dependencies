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
`bluetape4k-bom` (from `bluetape4k-projects`) is imported as `api(platform(...))` so **all**
`io.github.bluetape4k:*` modules (cache-*, lettuce, jdbc, r2dbc, etc.) are version-managed
for consumers automatically — no per-module entry needed here.
Other ecosystem repos (aws, image, text, graph, leader, exposed) are listed as explicit `constraints`.

```
bluetape4k-bom  ──platform import──▶  ALL bluetape4k-projects versions
libs.versions.toml  ──version refs──▶  explicit constraints for other repos
```

Consumers use `platform(...)` to import the BOM:

```kotlin
dependencies {
    implementation(platform("io.github.bluetape4k:bluetape4k-dependencies:VERSION"))
    implementation("io.github.bluetape4k:bluetape4k-core")          // no version
    implementation("io.github.bluetape4k.image:images")             // no version
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

2. **Verify constraints** in `build.gradle.kts` — all `api(libs.bluetape4k.*)` entries for that repo
   automatically pick up the new version via the catalog ref. No manual edit of `build.gradle.kts` is needed
   unless you are **adding** a brand-new artifact.

3. **Add a new artifact** (when a repo publishes a new module):
   - Add a `[libraries]` entry in `libs.versions.toml` pointing to the correct module coordinate and version ref.
   - Add a corresponding `api(libs.<alias>)` line inside `dependencies { constraints { } }` in `build.gradle.kts`.

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
- All per-repo versions live exclusively in `gradle/libs.versions.toml` — never hard-coded elsewhere.

---

## Important Notes

- **No source code lives here.** This is a pure `java-platform` BOM project.
- **`allowDependencies()`** is enabled to allow `api(platform(...))` declarations alongside `constraints {}`.
- `bluetape4k-bom` is imported via `api(platform(...))` — this propagates ALL `bluetape4k-projects` module versions to consumers. Do NOT put it back inside `constraints {}`.
- Individual constraints for aws, image, text, graph, leader, exposed remain explicit because those repos don't have sub-BOMs imported here.
- The CI workflow (`ci.yml`) runs `./gradlew build` on every push/PR against `develop` and `main`.

