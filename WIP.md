# WIP - bluetape4k-dependencies

Snapshot: 2026-05-18 KST
Scope: open GitHub issues assigned to `debop`, created on or after 2026-01-01.
Open count: 3 issues.

## Recently Completed

- First-release Spring Boot 4-only versionless alias policy (#8) is closed.
- Central dependency governance is active: `sync-shared-versions.py`,
  `sync-dependabot-ignores.py`, and `sync-managed-catalog.py` are now the
  workspace propagation surfaces.
- Organization-level Dependabot ignore generation and managed catalog sync are
  covered by unit tests and CI checks.

## Current Direction

Dependency governance script correctness before more version upgrades.

The catalog is the workspace source of truth. Fix sync-tool safety gaps before
promoting larger dependency upgrades so local checks and CI cannot silently skip
managed repositories.

## Priority Queue

| Priority | Issue | Difficulty | Notes |
|---|---|---:|---|
| P1 | [#39](https://github.com/bluetape4k/bluetape4k-dependencies/issues/39) `sync-dependabot-ignores` default workspace is one directory too high | S | Default run can silently no-op; align with `sync-shared-versions.py` and add no-target diagnostics. |
| P2 | [#34](https://github.com/bluetape4k/bluetape4k-dependencies/issues/34) Upgrade MyBatis Dynamic SQL to 2.x | M | Dependency upgrade lane; verify downstream consumers before promotion. |
| P2 | [#35](https://github.com/bluetape4k/bluetape4k-dependencies/issues/35) Upgrade Timefold Solver to 2.x | M | Dependency upgrade lane; likely requires workshop/example compatibility checks. |

## Dependency Map

```text
#39 sync-dependabot-ignores default workspace fix
  -> safe local governance checks
  -> #34 MyBatis Dynamic SQL 2.x
  -> #35 Timefold Solver 2.x

#8 Spring Boot 4-only versionless alias policy (closed)
  -> first official BOM/Version Catalog contract baseline
```

## WIP Limits

| Lane | Limit | Current next |
|---|---:|---|
| Governance tooling | 1 | `#39` |
| Dependency upgrade | 1 | `#34`, then `#35` |

## Cleanup Actions

| Candidate | Action |
|---|---|
| no-target-file script behavior | Fail or warn when governance scripts discover no managed repositories. |
| dependency major upgrades | Verify downstream compile/test impact before catalog promotion. |
