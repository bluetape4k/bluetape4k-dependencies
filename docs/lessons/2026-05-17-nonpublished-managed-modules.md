# Non-published managed modules

## Context

`bluetape4k-dependencies` generates its catalog aliases and BOM constraints
from sibling repositories. The generator must use the same publishable-module
policy as the upstream BOMs.

## Decision

Exclude `examples/`, `*-examples`, `*-demo`, `benchmark/`, and `*-benchmark`
modules in `scripts/sync-managed-catalog.py`, then regenerate the managed
catalog and constraint blocks.

## Outcome

Benchmark aliases and constraints are removed from the generated graph module
set, and future non-published modules stay out of the dependencies BOM.

## Verification

- `python3 -m unittest tests/test_sync_managed_catalog.py`
- `scripts/sync-managed-catalog.py --write --check --summary`
- `./gradlew generatePomFileForBluetapeDependenciesPublication generatePomFileForBluetapeVersionCatalogPublication --no-daemon --no-configuration-cache --no-build-cache`
- Generated dependencies metadata scan found no `examples`, `demo`, or
  `benchmark` entries.
