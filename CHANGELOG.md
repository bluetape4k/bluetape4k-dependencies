# Changelog

All notable changes to `bluetape4k-dependencies` are documented in this file.

## Unreleased

### Changed

- Standardized the first official Spring Boot integration surface on Spring Boot
  4-only, versionless `spring-boot` artifact names before the BOM is publicly
  released.
- Replaced transitional `leader-spring-boot3` / `leader-spring-boot4` aliases
  with the single `leader-spring-boot` alias.
- Replaced transitional Exposed `bluetape4k-spring-boot3-*` and
  `bluetape4k-spring-boot4-*` aliases with versionless
  `bluetape4k-spring-boot-*` aliases.
- Added versionless Spring Boot module aliases for the core
  `bluetape4k-projects` Spring Boot integration modules.

### Notes

- Spring Boot 3 artifacts remain available from the older 1.7.x line, but they
  are intentionally not part of the first official `bluetape4k-dependencies`
  public contract.
