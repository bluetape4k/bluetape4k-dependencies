# WIP - bluetape4k-dependencies

Snapshot: 2026-05-09 KST
Scope: open GitHub issues assigned to `debop`, created on or after 2026-01-01.
Open count: 1 issue.

## Current Direction

This repo has not had an official public release yet, so it is still possible
to change the first BOM and Version Catalog contract without creating a public
migration burden.

The first official surface should expose Spring Boot 4 integrations through
versionless `spring-boot` names. Do not publish `spring-boot3` aliases, and do
not make `spring-boot4` suffixes the standard public names.

## Priority Queue

| Priority | Issue | Difficulty | Notes |
|---|---|---:|---|
| P0 | [#8](https://github.com/bluetape4k/bluetape4k-dependencies/issues/8) Spring Boot 4-only versionless aliases | M | First official BOM/Version Catalog contract. Aligns with `projects #280/#263` and `exposed #3`. |

## Dependency Map

```text
projects #280 Boot 4-only policy
  -> dependencies #8 first official Spring Boot alias policy
  -> projects #263 spring-boot3 removal + spring-boot4 -> spring-boot rename
      -> exposed #3 spring-boot3 removal + spring-boot4 -> spring-boot rename

projects #263 and exposed #3 publishable artifact names
  -> dependencies #8 constraints and catalog aliases
```

## WIP Limits

| Lane | Limit | Current next |
|---|---:|---|
| Public BOM contract | 1 | `#8` |

## Cleanup Actions

| Candidate | Action |
|---|---|
| stale `leader-spring-boot3/4` aliases | Remove before official release; expose `leader-spring-boot` only. |
| stale `bluetape4k-spring-boot3-*` aliases | Remove before official release. |
| transitional `bluetape4k-spring-boot4-*` aliases | Replace with versionless `bluetape4k-spring-boot-*` aliases after upstream rename lands. |
