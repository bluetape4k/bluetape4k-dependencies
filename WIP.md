# WIP - bluetape4k-dependencies

Snapshot: 2026-08-05 KST
Scope: dependencies 1.4.0 coordinated stable release train.
Milestone: 1.4.0, 2 open issues (#168 and #169).

## Current Direction

`1.4.0` is the final BOM in a coordinated upstream release train. The external
catalog upgrade candidate is locally verified, but the current BOM imports eight
unpublished snapshot BOMs and is not a stable publication candidate yet.

The release order is:

1. `bluetape4k-projects:1.12.0`
2. `bluetape4k-exposed:1.12.0`, `bluetape4k-image:0.4.0`,
   `bluetape4k-text:0.3.0`, `bluetape4k-graph:0.6.0`, and
   `bluetape4k-javers:0.3.0`
3. `bluetape4k-aws:0.5.0` and `bluetape4k-leader:0.5.0`
4. Replace all eight snapshot BOM refs with Maven Central-visible stable refs,
   cut a new catalog train ref, repeat downstream/POM gates, then publish
   `bluetape4k-dependencies:1.4.0`.

`bluetape4k-workshop` and other example repositories are outside the stable
release train. `bluetape4k-experimental` participated only in catalog consumer
validation and does not publish a stable BOM for this train.

## Candidate Evidence

- Central candidate HEAD: `188f27c012801e011c416ee4e0cfded9294293d9`
- Catalog source commit: `fbb6df78d04fcb9d7252ce0a1338ee67af9fa817`
- Catalog SHA-256: `9c9469f516e818dd4c0503babaff182613d7994b109441e78acf3bc4842c25df`
- External-version audit: 509 authorities and 543 compatibility lines.
- Adoption ledger: 121 deltas, 130 authorities, 260 exact before/after
  resolved-graph observations, all verified.
- Consumer validation: nine library repositories passed full local builds at
  their pinned candidate heads; 175 generated POMs and Maven effective models
  passed with zero failures.

## Current Blockers

- All eight target stable upstream BOM POMs return Maven Central HTTP 404.
- The generated `1.4.0` POM still imports all eight `*-SNAPSHOT` BOMs.
- Exact candidate full CI/Nightly evidence is absent across the upstream train.
- Upstream changelogs and WIP/release notes are incomplete or stale.
- Release-affecting open PRs require explicit merge, close, or waiver decisions.
- Catalog tags, semver tags, workflow dispatch, publication, releases, merges,
  milestone closure, and cleanup remain separate approval gates.

## Priority Queue

1. Make `bluetape4k-projects:1.12.0` release-ready and publish it.
2. Promote core consumers to the public stable BOM and complete their exact-head
   validation and release notes.
3. Publish the remaining upstream BOMs in dependency order.
4. Replace snapshot refs in this repository, cut the final catalog candidate,
   and repeat the POM, downstream, and resolved-graph gates.
5. Request fresh approval for the `1.4.0` tag and release workflow dispatch.

## WIP Limits

| Lane | Limit | Current next |
|---|---:|---|
| Stable release | 1 | Prepare and verify `bluetape4k-projects:1.12.0`. |
| Catalog promotion | 1 | Hold until every selected stable upstream POM is HTTP 200. |
| Publication | 0 | No tag or dispatch before the final stable-POM gate. |
