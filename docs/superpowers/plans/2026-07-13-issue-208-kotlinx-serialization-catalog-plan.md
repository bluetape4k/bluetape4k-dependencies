# Issue #208 Kotlinx Serialization Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make kotlinx-serialization 1.11.0 a central catalog and BOM contract so `bluetape4k-image#208` can remove its repo-local version pin.

**Architecture:** The central catalog owns the version and versioned BOM/JSON aliases; the Java platform imports the Serialization BOM. The image consumer uses the checked-out central `bt4k` catalog, validates against the prerequisite worktree before tagging, and pins the merged catalog tag only after its irreversible-action gate.

**Tech Stack:** Gradle 9.6, Gradle Kotlin DSL, Java Platform, TOML version catalog, Python `unittest`, kotlinx-serialization 1.11.0.

---

## Preconditions and Boundaries

- Repository: `bluetape4k-dependencies`
- Worktree: `.worktrees/build-issue-208-kotlinx-serialization-catalog`
- Branch: `build/issue-208-kotlinx-serialization-catalog`
- Base: `origin/develop` at `ecefcf855f44e8d82fb1d5202147e1c504ae0cef`
- Consumer: `bluetape4k-image`, branch `perf/issue-208-codec-runtime-matrix`
- Target catalog ref: `catalog/2026-07-13-00`
- PR creation, merge, tag creation/push, and consumer PR remain separate workflow gates.
- Maven BOM version and publication are unchanged.

### Task 1: Lock the Central Serialization Contract

**Files:**
- Create: `tests/test_kotlinx_serialization_catalog.py`
- Modify: `gradle/libs.versions.toml`
- Modify: `build.gradle.kts`
- Modify: `CHANGELOG.md`

- [x] **Step 1: Write the failing catalog contract test**

Create a dependency-free `unittest` that reads the catalog text with the same
Python 3.9-compatible regular-expression style used by the repository scripts
and asserts:

```python
self.assertRegex(catalog_text, r'(?m)^kotlinx-serialization\s*=\s*"1\.11\.0"')
self.assert_catalog_alias("kotlinx-serialization-bom", "org.jetbrains.kotlinx:kotlinx-serialization-bom")
self.assert_catalog_alias("kotlinx-serialization-json", "org.jetbrains.kotlinx:kotlinx-serialization-json")
self.assertIn("api(platform(libs.kotlinx.serialization.bom))", build_text)
```

- [x] **Step 2: Observe RED**

```bash
python3 -m unittest tests/test_kotlinx_serialization_catalog.py
```

Expected: fail because the central version and aliases are absent.

- [x] **Step 3: Add the minimal central catalog and BOM contract**

Add under the shared runtime version block:

```toml
kotlinx-serialization = "1.11.0"  # https://mvnrepository.com/artifact/org.jetbrains.kotlinx/kotlinx-serialization-bom
```

Add library aliases:

```toml
kotlinx-serialization-bom = { module = "org.jetbrains.kotlinx:kotlinx-serialization-bom", version.ref = "kotlinx-serialization" }
kotlinx-serialization-json = { module = "org.jetbrains.kotlinx:kotlinx-serialization-json", version.ref = "kotlinx-serialization" }
```

Import the BOM immediately after the external platform imports begin:

```kotlin
api(platform(libs.kotlinx.serialization.bom))
```

Add an English Unreleased changelog entry for the new central catalog and BOM
contract.

- [x] **Step 4: Observe GREEN**

```bash
python3 -m unittest tests/test_kotlinx_serialization_catalog.py
```

Expected: PASS.

### Task 2: Validate Central Governance and Downstream Blast Radius

**Files:** no intended source changes beyond Task 1.

- [x] **Step 1: Run focused and full Python validation**

