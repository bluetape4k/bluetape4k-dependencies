# Central Catalog Adoption Train Checklist

- Flow: `catalog-train-snapshot`
- Train class: catalog/build-contract adoption; no Maven Central publication
- Catalog authority: `bluetape4k-dependencies/gradle/libs.versions.toml`
- Catalog train target: `catalog/2026-07-15-01`
- Central branch: `build/central-catalog-adoption`
- Consumer branches: `build/central-catalog-adoption`
- Base branch: remote default branch per repository, expected `develop`
- Consumer scope: `bluetape4k-projects`, `bluetape4k-experimental`, `bluetape4k-aws`, `bluetape4k-exposed`, `bluetape4k-graph`, `bluetape4k-image`, `bluetape4k-javers`, `bluetape4k-leader`, `bluetape4k-text`
- Artifact/BOM matrix: N/A — this train publishes no Maven artifacts
- Side-effect authority: user explicitly requested all PR creation and merges on 2026-07-15, gave the fresh merge-ready approval after CAT-08, and approved catalog-train closeout/tagging on 2026-07-16

- [x] **CAT-01 — Pin repository identities**
  - **Action:** Record exact remotes, base branches, candidate branches, and candidate SHAs for all ten repositories.
  - **Evidence:** 2026-07-15 live inspection confirmed all ten remotes under `bluetape4k/*`, remote default `develop`, candidate branch `build/central-catalog-adoption`, and the base/candidate SHAs recorded below. The central content SHA is recorded before this checklist-only follow-up commit to avoid a self-referential SHA update loop.
  - **Failure:** Stop before push or PR creation.

- [x] **CAT-02 — Close live PR and catalog-tag conflicts**
  - **Action:** Check existing PRs for each candidate branch and confirm the provisional catalog tag does not exist.
  - **Evidence:** 2026-07-15 `gh pr list --state all --head build/central-catalog-adoption` returned `[]` for all ten repositories; `git ls-remote --tags origin refs/tags/catalog/2026-07-15-01` returned no tag.
  - **Failure:** Reuse/retarget the existing PR or choose the next unused train tag.

- [x] **CAT-03 — Complete catalog governance implementation**
  - **Action:** Add PR-time guard enforcement, declared-ref integrity, and an intentional resolved-version delta ledger.
  - **Evidence:** Central report-only fail-closed guard, strict exception schema, settings/workflow ref parity, immutable loader contract checks, PR fixture/full workspace CI split, catalog SHA-256 sidecar, verified version-delta ledger, and nine consumer exact-SHA/checksum/bounded-download/atomic-cache CI integrations are implemented.
  - **Failure:** Do not commit an incomplete governance contract.

- [x] **CAT-04 — Prove the exact candidate state**
  - **Action:** Run central tests/build/guard, every consumer build, k8sTest, and whitespace/static checks from the exact candidate worktrees.
  - **Evidence:** Central 88-test suite/build/actionlint/checksum passed; exact repository-map guard was clean; all nine consumers passed no-override `help`, actionlint, and diff checks; representative symbolic-ref, symlink, and malformed-catalog rejection passed; text full build and failing example compile tasks passed; `k8sTest --rerun-tasks` produced 9 tests with 0 failures/errors.
  - **Failure:** Repair and rerun affected checks before commit.

- [x] **CAT-05 — Commit with Lore decision records**
  - **Action:** Stage only scoped files and create an intentional Lore commit set per repository.
  - **Evidence:** Central content head `2646d2cd2d4ecc09654c2ac6ef11cfd6679f1086`; consumer SHAs recorded below; all ten candidate worktrees were clean after commit and validation.
  - **Failure:** Stop before push if unrelated files are staged.

- [x] **CAT-06 — Push candidate branches**
  - **Action:** Push each `build/central-catalog-adoption` branch with upstream tracking.
  - **Evidence:** All ten `build/central-catalog-adoption` branches were pushed with upstream tracking; GitHub PR head OIDs matched the local consumer SHAs and central PR #159 head.
  - **Failure:** Stop PR creation for any mismatched repository.

