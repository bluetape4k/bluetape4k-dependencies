# Exposed ArtifactId Sync

## Context

`bluetape4k-exposed` issue #77 shortened its published artifactIds before the
first official release. The dependencies BOM/catalog must consume the renamed
snapshot first because the other downstream repositories use this repository as
their centralized version source.

## Lesson

Do not regenerate managed modules from artifactId assumptions alone. The
upstream `settings.gradle.kts` can expose short project names with
`includeModules("exposed", withBaseDir = false)` and explicit project-to-path
mappings with `includeMappedModule(...)`.

## Verification

- `scripts/sync-managed-catalog.py --workspace-root ../../.. --write --check --summary`
- `python3 -m py_compile scripts/sync-managed-catalog.py scripts/sync-shared-versions.py tests/*.py`
- `python3 -m unittest tests/test_sync_managed_catalog.py tests/test_sync_shared_versions.py`
- `./gradlew build --no-daemon --no-configuration-cache`
- `./gradlew publishToMavenLocal --no-daemon --no-configuration-cache`
