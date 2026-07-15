# Central Catalog Adoption Train Checklist

- Flow: `catalog-train-snapshot`
- Train class: catalog/build-contract adoption; no Maven Central publication
- Catalog authority: `bluetape4k-dependencies/gradle/libs.versions.toml`
- Catalog train target: `catalog/2026-07-15-01` (provisional until the irreversible hold)
- Central branch: `build/central-catalog-adoption`
- Consumer branches: `build/central-catalog-adoption`
- Base branch: remote default branch per repository, expected `develop`
- Consumer scope: `bluetape4k-projects`, `bluetape4k-experimental`, `bluetape4k-aws`, `bluetape4k-exposed`, `bluetape4k-graph`, `bluetape4k-image`, `bluetape4k-javers`, `bluetape4k-leader`, `bluetape4k-text`
- Artifact/BOM matrix: N/A — this train publishes no Maven artifacts
- Side-effect authority: user explicitly requested all PR creation and merges on 2026-07-15; merge still requires the repository-policy fresh merge-ready approval gate

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
  - **Evidence:** Central report-only fail-closed guard, strict exception schema, PR fixture/full workspace CI split, catalog SHA-256 sidecar, verified version-delta ledger, and nine consumer exact-SHA/checksum/atomic-cache CI integrations are implemented.
  - **Failure:** Do not commit an incomplete governance contract.

- [x] **CAT-04 — Prove the exact candidate state**
  - **Action:** Run central tests/build/guard, every consumer build, k8sTest, and whitespace/static checks from the exact candidate worktrees.
  - **Evidence:** Central 82-test suite/build/actionlint/checksum passed; exact repository-map guard was clean; all nine consumers passed no-override `help`, `build -x test`, actionlint, and diff checks; `k8sTest --rerun-tasks` produced 9 tests with 0 failures/errors.
  - **Failure:** Repair and rerun affected checks before commit.

- [x] **CAT-05 — Commit with Lore decision records**
  - **Action:** Stage only scoped files and create an intentional Lore commit set per repository.
  - **Evidence:** Central content head `c11c363f3ca945d4ef3ed92f98ce85ecf7c53bc6`; consumer SHAs recorded below; all ten candidate worktrees were clean after commit and validation.
  - **Failure:** Stop before push if unrelated files are staged.

- [x] **CAT-06 — Push candidate branches**
  - **Action:** Push each `build/central-catalog-adoption` branch with upstream tracking.
  - **Evidence:** All ten `build/central-catalog-adoption` branches were pushed with upstream tracking; GitHub PR head OIDs matched the local consumer SHAs and central PR #159 head.
  - **Failure:** Stop PR creation for any mismatched repository.

- [x] **CAT-07 — Create ready-for-review PRs**
  - **Action:** Open one PR per repository with summary, root cause, tests, and `## DoD Status`.
  - **Evidence:** Ready PRs: dependencies #159, projects #1025, experimental #80, aws #374, exposed #380, graph #388, image #291, javers #243, leader #609, text #163. All target `develop`, use the expected head branch, and end with `## DoD Status`.
  - **Failure:** Repair malformed or incorrectly targeted PRs before CI wait.

- [ ] **CAT-08 — Reach merge-ready state**
  - **Action:** Wait for required CI, reviews, and unresolved threads on all PRs.
  - **Evidence:** Live check/review/thread status per PR.
  - **Failure:** Fix failures and rerun until green; normal CI wait remains PENDING.

- [ ] **CAT-09 — Obtain fresh merge-ready approval**
  - **Action:** Report exact PR numbers/head SHAs and request the mandatory fresh merge approval.
  - **Evidence:** User approval after CAT-08 is complete.
  - **Failure:** Do not merge.

- [ ] **CAT-10 — Merge PRs in dependency order**
  - **Action:** Merge central first, then consumers after confirming their pinned catalog commit remains reachable.
  - **Evidence:** Merge commit and live merged state for every PR.
  - **Failure:** Stop on the first failed/stale PR and refresh downstream verification.