```bash
python3 -m py_compile scripts/*.py tests/*.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

Expected: all tests pass.

- [x] **Step 2: Run generated-catalog and downstream checks without writes**

```bash
scripts/sync-managed-catalog.py --workspace-root /Users/debop/work/bluetape4k --check --summary
scripts/sync-shared-versions.py --workspace /Users/debop/work/bluetape4k --check --summary
scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --check --summary
scripts/verify-managed-artifacts.py --summary --allow-snapshots
```

Expected: no unexpected downstream drift. A repo already declaring
`kotlinx-serialization` at another value is a scope failure, not an automatic
write authorization.

- [x] **Step 3: Verify the Gradle platform**

```bash
./gradlew build publishToMavenLocal --no-configuration-cache --console=plain
git diff --check
```

Expected: PASS and the generated POM resolves the Serialization BOM at 1.11.0.

### Task 3: Prove the Image Consumer Without a Local Pin

**Files in `bluetape4k-image`:**
- Modify: `benchmark/images-benchmark/build.gradle.kts`
- Restore: `gradle/libs.versions.toml` serialization lines to `origin/develop`
- Later modify: `settings.gradle.kts` default ref after the tag exists

- [x] **Step 1: Replace the consumer accessor**

Use:

```kotlin
implementation(bt4k.kotlinx.serialization.json)
```

Remove the branch-local `kotlinx-serialization = "1.11.0"` version and restore
the local JSON alias to its unversioned `origin/develop` form.

- [x] **Step 2: Validate against the central worktree catalog**

```bash
./gradlew :bluetape4k-images-benchmark:test \
  --tests "io.bluetape4k.images.benchmark.CodecMatrixModelsTest" \
  -Pbluetape4kDependenciesCatalogPath=/Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/build-issue-208-kotlinx-serialization-catalog/gradle/libs.versions.toml \
  -Pvips.impl=java25 --console=plain
```

Expected: PASS with no image-local serialization version pin.

Run this verification serially with no other Gradle invocation in the same
image worktree. The focused pre-tag proof intentionally selects
`CodecMatrixModelsTest`; nested TestKit builds do not inherit the top-level
catalog-path override and belong to the post-tag default-ref verification.

- [x] **Step 3: Preserve the pre-tag boundary**

Do not update `settings.gradle.kts` to `catalog/2026-07-13-00` and do not claim
the default build is ready until the tag exists. Keep the consumer change
uncommitted or explicitly blocked at this gate.

### Task 4: Review, Commit, and Stop Before External Delivery

**Files:** central spec/plan/test/catalog/build plus
`docs/review/2026-07-13-issue-208-kotlinx-serialization-catalog-review.md` and
`docs/lessons/2026-07-13-issue-208-kotlinx-serialization-catalog.md`.

- [x] **Step 1: Review exact diffs and converge P0/P1**

Run performance, stability, security, operator/Ops, developer/API, user/caller,
and main-session integration lenses. Confirm catalog/BOM separation, downstream
blast radius, tag ordering, and consumer proof.

- [x] **Step 2: Write the durable lesson**

Record the empty-version failure, the central catalog/BOM distinction, local
catalog-path validation before tagging, and the fresh tag-approval guard in
`docs/lessons/2026-07-13-issue-208-kotlinx-serialization-catalog.md`.

- [x] **Step 3: Commit the central prerequisite**

```bash
git add CHANGELOG.md gradle/libs.versions.toml build.gradle.kts \
  tests/test_kotlinx_serialization_catalog.py \
  docs/superpowers/specs/2026-07-13-issue-208-kotlinx-serialization-catalog-design.md \
  docs/superpowers/plans/2026-07-13-issue-208-kotlinx-serialization-catalog-plan.md \
  docs/review/2026-07-13-issue-208-kotlinx-serialization-catalog-review.md \
  docs/lessons/2026-07-13-issue-208-kotlinx-serialization-catalog.md
git commit -m "build: govern kotlinx serialization centrally"
```

- [x] **Step 4: Stop at PR and tag boundaries**

Report the exact central head and validation. PR creation requires explicit
authority naming repository `bluetape4k-dependencies`, base `develop`, and head
`build/issue-208-kotlinx-serialization-catalog`. After merge-ready review and
fresh merge approval, tag creation/push requires another fresh CG-X01 approval
for `catalog/2026-07-13-00` at the merged `origin/develop` SHA.

## Rollback

- Before tag: revert the central commit and restore the image consumer accessor.
- After tag: never rewrite the tag; publish a later date-sequence catalog ref and
  move the consumer in a reviewed follow-up.
- No accepted benchmark evidence or production API is modified by this prerequisite.
