# Issue #208 Kotlinx Serialization Catalog Lesson

## Context

`bluetape4k-image` had an unversioned local JSON alias. Removing its temporary
1.11.0 pin exposed `kotlinx-serialization-json:.`, because the imported central
catalog did not yet define the alias or version.

## Decision

- Own `kotlinx-serialization = "1.11.0"` in `bluetape4k-dependencies`.
- Publish versioned BOM and JSON aliases from the central catalog.
- Import the Serialization BOM in the Java platform as a separate constraint
  contract.
- Prove the consumer with `bluetape4kDependenciesCatalogPath` before tagging;
  update the default ref only after the merged commit receives an immutable tag.

## Outcome and Evidence

- The focused contract test was RED for the missing alias/version and BOM import,
  then GREEN after the four-line production change.
- All 64 Python tests passed; 168 managed aliases and artifacts were verified;
  shared versions and Dependabot ignores were aligned.
- Gradle build and local publication passed, and the generated POM imports
  `kotlinx-serialization-bom:1.11.0`.
- The image consumer resolved `bt4k.kotlinx.serialization.json` without a local
  version pin and reran all 12 focused model tests successfully.

## What Future Agents Should Do

- Do not assume `tomllib`: the repository baseline may be system Python 3.9.
  Reuse the dependency-free parsing style of existing governance scripts.
- Keep catalog aliases and Java platform BOM imports explicit; they solve
  different consumer contracts.
- Run Gradle serially per worktree. Parallel invocations deleted the shared
  `in-progress-results-generic.bin` after 12 passing tests and caused a false
  task failure.
- Before the catalog tag exists, nested TestKit builds will not inherit a
  top-level catalog-path override. Use the approved focused proof, then run the
  full default-ref suite after tagging.
- Never rewrite a catalog tag. A correction needs a later date-sequence ref and
  a new approval.
