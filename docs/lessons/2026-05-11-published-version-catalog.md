# Gradle version catalog source

## Context

The ecosystem BOM aligns runtime dependency resolution, but it does not govern
Gradle build aliases, plugin versions, or compatibility-line names such as
`kafka3`/`kafka4`, `jackson2`/`jackson3`, and `spring-boot3`/`spring-boot4`.

## Decision

Keep `gradle/libs.versions.toml` in this repository as the shared Gradle
catalog source consumed from checked-out git refs or catalog tags. Do not
publish it as a Maven Central artifact.

## Outcome

The BOM remains the dependency-resolution contract. The version catalog becomes
the git-ref build contract for shared aliases, plugin versions, and managed
module coordinates used by ecosystem repositories.

## Verification

- `./gradlew build publishToMavenLocal --no-daemon`
- Downstream smoke checks that read this repository's
  `gradle/libs.versions.toml` from a checked-out ref or catalog tag.

## Future Guard

Do not replace the BOM with the version catalog. Consumers should read the
catalog source for Gradle build aliases and still import
`bluetape4k-dependencies` as a platform for dependency resolution alignment.
