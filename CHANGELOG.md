# Changelog

All notable changes to `bluetape4k-dependencies` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `bluetape4k-leader-dynamodb` generated catalog alias and BOM constraint.

## [1.0.1] - 2026-05-22

### Added

- Dependabot configuration for repository maintenance ([PR #1](https://github.com/bluetape4k/bluetape4k-dependencies/pull/1)).
- Release workflow for Maven Central Portal publishing and GitHub Release creation.
- SNAPSHOT publishing workflow on `develop` pushes ([PR #3](https://github.com/bluetape4k/bluetape4k-dependencies/pull/3)).
- `bluetape4k-exposed` modules in the central BOM ([PR #2](https://github.com/bluetape4k/bluetape4k-dependencies/pull/2)).
- AWS, image, text, exposed, and javers BOM platform imports ([PR #6](https://github.com/bluetape4k/bluetape4k-dependencies/pull/6)).
- `leader-zookeeper` BOM entry ([PR #7](https://github.com/bluetape4k/bluetape4k-dependencies/pull/7)).
- `bluetape4k-graph-ktor` generated catalog alias and BOM constraint.

### Changed

- Opened the next snapshot train as `1.0.1-SNAPSHOT` and aligned the managed
  `bluetape4k-exposed` BOM to `1.8.1-SNAPSHOT`.
- Standardized the first official Spring Boot integration surface on Spring Boot 4-only, versionless `spring-boot` artifact names before the BOM is publicly released ([PR #9](https://github.com/bluetape4k/bluetape4k-dependencies/pull/9)).
- Replaced transitional `leader-spring-boot3` / `leader-spring-boot4` aliases with the single `leader-spring-boot` alias ([PR #9](https://github.com/bluetape4k/bluetape4k-dependencies/pull/9)).
- Replaced transitional Exposed `bluetape4k-spring-boot3-*` and `bluetape4k-spring-boot4-*` aliases with versionless `bluetape4k-spring-boot-*` aliases ([PR #9](https://github.com/bluetape4k/bluetape4k-dependencies/pull/9)).
- Added versionless Spring Boot module aliases for the core `bluetape4k-projects` Spring Boot integration modules ([PR #9](https://github.com/bluetape4k/bluetape4k-dependencies/pull/9)).
- Replaced the generated `bluetape4k-graph-spring-boot4-starter` alias with the versionless `bluetape4k-graph-spring-boot` alias.
- README license references now point to MIT License.
- Promoted the ecosystem BOM set to the current published release train:
  `bluetape4k-bom:1.9.0`, `bluetape4k-aws-bom:0.2.0`,
  `bluetape4k-exposed-bom:1.9.0`, `bluetape4k-graph-bom:0.4.0`,
  `bluetape4k-image-bom:0.1.1`, `bluetape4k-javers-bom:0.1.1`, and
  `bluetape4k-text-bom:0.1.1`.

### Fixed

- Converted `bluetape4k-bom`, graph BOM, and leader BOM references to platform imports so dependency constraints compose correctly ([PR #4](https://github.com/bluetape4k/bluetape4k-dependencies/pull/4), [PR #5](https://github.com/bluetape4k/bluetape4k-dependencies/pull/5)).

### Notes

- Spring Boot 3 artifacts remain available from the older 1.7.x line, but they are intentionally not part of the first official `bluetape4k-dependencies` public contract.
