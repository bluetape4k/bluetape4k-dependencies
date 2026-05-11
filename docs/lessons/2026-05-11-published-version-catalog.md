# Published Gradle version catalog

## Context

The ecosystem BOM aligns runtime dependency resolution, but it does not govern
Gradle build aliases, plugin versions, or compatibility-line names such as
`kafka3`/`kafka4`, `jackson2`/`jackson3`, and `spring-boot3`/`spring-boot4`.

## Decision

Publish `gradle/libs.versions.toml` as a separate
`bluetape4k-version-catalog` artifact from the same repository that publishes
the `bluetape4k-dependencies` BOM.

## Outcome

The BOM remains the dependency-resolution contract. The version catalog becomes
the Gradle build contract for shared aliases, plugin versions, and managed
module coordinates.

## Verification

- `./gradlew build publishToMavenLocal --no-daemon`
- `./gradlew publishAllPublicationsToCentralPortal --dry-run --no-daemon`
- Local smoke project importing
  `io.github.bluetape4k:bluetape4k-version-catalog:1.0.0-SNAPSHOT`

## Future Guard

Do not replace the BOM with the version catalog. Consumers should import the
catalog for Gradle build aliases and still import `bluetape4k-dependencies` as
a platform for dependency resolution alignment.
