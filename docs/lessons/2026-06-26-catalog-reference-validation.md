# Catalog reference validation

## Context

The managed catalog sync verified generated bluetape4k module aliases, but it
did not verify that every `[versions]` key was referenced by either
`version.ref` entries, documented Gradle build logic, or downstream
`bt4kVersion("...")` calls.

That gap allowed a downstream-only compatibility alias such as
`jackson-annotations` to depend on manual review instead of structural
validation.

## Decision

Treat catalog version keys as first-class validation inputs:

- fail when a `[versions]` alias is not referenced;
- keep explicit, reasoned allowlist entries only for true version-only build
  logic aliases;
- scan managed downstream repositories for `bt4kVersion("alias")` and fail
  when those aliases are missing from the central catalog.

## Outcome

`scripts/sync-managed-catalog.py --check` now catches both orphan catalog
version keys and downstream `bt4kVersion` references that no longer resolve.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k --check --summary`
- `scripts/verify-managed-artifacts.py --summary --allow-snapshots`
- `python3 -m py_compile scripts/sync-managed-catalog.py scripts/sync-shared-versions.py scripts/sync-dependabot-ignores.py scripts/verify-managed-artifacts.py tests/*.py`
