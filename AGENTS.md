# AGENTS.md - bluetape4k-dependencies

This repository inherits the workspace guidance from `../AGENTS.md`.
Read and follow the workspace root guide first. This file only adds
repo-specific layout, commands, domain rules, and local exceptions.


This repository is the centralized dependency-governance project for the
bluetape4k ecosystem. It publishes a Gradle `java-platform` BOM. Its
`gradle/libs.versions.toml` is also the internal build catalog source consumed
by other `bluetape4k-*` repositories from a checked-out git ref. It contains no
production source code.

- Group: `io.github.bluetape4k`
- BOM artifact: `bluetape4k-dependencies`
- Published to Maven Central through Sonatype NMCP

## Managed Repositories

| Repository | Version key | Group ID |
|---|---|---|
| `bluetape4k-projects` | `bluetape4k-core` | `io.github.bluetape4k` |
| `bluetape4k-aws` | `bluetape4k-aws` | `io.github.bluetape4k.aws` |
| `bluetape4k-experimental` | shared catalog only | mixed bluetape4k modules |
| `bluetape4k-exposed` | `bluetape4k-exposed` | `io.github.bluetape4k.exposed` |
| `bluetape4k-graph` | `bluetape4k-graph` | `io.github.bluetape4k.graph` |
| `bluetape4k-image` | `bluetape4k-image` | `io.github.bluetape4k.image` |
| `bluetape4k-javers` | `bluetape4k-javers` | `io.github.bluetape4k.javers` |
| `bluetape4k-leader` | `bluetape4k-leader` | `io.github.bluetape4k.leader` |
| `bluetape4k-text` | `bluetape4k-text` | `io.github.bluetape4k.text` |
| `bluetape4k-workshop` | shared catalog only | mixed examples |
| `clinic-appointment` | shared catalog only | example application |
| `exposed-r2dbc-workshop` | shared catalog only | Exposed R2DBC examples |
| `exposed-workshop` | shared catalog only | Exposed examples |
| `timefold-workshop` | shared catalog only | Timefold examples |

## How It Works

`gradle/libs.versions.toml` owns version refs, library aliases, and plugin
aliases. `build.gradle.kts` imports bluetape4k sub-BOMs with
`api(platform(...))`; those sub-BOMs provide the Maven dependency-management
contract for bluetape4k artifacts. Other `bluetape4k-*` repositories read this
catalog from a checked-out `bluetape4k-dependencies` ref; it is not a Maven
Central publication.

Use the BOM for dependency resolution contracts. Use the checked-out catalog
source for Gradle build aliases and plugin/tooling versions.

## Versioning Policy

- `baseVersion` is the semantic version of the user-facing
  `bluetape4k-dependencies` BOM.
- Shared catalog source refs use date-stamped train tags such as
  `catalog/2026-05-23-00`. Do not publish the internal catalog as a Maven
  Central artifact.

## Updating Versions

1. Update the relevant version ref in `gradle/libs.versions.toml`.
2. For shared dependency/plugin version changes, run
   `scripts/sync-shared-versions.py --workspace .. --write --check --summary`
   so downstream `bluetape4k-*` catalogs stay aligned with this source.
3. For centrally managed dependency names, run
   `scripts/sync-dependabot-ignores.py --workspace .. --write --check --summary`
   so downstream Dependabot does not open repo-local PRs for source-of-truth
   versions.
4. For managed repository module additions/removals, run
   `scripts/sync-managed-catalog.py --write --check`; do not edit
   generated catalog blocks by hand.
5. Verify the matching sub-BOM import exists in `build.gradle.kts`.
6. When adding a new published artifact outside generated blocks, add both a `[libraries]` alias and a
   matching `api(libs.<alias>)` constraint only if no imported BOM governs it.
7. Run `./gradlew build`.

## Commands

```bash
scripts/sync-managed-catalog.py --check --summary
scripts/sync-managed-catalog.py --write --check --summary
scripts/sync-shared-versions.py --workspace .. --check --summary
scripts/sync-shared-versions.py --workspace .. --write --check --summary
scripts/sync-dependabot-ignores.py --workspace .. --check --summary
scripts/sync-dependabot-ignores.py --workspace .. --write --check --summary
scripts/triage-dependabot-alerts.py --repo bluetape4k-projects
python3 -m unittest tests/test_sync_managed_catalog.py
python3 -m unittest tests/test_sync_shared_versions.py
python3 -m unittest tests/test_sync_dependabot_ignores.py
python3 -m unittest tests/test_triage_dependabot_alerts.py
./gradlew build
./gradlew publishBluetapeDependenciesPublicationToCentralPortal
./gradlew publishToMavenLocal
```

Publishing credentials come from `resolveCentralPublishingConfig()`. Use
`CENTRAL_USERNAME` and `CENTRAL_PASSWORD` env vars or Gradle properties.

## Rules

- Keep all per-repo versions and shared Gradle plugin/tooling versions in
  `gradle/libs.versions.toml`; do not hard-code module versions elsewhere.
- Downstream Dependabot must ignore centrally governed dependency names; update
  `CENTRAL_DEPENDENCY_IGNORES` and resync downstream repos when a new shared
  dependency line is added.
- Triage Dependabot security alerts by ownership, not by the repository where
  the alert is displayed. Use `scripts/triage-dependabot-alerts.py` to route
  alerts to `central-catalog`, `central-bom-transitive`, `repo-tooling`, or
  `repo-local`.
- The BOM version is bumped when a coordinated upstream version set is promoted.
- The build/contributor catalog is cut by tagging this repo, for example
  `catalog/2026-05-23-00`; it does not have to match the BOM version.
- `allowDependencies()` is enabled so constraints can reference external BOMs.
- The version catalog source is a Gradle build contract, not a substitute for the BOM.
  Consumers should still import `bluetape4k-dependencies` as a platform when
  they need dependency resolution alignment.
- CI runs `./gradlew build` for pushes/PRs against `develop` and `main`.

## Repo-Specific Guards

- Treat module additions, removals, artifact renames, and compatibility-line
  changes as cross-repo catalog work: update managed catalog generation,
  downstream shared-version sync, Dependabot ignore sync, README/runbook
  references, and tests in the same pass.
- Release and snapshot dispatch stays audit-first: read declared workflow inputs
  from YAML and pass only supported inputs.
