# Issue #104 Snapshot Resolution Lesson

## Context

Downstream CI/Nightly/Examples workflows consuming the `1.11.0-SNAPSHOT` train
hit transient Maven Central snapshot metadata and artifact `403` responses.

## Decision

Keep snapshot freshness bounded instead of forcing refreshes. Downstream
workflows should avoid `--refresh-dependencies`, cache changing modules for one
day, warm representative compile tasks before large matrices, and retry only
Central snapshot `403` resolution signatures.

## Outcome

Added a reusable retry wrapper and documented the operating rule in the central
version-management runbook. Representative reruns showed `javers` and `exposed`
Nightly passing; remaining `leader` Examples failures were Vert.x/Fabric8 binary
compatibility failures, not snapshot resolution.

The catalog sync also detected local Exposed database modules that had not yet
been published to Central snapshots. Keep `cockroachdb` and `starrocks` gated
until their first published line so PR CI artifact availability remains a hard
release signal.

`verify-managed-artifacts.py --allow-snapshots` must not treat Central snapshot
`403` responses as missing artifacts. Retry only that status for snapshot
metadata, keep `404` as a hard missing-artifact failure, and keep release-line
verification strict.

## Verification

- `bash -n scripts/retry-snapshot-resolution.sh`
- `python3 -m unittest tests/test_retry_snapshot_resolution.py`
- `python3 -m unittest tests/test_verify_managed_artifacts.py`
- `scripts/sync-managed-catalog.py --workspace /Users/debop/work/bluetape4k --check --summary`
- `scripts/verify-managed-artifacts.py --summary --allow-snapshots`
- `git diff --check`

## Future Guard

Do not use broad Gradle command retries as proof of snapshot stability. Retry
only known Central snapshot resolution signatures, and split unrelated runtime
or test failures into repo-local issues. Do not expose newly discovered modules
from sibling repos until their artifacts exist in the selected release or
snapshot repository line. Keep artifact availability relaxation limited to
snapshot `403`; do not relax snapshot `404` or release verification.
