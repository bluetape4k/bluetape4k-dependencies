# bluetape4k-dependencies 1.4.0 Release Checklist

Status: **RELEASE PR READY / PUBLICATION PENDING**
Target version: `1.4.0`
Latest observed external version: `1.3.1`
Release authority: the user explicitly authorized the complete stable train,
including tags, workflow dispatch, publication, GitHub Releases, merges,
milestone closure, follow-up work, and safe cleanup on 2026-08-06.

## Pinned Candidate

- Immutable catalog candidate: `03eb9fe120670e55c77bee998dc318df8184c755`
- Catalog SHA-256: `6c52b7f09e28de2e8b23462d05819c09cb33fe9bf42762f1f97216a8b78dea34`
- Resolved-graph receipt SHA-256:
  `2b1735f5684aa7eb843d91237dae38edf613dc0485d9550537bfe9312ab5652c`
- Full candidate receipt SHA-256:
  `37f66a1a99f48c0be27f697625c06eb2240d023f4b487cb2d36df47c07d24a1c`
- Consumer scope: eight published library repositories plus
  `bluetape4k-experimental` for catalog-only validation.
- Excluded scope: `bluetape4k-workshop` and all example application/workshop
  repositories.
- Catalog merge: `3d2fb6e0087a6bbef5418aee8024bba9dd527e26`.
- Signed catalog tag: `catalog/2026-08-06-03`; remote tag object `97d89596`
  is GitHub-verified and peels to the exact catalog merge.
- Catalog Type P receipt: run `20260806T044439Z-c93bded1`, sequence 14,
  checksum `ad45b248d312f19025cab497b7472d41739600183599e9c54c7b675126e1ad47`.
- Dispatch hold: dependencies publication remains held only until this release
  PR passes exact-head CI and its merge is revalidated for the signed `1.4.0` tag.

## Stable Upstream Matrix

| Repository | Version | Exact release HEAD | Public publications | Gate |
|---|---:|---|---:|---|
| bluetape4k-projects | `1.12.1` | `7cf0b736` | 75 | PASS |
| bluetape4k-exposed | `1.12.1` | `4cc2cce0` | 35 | PASS |
| bluetape4k-image | `0.4.0` | `9961d45d` | 11 | PASS |
| bluetape4k-text | `0.3.0` | `aead213d` | 6 | PASS |
| bluetape4k-graph | `0.6.0` | `72c0256e` | 15 | PASS |
| bluetape4k-javers | `0.3.0` | `978d0490` | 7 | PASS |
| bluetape4k-aws | `0.5.0` | `664e4dfb` | 6 | PASS |
| bluetape4k-leader | `0.5.0` | `721a9a38` | 17 | PASS |

Every selected release has an exact-head signed tag, successful stable release
workflow, public Maven Central POM and Gradle module metadata, and a GitHub
Release. The combined AWS/Javers/Leader Central-only consumer resolved 30
components without SNAPSHOT versions.

## Publication Gates

- [x] **PUB-01 / REL-01 — Pin release identity and inventory.**
- [x] **PUB-02 / REL-02 — Close upstream live planning gaps.**
- [x] **PUB-03 / REL-03 — Prove the final local catalog candidate.**
  Nine downstream full builds, 173 POM/effective-model checks, and 286 isolated
  resolved-graph observations passed at the pinned candidate.
- [x] **PUB-04 / REL-04 / REL-05 — Prove public stable prerequisites.**
  All eight selected upstream BOMs and their publication inventories are public.
- [x] **PUB-05 — Refresh the irreversible dispatch hold for the catalog candidate.**
  Exact heads, catalog bytes, strict repository map, audit, graph, builds, POMs,
  and explicit authority were re-read immediately before candidate publication.
- [x] **PUB-06 — Dispatch upstream releases in dependency order.**
- [x] **PUB-07 — Verify every public stable upstream artifact.**
- [x] **PUB-08 / REL-06 — Merge and sign the final stable catalog.**
  PR #173 and post-merge CI passed, the signed catalog tag is valid, and all
  nine downstream declared refs were adopted through exact-head PRs.
- [ ] **PUB-09 / REL-07 — Publish dependencies 1.4.0.**
  Require exact release-head CI, stable-only generated POM, signed `1.4.0`,
  successful Publish Release, Maven Central visibility, and Central-only consumer.
- [ ] **PUB-10 / REL-08 — Complete public documentation and milestone handoff.**

## Final Candidate Evidence

- Catalog checksum sidecar: PASS.
- Authority audit: 512 authorities, 546 lines, 507 verified metadata records,
  5 preview-only records, 0 unavailable records.
- Resolved graph: 143 specs, 286 observations, failures 0.
- Central adoption and Dependabot governance: PASS.
- Managed catalog: 168 aliases, 8 sub-BOMs.
- Full downstream builds: 9 repositories, failures 0.
- Publication contract: 173 POMs, 45,211 dependency entries, 173 Maven
  effective models, failures 0.
- Candidate repository state: all downstream exact HEADs clean; remote catalog
  commit `03eb9fe120670e55c77bee998dc318df8184c755` verified.
- Catalog PR CI `31075340907` and post-merge CI `31076033049`: PASS.
- Downstream adoption PRs: Projects #1317, AWS #444, Experimental #88,
  Exposed #622, Graph #453, Image #469, Javers #295, Leader #655, and Text #231;
  every exact head passed CI and merged with zero unresolved review threads.
- Fresh merged-default publication contract: 9 repositories, 173 POMs,
  45,211 dependency entries, 173 Maven effective models, failures 0.
- Generated `1.4.0` POM: 77 dependency-management entries, 18 imported BOMs,
  missing versions 0, SNAPSHOT entries 0, SHA-256
  `d6b4305d5fba5ec960532b34864254fd9ed844cb67adbecff1d00eca8f0eb967`.

## Remaining Release Sequence

1. Verify this release PR exact-head CI, reviews, threads, and mergeability;
   merge the exact head.
2. Regenerate the stable-only POM from the merge and verify the remote tag is absent.
3. Create and verify signed tag `1.4.0`; let the tag-triggered Publish Release run.
4. Verify public BOM POM/module, every imported stable BOM, Central-only
   resolution, GitHub Release, issue #171, milestone `1.4.0`, receipt, and next
   development version.
5. Remove only worktrees proven clean, merged, and no longer needed.

## Stop Condition

Do not tag or publish `1.4.0` before the release PR exact head is merged and the
stable-only POM is regenerated from that merge. Stop only after public Maven
Central visibility, GitHub Release, receipts, follow-up versioning, milestone
closure, and conservative cleanup all pass.
