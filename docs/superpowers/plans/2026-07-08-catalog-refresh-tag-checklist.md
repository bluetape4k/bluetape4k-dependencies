# Catalog Refresh Tag Checklist

## Target Inventory

| Field | Value |
|---|---|
| Repository | `bluetape4k-dependencies` |
| Branch / PR | `build/refresh-catalog-managed-versions` / PR #146 |
| Base branch | `develop` |
| Catalog ref | `catalog/2026-07-08-00` |
| Target SHA authority | Merge commit of PR #146 on `develop` |
| Release class | Gradle version catalog source ref, not Maven BOM release |
| Publish artifact | None in this step |
| Catalog version semantics | Date-formatted git ref; unrelated to `bluetape4k-dependencies` artifact version |

## Scope

- Refresh centrally governed stable external dependency and plugin versions.
- Preserve compatibility-line aliases within their existing major lines.
- Preserve current snapshot BOM refs.
- Exclude `bluetape4k-experimental` from downstream propagation.

## Downstream Propagation PRs

| Repository | PR |
|---|---|
| `bluetape4k-projects` | https://github.com/bluetape4k/bluetape4k-projects/pull/992 |
| `bluetape4k-aws` | https://github.com/bluetape4k/bluetape4k-aws/pull/367 |
| `bluetape4k-exposed` | https://github.com/bluetape4k/bluetape4k-exposed/pull/363 |
| `bluetape4k-graph` | https://github.com/bluetape4k/bluetape4k-graph/pull/383 |
| `bluetape4k-image` | https://github.com/bluetape4k/bluetape4k-image/pull/268 |
| `bluetape4k-javers` | https://github.com/bluetape4k/bluetape4k-javers/pull/239 |
| `bluetape4k-leader` | https://github.com/bluetape4k/bluetape4k-leader/pull/594 |
| `bluetape4k-text` | https://github.com/bluetape4k/bluetape4k-text/pull/162 |
| `bluetape4k-workshop` | https://github.com/bluetape4k/bluetape4k-workshop/pull/509 |
| `clinic-appointment` | https://github.com/bluetape4k/clinic-appointment/pull/162 |
| `exposed-r2dbc-workshop` | https://github.com/bluetape4k/exposed-r2dbc-workshop/pull/130 |
| `exposed-workshop` | https://github.com/bluetape4k/exposed-workshop/pull/163 |

## Pre-Tag Gate

| Gate | Status | Evidence |
|---|---|---|
| Existing catalog tag absence | PASS | `git tag -l 'catalog/2026-07-08-*'` returned no existing tag. |
| Central PR body | PASS | Final PR body section is `## DoD Status`. |
| Central CI | PASS | PR #146 checks were green before this checklist commit. |
| Downstream CI | PENDING | Merge downstream PRs only after each PR is green and review threads are clear. |
| Central merge order | PENDING | Merge PR #146 only after downstream PRs are merged. |
| Tag push | PENDING | Push `catalog/2026-07-08-00` only after PR #146 merge commit is on `origin/develop`. |

## Validation Commands

```bash
python3 -m py_compile scripts/sync-managed-catalog.py scripts/sync-shared-versions.py scripts/sync-dependabot-ignores.py scripts/verify-managed-artifacts.py tests/*.py
python3 -m unittest discover -s tests -p 'test_*.py'
scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k --check --summary
scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --check --summary
scripts/verify-managed-artifacts.py --summary --allow-snapshots
./gradlew build --no-configuration-cache --console=plain
./gradlew publishToMavenLocal --no-configuration-cache --console=plain
```
