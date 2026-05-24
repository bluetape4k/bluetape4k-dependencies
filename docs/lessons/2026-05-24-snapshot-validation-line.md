# Snapshot Validation Line

## Context

After the previous release, snapshot validation needed the ecosystem BOM repo
reopened on the next development line while importing matching upstream
snapshots.

## Decision

Set `baseVersion=1.1.4`, keep `snapshotVersion=` empty, and point imported
bluetape4k BOM versions at the matching `-SNAPSHOT` lines.

## Outcome

The repository can publish `1.1.4-SNAPSHOT` through `publish-snapshot.yml`
without checking a snapshot suffix into `gradle.properties`.

## Verification

Pending in the snapshot validation train.
