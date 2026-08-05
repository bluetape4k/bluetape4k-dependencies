# bluetape4k-dependencies 1.4.0 Release Checklist

Status: **PENDING**
Target version: `1.4.0`
Latest observed external version: `1.3.1`
Release authority: tags, workflow dispatch, publication, GitHub Releases,
merges, milestone closure, and cleanup require fresh explicit approval.

## Pinned Candidate

- Dependencies candidate HEAD: `188f27c012801e011c416ee4e0cfded9294293d9`
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
- Dispatch hold: no catalog tag, semver tag, or workflow dispatch is authorized
  while any selected stable upstream POM is unavailable.

## Stable Upstream Order

| Stage | Repository | Version | Exact candidate | Current gate |
|---:|---|---:|---|---|
| 1 | bluetape4k-projects | `1.12.0` | `66fe47d3` | PENDING |
| 2 | bluetape4k-exposed | `1.12.0` | `16a8fed2` | PENDING |
| 2 | bluetape4k-image | `0.4.0` | `295c7228` | PENDING |
| 2 | bluetape4k-text | `0.3.0` | `dedfb886` | PENDING |
| 2 | bluetape4k-graph | `0.6.0` | `95677bb7` | PENDING |
| 2 | bluetape4k-javers | `0.3.0` | `6ac3b824` | PENDING |
| 3 | bluetape4k-aws | `0.5.0` | `7584c2f3` | PENDING |
| 3 | bluetape4k-leader | `0.5.0` | `7f6bcc51` | PENDING |
| 4 | bluetape4k-dependencies | `1.4.0` | final stable-pin head | BLOCKED |

## Publication Gates

- [x] **PUB-01 / REL-01 — Pin release identity and inventory.**
  Target, external baseline, candidate commit, catalog bytes, consumer scope,
  and excluded examples are recorded above.
- [ ] **PUB-02 / REL-02 — Close live planning gaps.**
  Issues #168 and #169 remain open; upstream changelogs/WIP and
  release-affecting pull requests still need disposition.
- [x] **PUB-03 / REL-03 — Prove the current local candidate.**
  Nine downstream full builds, 175 POM/effective-model checks, and 260 isolated
  resolved-graph observations passed at the pinned candidate set.
- [ ] **PUB-04 / REL-04 / REL-05 — Prove public stable prerequisites.**
  All eight selected upstream stable BOM POMs currently return HTTP 404, and the
  generated dependencies POM imports eight snapshot BOMs.
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
- [x] **PRE-04 — Verify current source identity and catalog content checksum.**
- [ ] **PRE-07 — Generate stable-only publication POMs.**
  Current generation succeeds structurally but contains snapshot imports.
- [ ] **PRE-08 / PRE-09 — Verify publishing diagnostics, credentials, and the
  final artifact matrix.**
- [ ] **PRE-10 — Obtain fresh explicit approval for irreversible actions.**

## Stop Condition

Do not create tags, dispatch workflows, publish artifacts, create GitHub
Releases, merge release branches, close milestones, or clean worktrees until all
unchecked prerequisites above are satisfied and the exact action receives fresh
explicit approval.
