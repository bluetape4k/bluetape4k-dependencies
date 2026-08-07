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
| bluetape4k-dependencies | `1.5.0-SNAPSHOT` | `1d23b2386ea68ada57eff349fc2e9383eb279706` | Metadata HTTP 200; build 1 |
| bluetape4k-projects | `1.13.0-SNAPSHOT` | `ffde7b8be16124b1c538bb318a7d482927f738ad` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-aws | `0.6.0-SNAPSHOT` | `76f9caed95263acef6f6143ded9519264b88c853` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-exposed | `1.13.0-SNAPSHOT` | `6bff7d9939243d166e212ce840ee90261e7239c7` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-graph | `0.7.0-SNAPSHOT` | `f29ddc29f5b59a82f218b9f815046fac288ecd30` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-image | `0.5.0-SNAPSHOT` | `e56fea655ad3168527b5f663d114df722ad55d3f` | Full Nightly/publish repaired; metadata HTTP 200; build 1 |
| bluetape4k-javers | `0.4.0-SNAPSHOT` | `fb279cdba663bde80d9b146049aca146433a9b36` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-leader | `0.6.0-SNAPSHOT` | `5a4837e374df53c5a2c272b7a1d883f07abda6ae` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |
| bluetape4k-text | `0.4.0-SNAPSHOT` | `c5726bea30591e4c5c26523ccac4ad62c5ea9237` | Exact-head Nightly/publish; metadata HTTP 200; build 2 |

## Ordered gates

- [x] **PUB-01 / REL-01 — Pin target inventory and authority.**
  The target is the 1.5.0 development snapshot line; stable publication remains
  outside this checklist. Workshop scope is explicitly excluded.
- [x] **PUB-02 / REL-02 — Query live topology and planning state.**
  The eight published libraries plus dependencies are the publisher inventory;
  Experimental is catalog-only and workshop/example repositories are excluded.
- [x] **PUB-03 / REL-03 — Establish the exact candidate state.**
  Central catalog checks and the publication-POM gate passed after the Image
  snapshot was repaired.
- [x] **PUB-06 — Complete the Image snapshot gate.**
  Full Nightly `31175781034` and publish `31176250467` passed at the exact
  `develop` head; `bluetape4k-image-bom:0.5.0-SNAPSHOT` metadata is HTTP 200
  (`lastUpdated=20260807120023`, build 1). All required OCR and VIPS jobs ran.
- [x] **PUB-08 — Verify all downstream snapshots.**
  Exact-head Nightly and workflow-run publication passed for all eight library
  repositories. All nine in-scope BOM metadata records are HTTP 200; refreshed
  downstream records are build 2 except the repaired Image record (build 1).
- [x] **PUB-09 — Re-run catalog and publication-POM validation.**
  Required commands are `sync-managed-catalog`, `sync-shared-versions`,
  `sync-dependabot-ignores`, and `verify-publication-poms.py --workspace ..`;
  all passed, including `failures=0`, `repositories=9`, `files=173`,
  `dependencies=45211`, and `maven_models=173`.
- [x] **PUB-10 — Complete post-release cleanup.**
  Audit linked worktrees and GitHub milestone/issue/Dependabot follow-up state.
  No safe worktree removal candidate existed; dirty, detached, ambiguous, or
  unmerged branches were preserved. Seven empty historical release milestones
  were closed; backlog/current milestones and open issues/PRs remain open.
- [x] **PUB-11 — Prepare the next stable release gate.**
  Record the final snapshot matrix and create a separate approved stable
  release checklist before any `1.5.0` tag or stable publication.

## Current evidence and recovery

- Dependencies snapshot workflow: run `31084129721`, exact head
  `1d23b2386ea68ada57eff349fc2e9383eb279706`, successful.
- Image recovery: Nightly `31175781034` and publish `31176250467` passed at
  `e56fea655ad3168527b5f663d114df722ad55d3f`.
- Exact-head refresh runs: Projects `31177226943`/`31178898628`, AWS
  `31177229239`/`31177844933`, Exposed `31177231582`/`31178860395`, Graph
  `31177233756`/`31177779183`, Javers `31177236072`/`31178149238`, Leader
  `31177238325`/`31178660581`, and Text `31177240333`/`31177822624`.
- Central gates: managed catalog `168 aliases / 8 sub-BOMs`, shared-version
  adoption clean, Dependabot ignore sync clean, and publication-POM gate
  `173 POMs / 45,211 dependency entries / 173 Maven models / failures 0`.
- The prior snapshot heads differed only under `docs/manual/**` and
  `scripts/manual/**`, but all seven libraries were still refreshed from the
  current exact `develop` SHA to satisfy the snapshot gate without a waiver.
- Recovery rule: do not use `override_full_validation` unless a later explicit
  release decision changes the gate; the Image repair used full Nightly plus
  validation-run-id publication.

## Cleanup and stable handoff

- Historical empty milestones closed: dependencies `1.3.0`/`1.3.1`, Projects
  `1.12.0`/`1.12.1`, and Text `0.1.1`/`0.1.2`/`0.1.3`.
- Current catalog consumers remain pinned to immutable commit
  `catalog/2026-08-06-03` (`3d2fb6e0087a6bbef5418aee8024bba9dd527e26`); no new
  catalog tag is needed because this development-line commit changes only the
  BOM version and release bookkeeping, not shared dependency refs.
- Separate stable hold document:
  `docs/releases/2026-08-07-dependencies-1.5.0-release-checklist.md`.
- Stable `1.5.0` tag, GitHub Release, and Maven Central publication remain
  unauthorized by this development checklist.

## Stop condition

This checklist is complete for the development snapshot train. The separate
stable checklist is a hold document only: do not create a `1.5.0` stable tag,
GitHub Release, or stable Maven publication until its exact-head CI/review,
catalog decision, and fresh publication authority gates are approved.
