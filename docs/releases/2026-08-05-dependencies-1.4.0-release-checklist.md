# bluetape4k-dependencies 1.4.0 Release Checklist

Status: **PENDING**
Target version: `1.4.0`
Latest observed external version: `1.3.1`
Release authority: the user explicitly authorized the complete stable train,
including tags, workflow dispatch, publication, GitHub Releases, merges,
milestone closure, follow-up work, and safe cleanup on 2026-08-06.

## Pinned Candidate

- Dependencies candidate HEAD: `7628e66c5e0c44e99a3401ceea5b7a253a6b4118`
- Catalog source commit: `fbb6df78d04fcb9d7252ce0a1338ee67af9fa817`
- Catalog SHA-256: `9c9469f516e818dd4c0503babaff182613d7994b109441e78acf3bc4842c25df`
- Resolved-graph receipt SHA-256:
  `1f019f350fa9c52c82f0152f2dd517fed55d93be354123b46df0d017f63d7c97`
- Full candidate receipt SHA-256:
  `0453bac944f1b92c24c6ce8257afc54812cf0033041e15dbb5b483939dce4e5f`
- Consumer scope: eight published library repositories plus
  `bluetape4k-experimental` for catalog-only validation.
- Excluded scope: `bluetape4k-workshop` and all example application/workshop
  repositories.
- Projects corrective final source HEAD:
  `7cf0b73646af05c0f8872cc4f6a16983949c4e3e`.
- Dispatch hold: no downstream catalog tag or semver tag may advance while its
  selected stable upstream POM is unavailable. Projects `1.12.1` passed exact
  push CI and Full Nightly; its automatic snapshot run is the active hold.

## Stable Upstream Order

| Stage | Repository | Version | Exact candidate | Current gate |
|---:|---|---:|---|---|
| 1 | bluetape4k-projects | `1.12.1` | `7cf0b736` | CENTRAL 75/75 PASS |
| 2 | bluetape4k-exposed | `1.12.0` | `16a8fed2` | PENDING |
| 2 | bluetape4k-image | `0.4.0` | `295c7228` | PENDING |
| 2 | bluetape4k-text | `0.3.0` | `dedfb886` | PENDING |
| 2 | bluetape4k-graph | `0.6.0` | `95677bb7` | PENDING |
| 3 | bluetape4k-javers | `0.3.0` | `6ac3b824` | PENDING ON EXPOSED |
| 3 | bluetape4k-aws | `0.5.0` | `7584c2f3` | PENDING |
| 3 | bluetape4k-leader | `0.5.0` | `7f6bcc51` | PENDING |
| 4 | bluetape4k-dependencies | `1.4.0` | final stable-pin head | BLOCKED |

## Publication Gates

- [x] **PUB-01 / REL-01 — Pin release identity and inventory.**
  Target, external baseline, candidate commit, catalog bytes, consumer scope,
  and excluded examples are recorded above.
- [ ] **PUB-02 / REL-02 — Close live planning gaps.**
  Issues #168 and #169 remain open until the public train completes; remaining
  upstream action-only pull requests will be dispositioned per repository
  before each stable tag.
- [x] **PUB-03 / REL-03 — Prove the current local candidate.**
  Nine downstream full builds, 175 POM/effective-model checks, and 260 isolated
  resolved-graph observations passed at the pinned candidate set.
- [ ] **PUB-04 / REL-04 / REL-05 — Prove public stable prerequisites.**
  Projects `1.12.1` is public with 75/75 POMs; the remaining seven selected
  upstream BOM POMs are pending and remain snapshot imports until released.
- [ ] **PUB-05 — Refresh the irreversible dispatch hold.**
  Re-read exact final heads, tags, CI/Nightly, reviews, threads, mergeability,
  credentials, workflow inputs, public POMs, and authorization immediately
  before each tag or dispatch.
- [ ] **PUB-06 — Dispatch upstream releases in dependency order.**
- [ ] **PUB-07 — Verify every public stable upstream artifact.**
- [ ] **PUB-08 / REL-06 — Promote and resynchronize the stable catalog.**
  Replace all eight snapshot refs only after their stable POMs are HTTP 200,
  then cut a new catalog train ref and repeat downstream/POM/graph verification.
- [ ] **PUB-09 / REL-07 — Publish dependencies 1.4.0.**
- [ ] **PUB-10 / REL-08 — Complete public documentation and milestone handoff.**

## Preflight Gates

- [x] **PRE-01 / PRE-05 — Confirm version transition and repository inventory.**
- [ ] **PRE-02 — Close live milestone and pull-request blockers.**
- [ ] **PRE-03 / PRE-06 — Finalize dated release notes and public artifact checks.**
  Projects `1.12.0` release notes are dated `2026-08-05`; its stable BOM remains
  HTTP 404 until the authorized stable publication completes.
- [x] **PRE-04 — Verify current source identity and catalog content checksum.**
- [ ] **PRE-07 — Generate stable-only publication POMs.**
  Current generation succeeds structurally but contains snapshot imports.
- [ ] **PRE-08 / PRE-09 — Verify publishing diagnostics, credentials, and the
  final artifact matrix.**
- [x] **PRE-10 — Record explicit authority for irreversible actions.**
  The active-thread instruction authorizes all train releases and follow-up
  closeout; each action still requires a fresh live hold read-back.

## Projects 1.12.1 Corrective Preflight Refresh — 2026-08-06

- The immutable `1.12.0` release was incomplete because 19 constrained
  non-published modules were expected, and its corrective publication inventory
  work was promoted to `1.12.1`.
- PR #1314 merged the publication inventory contract as
  `af19a8e25c6e5f432a58253bfbb2e055590078d2`; its first exact snapshot proved
  74/75 timestamped POMs and exposed the missing BOM aggregation.
- PR #1316 added the BOM to NMCP aggregation and merged as final source HEAD
  `7cf0b73646af05c0f8872cc4f6a16983949c4e3e`. Exact push CI run
  `31028017255` and Full Nightly run `31028038544` both succeeded.
- The source declares `baseVersion=1.12.1`, empty `snapshotVersion`, and a dated
  `1.12.1` changelog section.
- Nightly workflow blob `88eda7c574da137e041939737ec38d683205ff92`
  declares only optional choice input `scope`; the selected value is `full`.
- Publish Snapshot workflow blob
  `11e6b3d6358f3d71f222eccce9ddb45e97e516ff` automatically checks out the
  successful Nightly head SHA and publishes only after that Nightly succeeds.
- Signed tag `1.12.1` resolves to the exact final source HEAD. Snapshot run
  `31034013600` and release run `31035173270` both succeeded.
- Central Snapshots returned 75/75 timestamped POMs and Maven Central returned
  75/75 stable POMs. The catalog now promotes only `bluetape4k-bom` to
  `1.12.1`; all downstream stable refs remain blocked on their own releases.

## Stop Condition

Do not advance a dependent release while its prerequisite artifact or exact
candidate proof is pending. The user has authorized the complete train, but
every irreversible action still requires the immediately preceding live hold,
workflow-schema read-back, and complete post-action artifact verification.