- [x] **CAT-07 — Create ready-for-review PRs**
  - **Action:** Open one PR per repository with summary, root cause, tests, and `## DoD Status`.
  - **Evidence:** Ready PRs: dependencies #159, projects #1025, experimental #80, aws #374, exposed #380, graph #388, image #291, javers #243, leader #609, text #163. All target `develop`, use the expected head branch, and end with `## DoD Status`.
  - **Failure:** Repair malformed or incorrectly targeted PRs before CI wait.

- [x] **CAT-08 — Reach merge-ready state**
  - **Action:** Wait for required CI, reviews, and unresolved threads on all PRs.
  - **Evidence:** Exact-head GitHub checks passed 202/202: dependencies 5/5, projects 19/19, experimental 6/6, aws 17/17, exposed 36/36, graph 18/18, image 25/25, javers 17/17, leader 46/46, text 13/13. All ten PRs were OPEN, non-draft, MERGEABLE, with 0 reviews and 0 unresolved threads. Independent exact-diff re-review returned GO with P0=0/P1=0/P2=0.
  - **Failure:** Fix failures and rerun until green; normal CI wait remains PENDING.

- [x] **CAT-09 — Obtain fresh merge-ready approval**
  - **Action:** Report exact PR numbers/head SHAs and request the mandatory fresh merge approval.
  - **Evidence:** The exact ten PR/head pairs, 202/202 green checks, zero reviews/threads, and independent GO review were reported; the user then explicitly approved merge with `머지하자`.
  - **Failure:** Do not merge.

- [x] **CAT-10 — Merge PRs in dependency order**
  - **Action:** Merge central first, then consumers after confirming their pinned catalog commit remains reachable.
  - **Evidence:** Dependencies #159 was merged first with merge commit `510d78be2b7c8c3d2377492ad37937ef8687b4d0`, preserving catalog content commit `2646d2cd2d4ecc09654c2ac6ef11cfd6679f1086` as an ancestor. All nine consumer PRs were then squash-merged from their approved exact heads; GitHub reported all ten PRs `MERGED` with the merge SHAs below.
  - **Failure:** Stop on the first failed/stale PR and refresh downstream verification.

- [x] **CAT-11 — Refresh irreversible catalog-tag hold**
  - **Action:** Confirm merged central SHA, tag absence, clean train state, and exact target `catalog/2026-07-15-01` immediately before tagging.
  - **Evidence:** On 2026-07-16, local `develop` and `origin/develop` both resolved to `510d78be2b7c8c3d2377492ad37937ef8687b4d0`; all ten PRs were `MERGED`; the central guard was clean; and the target tag was absent locally and remotely. `release.yml` accepts only numeric SemVer tags, so the catalog tag could not trigger Maven publication.
  - **Failure:** Do not create or push the tag.

- [x] **CAT-12 — Create and verify the catalog train tag**
  - **Action:** Create and push the approved immutable catalog tag at the verified central commit, then read it back remotely.
  - **Evidence:** Annotated tag `catalog/2026-07-15-01` was pushed as tag object `086824230017854c028d49763061ff966a196192`; the remote peeled commit is `510d78be2b7c8c3d2377492ad37937ef8687b4d0`. The consumers' pinned catalog content commit remains reachable from that commit.
  - **Failure:** Never move or overwrite the tag; use the next train identifier.

- [x] **CAT-13 — Synchronize local default branches**
  - **Action:** Fast-forward each local default branch after merge while preserving feature worktrees until confirmed cleanup scope.
  - **Evidence:** Local `develop` equals `origin/develop` for all ten repositories. The experimental repository's existing `docs/rename-bluetape-skills` checkout was preserved while its local `develop` ref was fast-forwarded; all current worktrees remained clean.
  - **Failure:** Stop on divergence and report it without destructive reset.

