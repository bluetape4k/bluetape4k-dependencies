# bluetape4k-dependencies 1.5.0 Development Train Checklist

Status: **IN PROGRESS / SNAPSHOT TRAIN**
Target line: `1.5.0-SNAPSHOT`
Stable publication target: `1.5.0` (not authorized by this checklist)
Latest observed stable version: `1.4.0`
Release authority: the user explicitly requested continuation of the approved
post-1.4.0 work on 2026-08-07. This checklist authorizes snapshot validation,
not a stable tag, GitHub Release, or Maven Central stable publication.

## Scope and boundaries

- Central source of truth: `bluetape4k-dependencies` `develop` at
  `1d23b2386ea68ada57eff349fc2e9383eb279706`.
- Current catalog contract: `gradle/libs.versions.toml` at the same develop
  head; stable consumers continue to pin immutable catalog tag
  `catalog/2026-08-06-03` until a new catalog train is approved.
- Published BOM snapshot: `bluetape4k-dependencies:1.5.0-SNAPSHOT`.
- Published-library snapshot scope: Projects, AWS, Exposed, Graph, Image,
  Javers, Leader, and Text. Experimental remains catalog-only.
- Explicit exclusion: `bluetape4k-workshop`, all workshops, and example or
  application repositories.
- Stable 1.4.0 artifacts, tags, GitHub Releases, source manuals, and
  `bluetape4k.github.io` are historical/publication-complete and must not be
  retagged or overwritten.

## Pinned development heads

| Repository | Development version | Exact `develop` head | Snapshot status |
|---|---:|---|---|
| bluetape4k-dependencies | `1.5.0-SNAPSHOT` | `1d23b2386ea68ada57eff349fc2e9383eb279706` | Published; verify metadata |
| bluetape4k-projects | `1.13.0-SNAPSHOT` | `ffde7b8be16124b1c538bb318a7d482927f738ad` | Published; verify metadata |
| bluetape4k-aws | `0.6.0-SNAPSHOT` | `76f9caed95263acef6f6143ded9519264b88c853` | Published; verify metadata |
| bluetape4k-exposed | `1.13.0-SNAPSHOT` | `6bff7d9939243d166e212ce840ee90261e7239c7` | Published; verify metadata |
| bluetape4k-graph | `0.7.0-SNAPSHOT` | `f29ddc29f5b59a82f218b9f815046fac288ecd30` | Published; verify metadata |
| bluetape4k-image | `0.5.0-SNAPSHOT` | `e56fea655ad3168527b5f663d114df722ad55d3f` | **Blocked; metadata 404** |
| bluetape4k-javers | `0.4.0-SNAPSHOT` | `fb279cdba663bde80d9b146049aca146433a9b36` | Published; verify metadata |
| bluetape4k-leader | `0.6.0-SNAPSHOT` | `5a4837e374df53c5a2c272b7a1d883f07abda6ae` | Published; verify metadata |
| bluetape4k-text | `0.4.0-SNAPSHOT` | `c5726bea30591e4c5c26523ccac4ad62c5ea9237` | Published; verify metadata |

## Ordered gates

- [x] **PUB-01 / REL-01 — Pin target inventory and authority.**
  The target is the 1.5.0 development snapshot line; stable publication remains
  outside this checklist. Workshop scope is explicitly excluded.
- [x] **PUB-02 / REL-02 — Query live topology and planning state.**
  The eight published libraries plus dependencies are the publisher inventory;
  Experimental is catalog-only and workshop/example repositories are excluded.
- [x] **PUB-03 / REL-03 — Establish the exact candidate state.**
  Central catalog checks and the publication-POM gate must be rerun after the
  Image snapshot is repaired.
- [ ] **PUB-06 — Complete the Image snapshot gate.**
  Run full Nightly validation, then publish `0.5.0-SNAPSHOT` from the exact
  `develop` head and verify public snapshot metadata. The previous workflow
  skipped `Test / images-ocr`, so its publish job was correctly withheld.
- [ ] **PUB-08 — Verify all downstream snapshots.**
  Confirm the eight library snapshot metadata records, matching heads, and
  no missing publisher after Image recovery.
- [ ] **PUB-09 — Re-run catalog and publication-POM validation.**
  Required commands are `sync-managed-catalog`, `sync-shared-versions`,
  `sync-dependabot-ignores`, and `verify-publication-poms.py --workspace ..`.
- [ ] **PUB-10 — Complete post-release cleanup.**
  Audit linked worktrees and GitHub milestone/issue/Dependabot follow-up state.
  Remove only proven merged worktrees; preserve dirty, detached, ambiguous, or
  unmerged branches.
- [ ] **PUB-11 — Prepare the next stable release gate.**
  Record the final snapshot matrix and create a separate approved stable
  release checklist before any `1.5.0` tag or stable publication.

## Current evidence and recovery

- Dependencies snapshot workflow: run `31084129721`, exact head
  `1d23b2386ea68ada57eff349fc2e9383eb279706`, successful.
- Image snapshot workflow: run `31136273045`, overall success but publish job
  skipped because `Test / images-ocr` was skipped; this is not publication
  evidence.
- Prior central gates: managed catalog `168 aliases / 8 sub-BOMs`, shared
  version adoption clean, Dependabot ignore sync clean, and publication-POM
  gate `173 POMs / 45,211 dependency entries / 173 Maven models / failures 0`.
- Recovery rule: do not use `override_full_validation` unless a later explicit
  release decision changes the gate; the default repair is a full Nightly run
  followed by validation-run-id snapshot publication.

## Stop condition

This checklist becomes complete only when every applicable snapshot and
catalog/POM gate has fresh PASS evidence, the safe cleanup audit has a recorded
disposition, and a separate stable-release checklist exists. Until then, do
not create a `1.5.0` stable tag, GitHub Release, or stable Maven publication.
