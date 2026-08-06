# bluetape4k-dependencies 1.4.0 Release Checklist

Status: **CATALOG READY / RELEASE PENDING**
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
- Target catalog tag: `catalog/2026-08-06-03`.
- Dispatch hold: dependencies publication remains held until the catalog PR is
  merged, the signed catalog tag peels to that merge, and the exact release head
  passes CI.

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
- [ ] **PUB-08 / REL-06 — Merge and sign the final stable catalog.**
  Require exact-head PR CI, mergeability, signed `catalog/2026-08-06-03`, and
  downstream declared-ref adoption.
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

## Remaining Release Sequence

1. Open the catalog PR from `catalog/2026-08-06-03-final-stable` to `develop`.
2. Verify exact-head CI, reviews, threads, and mergeability; merge the exact head.
3. Create and verify signed tag `catalog/2026-08-06-03` at the merge commit.
4. Move all nine downstream declared catalog refs to that immutable tag.
5. Re-run dependencies stable-POM, build, and exact-head CI gates.
6. Create and verify signed tag `1.4.0`; let the tag-triggered Publish Release run.
7. Verify public BOM POM/module, every imported stable BOM, Central-only
   resolution, GitHub Release, issue #171, milestone `1.4.0`, receipt, and next
   development version.
8. Remove only worktrees proven clean, merged, and no longer needed.

## Stop Condition

Do not tag the catalog before its exact PR head is merged. Do not tag or publish
`1.4.0` before the signed catalog tag and release-head CI are verified. Stop only
after public Maven Central visibility, GitHub Release, receipts, follow-up
versioning, milestone closure, and conservative cleanup all pass.
