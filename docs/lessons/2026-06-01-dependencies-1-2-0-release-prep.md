# Dependencies 1.2.0 Release Prep

## Context

The dependencies 1.2.0 train should promote the latest Maven Central-visible
stable BOMs across the bluetape4k ecosystem. `bluetape4k-graph` needed a new
`0.5.0` release before this train could close.

## Decision

Use the following stable BOM matrix:

- `bluetape4k-bom:1.10.0`
- `bluetape4k-aws-bom:0.3.0`
- `bluetape4k-exposed-bom:1.9.2`
- `bluetape4k-graph-bom:0.5.0`
- `bluetape4k-image-bom:0.2.0`
- `bluetape4k-javers-bom:0.2.0`
- `bluetape4k-leader-bom:0.3.0`
- `bluetape4k-text-bom:0.2.0`

Keep `bluetape4k-exposed` on `1.9.2` because `1.10.0` is not published and the
1.10.0 epic still tracks downstream workshop/example scope.

## Outcome

The central catalog and BOM constraints can move to `baseVersion=1.2.0` with
only public stable upstream artifacts. Managed module generation should include
newly published image and Javers modules gated out of 1.1.4.

## Verification

- Maven Central HTTP 200 for projects `1.10.0`, AWS `0.3.0`, exposed `1.9.2`,
  graph `0.5.0`, image `0.2.0`, Javers `0.2.0`, leader `0.3.0`, and text
  `0.2.0`.
- Maven Central HTTP 404 for exposed `1.10.0`.
- Graph release workflow succeeded:
  `https://github.com/bluetape4k/bluetape4k-graph/actions/runs/26734244764`.

## Future Guidance

Do not include a locally bumped repository version in `bluetape4k-dependencies`
until its BOM is visible on Maven Central. An open release epic is enough to
hold the previous published BOM even when local README snippets already show the
next version.
