# Release Train CI Downstream Sync

## Context

The `catalog/2026-05-25-00` train validates downstream repositories on
release-train branches before those branches are merged back to `develop`.

## Decision

Allow `sync-shared-versions.py --check` to tolerate downstream default-branch
drift only for manual GitHub Actions dispatches outside `develop`.

## Outcome

Release-train CI can validate the dependencies BOM and catalog scripts without
failing on expected default-branch drift in downstream repositories. Regular
local checks and `develop` validations still fail when drift is present.

## Verification

- `./gradlew build --refresh-dependencies --console=plain -PsnapshotVersion=-SNAPSHOT`
- `python3 -m unittest tests.test_sync_shared_versions.SyncSharedVersionsTest.test_cli_check_allows_release_train_manual_dispatch_drift`
- `git diff --check`

## Future Guard

Do not use default-branch downstream sync as a hard gate for manually dispatched
release-train branch validation. Keep that guard on integration-branch checks.
