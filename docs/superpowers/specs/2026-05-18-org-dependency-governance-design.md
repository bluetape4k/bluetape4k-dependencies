# Org Dependency Governance Design

## Context

The bluetape4k organization has many independent Gradle repositories. Shared
libraries such as Kotlin, Spring Boot, Jackson, Kafka, Spring Kafka, and
Testcontainers must stay on one approved version matrix. Recent Dependabot PRs
showed that per-repository updates can break compatibility-line aliases, for
example moving `spring-kafka4` from the Spring Kafka 4 line to the 3 line.

## Goals

- Keep `bluetape4k-dependencies/gradle/libs.versions.toml` as the only approved
  shared version source.
- Ensure all non-archived bluetape4k Gradle repositories with local catalogs
  are checked against that source.
- Fail CI when compatibility-line aliases drift across major lines.
- Reduce duplicated repository lists between scripts and CI.
- Keep the design compatible with the existing BOM and git-ref version catalog
  source.

## Non-Goals

- Convert every downstream repository to a remote `bt4k` catalog in one PR.
- Remove all downstream `gradle/libs.versions.toml` files immediately.
- Change published dependency coordinates.

## Design

`bluetape4k-dependencies` remains the authority and exposes two contracts:

| Contract | Purpose |
|---|---|
| `bluetape4k-dependencies` BOM | Maven dependency resolution alignment |
| `gradle/libs.versions.toml` at a checked-out ref | Gradle alias and plugin authoring |

Downstream repositories will continue to carry local catalogs during migration,
but CI in `bluetape4k-dependencies` will treat them as synchronized materialized
copies for shared aliases.

The first implementation strengthens `scripts/sync-shared-versions.py`:

- expand default repositories to every active bluetape4k Gradle repository that
  can carry shared aliases;
- expose the default repository list to CI;
- validate compatibility-line aliases independently of exact source sync;
- keep source-of-truth version and project version consistency checks.

Compatibility-line validation is intentionally major-line based:

| Alias | Required line |
|---|---|
| `jackson2` | `2.x` |
| `jackson3` | `3.x` |
| `spring-boot3` | `3.x` |
| `spring-boot4` | `4.x` |
| `kafka3` | `3.x` |
| `kafka4` | `4.x` |
| `spring-kafka` | `3.x` |
| `spring-kafka4` | `4.x` |
| `ignite` | `2.x` |
| `ignite3` | `3.x` |

## Rollout

1. Add the stronger central governance gate in `bluetape4k-dependencies`.
2. Merge downstream drift fixes first when central CI detects existing drift.
3. Move downstream repositories toward reading
   `bluetape4k-dependencies/gradle/libs.versions.toml` from a checked-out
   catalog ref.
4. Add a shared convention plugin or repo convention that imports
   `io.github.bluetape4k:bluetape4k-dependencies` as a platform on standard
   configurations.

## Risks

- Central PRs can be blocked by downstream drift on `develop`; this is desired
  because the central source should merge last.
- Repositories with intentionally different major lines must use distinct alias
  names or module-group guard logic.
- Remote catalog migration needs staged downstream PRs because local `libs`
  catalog removal is disruptive.

## Verification

- Unit tests for default repository list and compatibility-line validation.
- `scripts/sync-shared-versions.py --check --summary` against cloned repos.
- Gradle build of `bluetape4k-dependencies`.
