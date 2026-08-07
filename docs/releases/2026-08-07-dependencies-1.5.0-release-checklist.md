# bluetape4k-dependencies 1.5.0 Stable Release Checklist

Status: **HOLD / NOT AUTHORIZED FOR PUBLICATION**
Target: `bluetape4k-dependencies` BOM `1.5.0`
Latest stable: `1.4.0`
Development snapshot evidence: `docs/releases/2026-08-07-dependencies-1.5.0-development-checklist.md`

## Release boundary

- Stable publication is not authorized by this document. It is a preparation
  artifact for the next explicit release decision.
- The published snapshot train covers dependencies plus Projects, AWS, Exposed,
  Graph, Image, Javers, Leader, and Text. Workshop/example/application
  repositories are excluded; Experimental remains catalog-only.
- Existing stable catalog consumers remain pinned to immutable catalog commit
  `catalog/2026-08-06-03` (`3d2fb6e0087a6bbef5418aee8024bba9dd527e26`) until a
  future dependency-change train proves and approves a new catalog tag.

## Required gates before any stable side effect

- [ ] Fresh exact `develop` SHA inventory and release authority.
- [ ] Fresh PR/review/CI proof for the release commit and release checklist.
- [ ] Stable candidate POM and effective-model validation for all publishers.
- [ ] Stable-equivalent snapshot proof with no source/catalog drift.
- [ ] Fresh tag/release absence and declared workflow-input audit.
- [ ] Explicit user approval for tag creation, Maven Central publication, and
  GitHub Release. These are separate gates.
- [ ] Post-publication Central POM, checksum, release, catalog, manual, and site
  verification followed by a new next-version development checklist.

## Current evidence baseline

- Dependencies `1.5.0-SNAPSHOT` metadata: HTTP 200, build 1.
- All eight library snapshot lines have exact-head Nightly and publication
  success; all nine BOM metadata records are HTTP 200.
- Central catalog/POM validation is clean: 168 aliases, 8 sub-BOMs, and
  `failures=0`, `repositories=9`, `files=173`, `dependencies=45211`,
  `maven_models=173`.
- No stable `1.5.0` tag, GitHub Release, or stable publication may be created
  until every required gate above is freshly rechecked.

## Stop condition

Remain on HOLD unless all unchecked gates are freshly PASS and a separate,
explicit approval authorizes each irreversible stable side effect.
