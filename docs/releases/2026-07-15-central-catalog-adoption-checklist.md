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

- [ ] **CAT-01 — Pin repository identities**
  - **Action:** Record exact remotes, base branches, candidate branches, and candidate SHAs for all ten repositories.
  - **Evidence:** 2026-07-15 live inspection confirmed all ten remotes under `bluetape4k/*`, remote default `develop`, and candidate branch `build/central-catalog-adoption`; final candidate SHAs remain pending commits.
  - **Failure:** Stop before push or PR creation.

- [x] **CAT-02 — Close live PR and catalog-tag conflicts**
  - **Action:** Check existing PRs for each candidate branch and confirm the provisional catalog tag does not exist.
  - **Evidence:** 2026-07-15 `gh pr list --state all --head build/central-catalog-adoption` returned `[]` for all ten repositories; `git ls-remote --tags origin refs/tags/catalog/2026-07-15-01` returned no tag.
  - **Failure:** Reuse/retarget the existing PR or choose the next unused train tag.

- [ ] **CAT-03 — Complete catalog governance implementation**
  - **Action:** Add PR-time guard enforcement, declared-ref integrity, and an intentional resolved-version delta ledger.
  - **Evidence:** Reviewed diffs, guard tests, CI workflow validation, and consumer ref checks.
  - **Failure:** Do not commit an incomplete governance contract.

- [ ] **CAT-04 — Prove the exact candidate state**
  - **Action:** Run central tests/build/guard, every consumer build, k8sTest, and whitespace/static checks from the exact candidate worktrees.
  - **Evidence:** Per-repository commands and exit status table.
  - **Failure:** Repair and rerun affected checks before commit.

- [ ] **CAT-05 — Commit with Lore decision records**
  - **Action:** Stage only scoped files and create one intentional commit per repository.
  - **Evidence:** Ten commit SHAs and clean scoped status review.
  - **Failure:** Stop before push if unrelated files are staged.

- [ ] **CAT-06 — Push candidate branches**
  - **Action:** Push each `build/central-catalog-adoption` branch with upstream tracking.
  - **Evidence:** Remote branch SHA equals local SHA for all ten repositories.
  - **Failure:** Stop PR creation for any mismatched repository.

- [ ] **CAT-07 — Create ready-for-review PRs**
  - **Action:** Open one PR per repository with summary, root cause, tests, and `## DoD Status`.
  - **Evidence:** Ten PR URLs, exact base/head, and live body read-back.
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
| bluetape4k-dependencies | pending | pending | pending | pending |
| bluetape4k-projects | pending | pending | pending | pending |
| bluetape4k-experimental | pending | pending | pending | pending |
| bluetape4k-aws | pending | pending | pending | pending |
| bluetape4k-exposed | pending | pending | pending | pending |
| bluetape4k-graph | pending | pending | pending | pending |
| bluetape4k-image | pending | pending | pending | pending |
| bluetape4k-javers | pending | pending | pending | pending |
| bluetape4k-leader | pending | pending | pending | pending |
| bluetape4k-text | pending | pending | pending | pending |

## Validation Evidence

Pending.
