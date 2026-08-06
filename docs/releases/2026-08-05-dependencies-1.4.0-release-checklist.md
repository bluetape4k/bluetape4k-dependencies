# bluetape4k-dependencies 1.4.0 Release Checklist

Status: **PUBLISHED / COMPLETE**
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
- Dispatch hold: released after exact-head PR and post-merge CI passed at merge
  `8a738f084de98323b5651c548b9d2c354fb22329`.

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
- [x] **PUB-09 / REL-07 — Publish dependencies 1.4.0.**
  PR CI `31079582802`, post-merge CI `31080318880`, signed tag `1.4.0`,
  Publish Release `31081143359`, Maven Central metadata, and the Central-only
  consumer all passed.
- [x] **PUB-10 / REL-08 — Complete public documentation and milestone handoff.**
  GitHub Release `1.4.0` is public; issues #168/#171 and milestone `1.4.0` are
  closed; Type P receipt `20260806T074128Z-5d92140b` is complete.

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

## Completion Evidence

1. Release PR #174 merged as `8a738f084de98323b5651c548b9d2c354fb22329`
   after all exact-head checks and zero unresolved review threads.
2. Generated and public POM SHA-256 both equal
   `d6b4305d5fba5ec960532b34864254fd9ed844cb67adbecff1d00eca8f0eb967`.
3. GitHub verified signed tag `1.4.0` as valid and exact-head; release run
   `31081143359` completed successfully.
4. Maven Central-only resolution imported `bluetape4k-dependencies:1.4.0` and
   resolved eight representative modules without explicit module versions.
5. The repository moved to the `1.5.0` development line after public validation.

## Stop Condition

The `1.4.0` train is closed. Do not create another stable tag or publication
without a new approved release checklist, exact-head validation, and explicit
publication authority.