- [x] **CAT-14 — Report train truth**
  - **Action:** Reconcile checklist counts, URLs, SHAs, tag, validations, N/A rows, and residual risks.
  - **Evidence:** Required checks: 14/14; N/A: 1 Maven artifact/BOM publication row; Blocked: 0. All ten PRs are merged, the immutable catalog tag is remotely verified, all default branches are synchronized, and the central adoption guard is clean. The only residual work is optional local feature-worktree/branch cleanup.
  - **Failure:** Do not claim completion.

## Candidate SHA Table

| Repository | Base | Candidate SHA | PR | Merge SHA |
|---|---|---|---|---|
| bluetape4k-dependencies | `3131b9f006ca819fed908f56384db392de5500e8` | `2646d2cd2d4ecc09654c2ac6ef11cfd6679f1086` (content head before checklist-only commit) | #159 | `510d78be2b7c8c3d2377492ad37937ef8687b4d0` |
| bluetape4k-projects | `66607608065293eb46a54a2a0d4172de23517a9d` | `f40d594d6f4c0c9512fcddfa80f1b909efe2cf9c` | #1025 | `09a1963915f7b89c410d40a3a23f0b6cf7f8a5e0` |
| bluetape4k-experimental | `1b0167ae9fc91d206202b04c93ff5540c3db2cf5` | `fc1fdef0d31eef44f4b0f94c1f69ffdec45b3507` | #80 | `0a7c11ba8699099e2ad9a4eb8d2438dd04ee32fa` |
| bluetape4k-aws | `cf9f7a4ed610f85b4af440bcdabedcab55f47bd1` | `4a3ee278c01d451751222ad4b48b4a027a47c984` | #374 | `113052aba1323135cf7e25b873ddf5a954525ebc` |
| bluetape4k-exposed | `a4964171d6668cc5de0734184dff7daf4e7b7221` | `d4e542e7ea97bc71f3488a030a60f08feffdc944` | #380 | `0907513a4dfb358a39f2b79002ec6ccd049635c6` |
| bluetape4k-graph | `d6f42b3c80c2dce9e298ec2b8506ef2f879cb7d5` | `5492e782dba85136a45194545e348e123e7a274f` | #388 | `5961a7aba5781b9329488a98b2dc624c777b9a89` |
| bluetape4k-image | `b68aaa17465015e4ee3a7c5a3b709eb129e4a4c9` | `d5208e056e17a9b1d10845536d0edde3e3690114` | #291 | `e2ffa4c85ff1bf8b2b6fed9ef9a4386e93286605` |
| bluetape4k-javers | `5cbe876a7164ccc1587f4cfcf792aeba55166276` | `8676738b1d2797551fdd39fcc884c2153c74c605` | #243 | `361b3391a7c54afe6d6586462cb99a235fd2eec8` |
| bluetape4k-leader | `0ba2ddee92b6ac6c3831c571489002fb7b459c8d` | `a38657dce7234e8ad9971eeaf9a98ca36bfdfbd9` | #609 | `81858b0d634853cd95469799580de3bcf44e1a12` |
| bluetape4k-text | `6283d3737185f8a60dfa9840502fcd8ed7b1b71c` | `59ffbb214cdc41665f254ac016666af9cdc22864` | #163 | `2fef5c4bf65ae2865e0b03900f5ce7bbd24f2d8f` |

## Validation Evidence

- Central: 88 Python tests, Gradle build, actionlint, SHA-256 verification, exact repository-map guard, PR #159 all checks green.
- Consumers: immutable exact-SHA remote catalog fetch, bounded download, checksum/structure cache verification 9/9; Gradle `help` 9/9; actionlint 9/9; `git diff --check` 9/9; GitHub checks 197/197 across consumer PRs.
- Resolved graph: Fabric8 7.8.0, Tomcat JDBC 11.0.24, HikariCP 7.1.0, Flyway 12.10.0, Shadow 9.5.1.
- Regression: `:bluetape4k-testcontainers:k8sTest --rerun-tasks`, 9 tests, 0 failures, 0 errors.
- Closeout: remote annotated tag `catalog/2026-07-15-01` peels to central merge `510d78be2b7c8c3d2377492ad37937ef8687b4d0`; post-merge central guard and local/remote default-branch parity checks passed.
