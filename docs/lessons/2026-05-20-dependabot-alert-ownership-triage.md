# Dependabot Alert Ownership Triage

## Context

Dependabot security alerts appear in downstream repositories even when the
vulnerable dependency version is governed by `bluetape4k-dependencies`.
Merging downstream Dependabot changes directly creates catalog drift and
duplicated dependency decisions.

## Decision

Classify alerts by dependency ownership before changing versions:

- `central-catalog`: update `bluetape4k-dependencies` first, then sync downstream.
- `central-bom-transitive`: update the owning BOM line when a patched BOM exists,
  or keep a central override until it does.
- `repo-tooling`: fix repository settings/plugin tooling unless the package is
  promoted to central governance.
- `repo-local`: fix the manifest-owning repository directly.

## Outcome

`scripts/triage-dependabot-alerts.py` now reads GitHub vulnerability alerts,
matches packages against the central catalog and ignore list, and emits a
markdown or JSON ownership report. BouncyCastle, ClassGraph, and Tomcat alert
ownership is now explicit in the central catalog and BOM constraints.

## Verification

- `python3 -m py_compile scripts/sync-managed-catalog.py scripts/sync-shared-versions.py scripts/sync-dependabot-ignores.py scripts/triage-dependabot-alerts.py`
- `python3 -m unittest tests/test_sync_dependabot_ignores.py tests/test_sync_shared_versions.py tests/test_sync_managed_catalog.py tests/test_triage_dependabot_alerts.py`
- `scripts/sync-shared-versions.py --workspace .. --check --summary`
- `scripts/sync-dependabot-ignores.py --workspace .. --check --summary`
- `scripts/triage-dependabot-alerts.py --repo bluetape4k-exposed`
- `scripts/triage-dependabot-alerts.py --repo bluetape4k-projects`
- `./gradlew build`

## Future Guidance

Do not close downstream Dependabot alerts by editing leaf catalogs first when
the package is centrally governed. Add a central line, sync downstream catalogs
and ignores, and only then handle repo-local leftovers.
