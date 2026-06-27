# dependencies 1.3.1 release checklist

## Scope

- Repository: `bluetape4k-dependencies`
- Target version: `1.3.1`
- Release class: `dependencies-patch-train`
- Target issue: `#133`
- Milestone: `1.3.1`
- Maven publication: `io.github.bluetape4k:bluetape4k-dependencies`
- Catalog contract: `gradle/libs.versions.toml` consumed from a checked-out git
  ref or catalog tag, not a Maven Central artifact
- Expected POM license: MIT License

## Current State

| Gate | Status | Evidence |
|---|---|---|
| Milestone exists | PASS | GitHub milestone `1.3.1` exists. |
| Release issue exists | PASS | `bluetape4k-dependencies#133` tracks the patch. |
| Open PRs against `develop` before work | PASS | `gh pr list --state open --base develop` returned `[]`. |
| Existing tag absent | PASS | `git ls-remote --tags origin refs/tags/1.3.1` returned no rows. |
| Existing GitHub Release absent | PASS | `gh release view 1.3.1` returned no release. |
| Existing Maven Central artifact absent | PASS | `repo1.maven.org` returned HTTP 404 for `bluetape4k-dependencies-1.3.1.pom`. |
| Workflow schema read | PASS | `.github/workflows/release.yml` declares `version` and optional `diagnoseSigning`. |
| Snapshot version absent | PASS | `gradle.properties` has `snapshotVersion=`. |
| POM license | PASS | Generated `pom-default.xml` contains `MIT License`. |
| Missing dependency versions | PASS | Generated POM scan found no empty `<version>`. |
| Snapshot leakage | PASS | Generated publication metadata scan found no `SNAPSHOT`. |
| Managed artifact availability | PASS | `scripts/verify-managed-artifacts.py --summary` checked 162 artifacts and skipped self. |
| Managed catalog sync | PASS | `scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k --check --summary` verified 162 aliases and 8 sub-BOMs. |
| Shared version sync | PASS | `scripts/sync-shared-versions.py --workspace /Users/debop/work/bluetape4k --check --summary` reported aligned versions. |
| Local build and publication | PASS | `./gradlew build publishToMavenLocal --no-daemon --no-configuration-cache --no-build-cache` succeeded. |
| Consumer repo scan | PASS | `bluetape4k-workshop`, `exposed-workshop`, `exposed-r2dbc-workshop`, `clinic-appointment`, and `timefold-workshop` currently reference `bluetape4k-dependencies 1.2.0`. |

## Pre-Dispatch Hold

Run these again after the PR is merged and immediately before tag push or
workflow dispatch:

- milestone `1.3.1` open issues are 0;
- open PRs against `develop` are 0;
- tag `1.3.1` is absent before creating it;
- GitHub Release `1.3.1` is absent before release workflow completion;
- `gradle.properties` has `baseVersion=1.3.1` and `snapshotVersion=`;
- generated POM license is MIT;
- generated POM has no missing dependency versions;
- generated publication metadata has no `SNAPSHOT`;
- release workflow inputs are still `version` and optional `diagnoseSigning`;
- Maven Central `1.3.1` artifact is absent before dispatch and HTTP 200 after
  publish completion.

## Post-Release Consumer Sync

After `bluetape4k-dependencies:1.3.1` is Maven Central HTTP 200, update these
Maven BOM consumers to `1.3.1` and verify each repo with its lightest
dependency-resolution/build check:

- `bluetape4k-workshop`
- `exposed-workshop`
- `exposed-r2dbc-workshop`
- `clinic-appointment`
- `timefold-workshop`

Do not promote these consumers to the partial `1.3.0` artifact.
