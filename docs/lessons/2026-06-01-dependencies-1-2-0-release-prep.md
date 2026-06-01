# Dependencies 1.2.0 Release Prep

## Context

The dependencies 1.2.0 train should promote the latest Maven Central-visible
stable BOMs across the bluetape4k ecosystem. `bluetape4k-graph` needed a new
`0.5.0` release before this train could close. `bluetape4k-exposed`,
`bluetape4k-aws`, and `bluetape4k-leader` were then promoted again after their
final train artifacts became visible on Maven Central.

## Decision

Use the following stable BOM matrix:

- `bluetape4k-bom:1.10.0`
- `bluetape4k-aws-bom:0.3.1`
- `bluetape4k-exposed-bom:1.10.0`
- `bluetape4k-graph-bom:0.5.0`
- `bluetape4k-image-bom:0.2.0`
- `bluetape4k-javers-bom:0.2.0`
- `bluetape4k-leader-bom:0.3.1`
- `bluetape4k-text-bom:0.2.0`

Use `bluetape4k-exposed` `1.10.0`, `bluetape4k-aws` `0.3.1`, and
`bluetape4k-leader` `0.3.1` only after their BOMs and representative modules
return Maven Central HTTP 200.

## Outcome

The central catalog and BOM constraints can move to `baseVersion=1.2.0` with
only public stable upstream artifacts. Managed module generation should include
newly published image and Javers modules gated out of 1.1.4.

## Verification

- Maven Central HTTP 200 for projects `1.10.0`, AWS `0.3.1`, exposed `1.10.0`,
  graph `0.5.0`, image `0.2.0`, Javers `0.2.0`, leader `0.3.1`, and text
  `0.2.0`.
- Graph release workflow succeeded:
  `https://github.com/bluetape4k/bluetape4k-graph/actions/runs/26734244764`.
- Exposed, AWS, and leader release workflows succeeded:
  `https://github.com/bluetape4k/bluetape4k-exposed/actions/runs/26736279613`,
  `https://github.com/bluetape4k/bluetape4k-aws/actions/runs/26737796498`, and
  `https://github.com/bluetape4k/bluetape4k-leader/actions/runs/26754212311`.

## Future Guidance

Do not include a locally bumped repository version in `bluetape4k-dependencies`
until its BOM is visible on Maven Central. An open release epic is enough to
hold the previous published BOM even when local README snippets already show the
next version.
