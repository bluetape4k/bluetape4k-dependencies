# Lesson: leader 0.2.0 catalog promotion

**Date**: 2026-05-23

## Context

`bluetape4k-leader` 0.2.0 was published through the tag-driven release workflow
and now needs to be consumable through the central BOM and version catalog. The
catalog release should be a minor `1.1.0` because the public managed release
train changes and the generated leader DynamoDB alias enters the published
catalog surface.

## Decision

Promote `bluetape4k-dependencies` to 1.1.0 and `bluetape4k-leader-bom` from
0.1.0 to 0.2.0 only after the upstream release workflow succeeds. Keep README
examples aligned with the current published train so the examples do not
suggest stale snapshot or maintenance lines.

## Outcome

The central version catalog and BOM now target the 1.1.0 catalog release and
the published leader 0.2.0 release train, including the newly generated DynamoDB
alias from the previous catalog sync.

## Verification

- `python3 -m py_compile scripts/sync-managed-catalog.py scripts/sync-shared-versions.py scripts/sync-dependabot-ignores.py tests/*.py`.
- `python3 -m unittest discover -s tests -p 'test_*.py'`.
- `scripts/sync-managed-catalog.py --check --summary`.
- `scripts/sync-shared-versions.py --workspace .. --check --summary` after
  generating downstream catalog sync branches.
- `scripts/sync-dependabot-ignores.py --workspace .. --check --summary`.
- `./gradlew build publishToMavenLocal --no-daemon`.

## Future Guidance

After each upstream official release, update the corresponding upstream version
ref, the `bluetape4k-dependencies` release version, and README version examples
before cutting the next central BOM/catalog release.
