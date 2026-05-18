# Org Dependency Governance Plan

## Tasks

1. Expand the sync target set to all active bluetape4k Gradle repositories.
2. Add compatibility-line alias validation to the shared-version sync script.
3. Add a CLI option that prints default repositories for CI cloning.
4. Update CI to clone the script-owned repository list instead of a hard-coded
   partial list.
5. Update README and version-management docs with the central authority model.
6. Add a lessons entry for the Dependabot compatibility-line failure mode.
7. Run script tests, sync checks, and Gradle build.

## Acceptance Criteria

- Shared aliases in downstream catalogs are checked against
  `bluetape4k-dependencies`.
- Major-line aliases fail fast when their version line is wrong.
- CI uses the same repository list as the governance script.
- Docs explain that BOM resolves dependencies and catalog supplies Gradle
  aliases.
- Existing downstream drift is visible as a CI failure until downstream fixes
  are merged.
