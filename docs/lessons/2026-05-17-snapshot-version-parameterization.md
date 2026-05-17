# Snapshot Version Parameterization

Context: Central Portal releases should not require editing `gradle.properties`
only to remove `-SNAPSHOT`.

Decision: Keep `snapshotVersion=` empty by default and let
`publish-snapshot.yml` pass `-PsnapshotVersion=-SNAPSHOT`.

Outcome: `develop` stays release-ready, while snapshot publishing remains
explicit in the workflow command.

Dependencies-specific outcome: the ecosystem BOM catalog now keeps
`bluetape4k-*` coordinates on formal release versions; snapshot references must
not be reintroduced before Central Portal release. Keep
`bluetape4k-dependencies` as the first release-train alias in version catalogs.
Name release-train version aliases after the BOM artifacts, for example
`bluetape4k-bom`, `bluetape4k-aws-bom`, and `bluetape4k-exposed-bom`.

Release scope: `bluetape4k-experimental` and `bluetape4k-workshop` are excluded
from the Central Portal release campaign, so default shared-version validation
must not clone or gate on them.

Verification: `actionlint .github/workflows/publish-snapshot.yml`;
`python3 -m unittest discover -s tests -p 'test_*.py'`.

Future guard: Do not reintroduce `snapshotVersion=-SNAPSHOT` as the default in
`gradle.properties`.
