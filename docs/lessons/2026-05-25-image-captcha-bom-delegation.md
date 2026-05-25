# Image Captcha BOM Delegation

## Context

`bluetape4k-dependencies` already imports `bluetape4k-image-bom` as a platform.
After `bluetape4k-image` added `bluetape4k-images-captcha`, the managed catalog
sync tried to expose the module as a separate alias and BOM constraint before
the artifact was available in the snapshot repository.

## Decision

Keep captcha version management delegated to `bluetape4k-image-bom` and defer the
individual `bluetape4k-dependencies` catalog alias until the captcha artifact is
published.

## Outcome

Consumers that import `bluetape4k-dependencies` still receive the image BOM
platform. They can use captcha once the artifact is published without requiring
`bluetape4k-dependencies` to carry a separate captcha alias immediately.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `scripts/sync-managed-catalog.py --check --summary`
- `scripts/verify-managed-artifacts.py --summary --allow-snapshots`

## Future Guard

Remove the `-captcha` exclusion after the captcha artifact is published and a
catalog alias is useful for consumers.