- [ ] **CAT-11 — Refresh irreversible catalog-tag hold**
  - **Action:** Confirm merged central SHA, tag absence, clean train state, and exact target `catalog/2026-07-15-01` immediately before tagging.
  - **Evidence:** Timestamped remote/tag/merge checks.
  - **Failure:** Do not create or push the tag.

- [ ] **CAT-12 — Create and verify the catalog train tag**
  - **Action:** Create and push the approved immutable catalog tag at the verified central commit, then read it back remotely.
  - **Evidence:** Remote tag object/commit and consumer resolution proof.
  - **Failure:** Never move or overwrite the tag; use the next train identifier.

- [ ] **CAT-13 — Synchronize local default branches**
  - **Action:** Fast-forward each local default branch after merge while preserving feature worktrees until confirmed cleanup scope.
  - **Evidence:** Local default HEAD equals upstream for all ten repositories.
  - **Failure:** Stop on divergence and report it without destructive reset.

- [ ] **CAT-14 — Report train truth**
  - **Action:** Reconcile checklist counts, URLs, SHAs, tag, validations, N/A rows, and residual risks.
  - **Evidence:** `Required checks: X/Y; N/A: N; Blocked: N` with every applicable row accounted for.
  - **Failure:** Do not claim completion.

## Candidate SHA Table

| Repository | Base | Candidate SHA | PR | Merge SHA |
|---|---|---|---|---|
| bluetape4k-dependencies | `3131b9f006ca819fed908f56384db392de5500e8` | `c11c363f3ca945d4ef3ed92f98ce85ecf7c53bc6` (content head before checklist-only commit) | #159 | pending |
| bluetape4k-projects | `66607608065293eb46a54a2a0d4172de23517a9d` | `f0a3dfd04e0ba36819a1ef97771227811278d310` | #1025 | pending |
| bluetape4k-experimental | `1b0167ae9fc91d206202b04c93ff5540c3db2cf5` | `01c1df278e342a7b52add51aae4d5db61804661b` | #80 | pending |
| bluetape4k-aws | `cf9f7a4ed610f85b4af440bcdabedcab55f47bd1` | `a02afb87c28a429e3cce8f21a39a94d710693cbe` | #374 | pending |
| bluetape4k-exposed | `a4964171d6668cc5de0734184dff7daf4e7b7221` | `8fb8ee303b3dd52caa8010f184e44f1e0e19233c` | #380 | pending |
| bluetape4k-graph | `d6f42b3c80c2dce9e298ec2b8506ef2f879cb7d5` | `c4f85c61a397e9e1fe6917431c5597fdd3c802a0` | #388 | pending |
| bluetape4k-image | `b68aaa17465015e4ee3a7c5a3b709eb129e4a4c9` | `473c2342886fe27e7d614e2871aa0a9484ef2e1f` | #291 | pending |
| bluetape4k-javers | `5cbe876a7164ccc1587f4cfcf792aeba55166276` | `362435be1c81632470ddb2b899beb099f8ee16cc` | #243 | pending |
| bluetape4k-leader | `0ba2ddee92b6ac6c3831c571489002fb7b459c8d` | `cb60543136621a607961a6ab1980f5ca7a911e8c` | #609 | pending |
| bluetape4k-text | `6283d3737185f8a60dfa9840502fcd8ed7b1b71c` | `639ac6d88fdd5199602ca75be63ce09e691b7484` | #163 | pending |

## Validation Evidence

- Central: 82 Python tests, Gradle build, actionlint, SHA-256 verification, PR #159 all checks green.
- Consumers: exact-SHA remote catalog fetch and checksum cache verification 9/9; `build -x test` 9/9; actionlint 9/9; `git diff --check` 9/9.
- Resolved graph: Fabric8 7.8.0, Tomcat JDBC 11.0.24, HikariCP 7.1.0, Flyway 12.10.0, Shadow 9.5.1.
- Regression: `:bluetape4k-testcontainers:k8sTest --rerun-tasks`, 9 tests, 0 failures, 0 errors.
