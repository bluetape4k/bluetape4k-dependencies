# Dependencies 1.2.0 Release Complete

## Context

The final 1.2.0 dependencies train promoted the latest public stable bluetape4k
BOM inputs, including AWS `0.3.1` and leader `0.3.1`.

## Decision

After the `1.2.0` release tag published, reopen `develop` on `baseVersion=1.3.0`
and set the shared catalog self-version to the latest released
`bluetape4k-dependencies:1.2.0`.

## Outcome

Downstream repositories can now consume `bluetape4k-dependencies:1.2.0`, while
the dependencies repository is ready for the next train.

## Verification

- Release workflow succeeded:
  `https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/26756150389`.
- GitHub Release exists:
  `https://github.com/bluetape4k/bluetape4k-dependencies/releases/tag/1.2.0`.
- Maven Central returned HTTP 200 for
  `io.github.bluetape4k:bluetape4k-dependencies:1.2.0` POM and module metadata.

